from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Recipe, FoodInventory, Category, user_categories
from database import get_db
from routers.auth import get_current_user_dependency
from sqlalchemy.sql import text

router = APIRouter()

### 🥘 Add a New Recipe
@router.post("/recipes")
def add_recipe(recipe_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    new_recipe = Recipe(
        user_id=current_user["id"],
        name=recipe_data["name"],
        ingredients=",".join(recipe_data["ingredients"]),
        instructions=recipe_data["instructions"]
    )
    db.add(new_recipe)
    db.commit()
    db.refresh(new_recipe)
    return new_recipe

### 📖 Get All Recipes for a User
@router.get("/recipes")
def get_recipes(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    recipes = db.query(Recipe).filter(Recipe.user_id == current_user["id"]).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "ingredients": r.ingredients.split(","),
            "instructions": r.instructions
        }
        for r in recipes
    ]

### 🛒 Store User’s Food Inventory
@router.post("/food-inventory")
def update_food_inventory(food_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    try:
        # Fetch existing inventory
        existing_inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).all()

        # Convert existing items to a dictionary for easy lookup
        inventory_dict = {item.name: item for item in existing_inventory}

        for item in food_data["items"]:
            if item["name"] in inventory_dict:
                # Update existing item
                inventory_dict[item["name"]].quantity = item["quantity"]
                inventory_dict[item["name"]].desired_quantity = item["desiredQuantity"]
                inventory_dict[item["name"]].categories = ",".join(item["categories"])
            else:
                # Add new item
                new_inventory = FoodInventory(
                    user_id=current_user["id"],
                    name=item["name"],
                    quantity=item["quantity"],
                    desired_quantity=item["desiredQuantity"],
                    categories=",".join(item["categories"])
                )
                db.add(new_inventory)

        db.commit()
        return {"message": "Food inventory updated successfully."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating food inventory: {str(e)}")

### 🔍 Get User’s Food Inventory
@router.get("/food-inventory")
def get_food_inventory(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).all()

    if not inventory:
        return {"items": []}

    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "quantity": item.quantity,
                "desiredQuantity": item.desired_quantity,
                "categories": item.categories.split(",") if item.categories else []  # ✅ Ensure empty categories don't break
            }
            for item in inventory
        ]
    }

### 📁 Manage Categories
@router.post("/categories")
def add_category(category_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    try:
        categories_input = category_data.get("categories", [])
        if not isinstance(categories_input, list):
            raise HTTPException(status_code=400, detail="Invalid format for categories")

        added_categories = []
        for category in categories_input:
            name = category.get("name")
            cat_type = category.get("type", "food")  # default to 'food'

            if not name:
                continue

            existing = db.query(Category).filter(Category.name == name).first()
            if not existing:
                new_category = Category(name=name, type=cat_type)
                db.add(new_category)
                db.commit()
                db.refresh(new_category)
            else:
                new_category = existing

            db.execute(user_categories.insert().values(user_id=current_user["id"], category_id=new_category.id))
            db.commit()
            added_categories.append({"name": new_category.name, "type": new_category.type})

        return {"message": "Categories added successfully.", "added": added_categories}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

### 📁 Get All Categories for a User
@router.get("/categories", response_model=dict)
def get_user_categories(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    try:
        categories = (
            db.query(Category)
            .join(user_categories, user_categories.c.category_id == Category.id)
            .filter(user_categories.c.user_id == current_user["id"])
            .all()
        )

        food = [{"id": c.id, "name": c.name} for c in categories if c.type == "food"]
        recipes = [{"id": c.id, "name": c.name} for c in categories if c.type == "recipe"]

        return {"food": food, "recipes": recipes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user["id"]).first()
    
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    
    db.delete(recipe)
    db.commit()
    return {"message": "Recipe deleted successfully"}

@router.delete("/food-inventory/{item_id}")
def delete_food_inventory(item_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    item = db.query(FoodInventory).filter(FoodInventory.id == item_id, FoodInventory.user_id == current_user["id"]).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Food inventory item not found.")
    
    db.delete(item)
    db.commit()
    return {"message": "Food inventory item deleted successfully"}

@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")
    
    # Remove associations from user_categories table
    db.execute(user_categories.delete().where(user_categories.c.category_id == category_id))
    
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}