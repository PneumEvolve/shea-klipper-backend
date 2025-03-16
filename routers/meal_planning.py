from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Recipe, FoodInventory, Category
from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()

### 🥘 Add a New Recipe
@router.post("/meal-planning/recipes")
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
@router.get("/meal-planning/recipes")
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
@router.post("/meal-planning/food-inventory")
def update_food_inventory(food_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    """ Updates food inventory with item name, quantity, desired quantity, and categories """
    try:
        inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).first()
        
        if inventory:
            inventory.items = ",".join([f"{item['name']}|{item['quantity']}|{item['desiredQuantity']}|{'|'.join(item['categories'])}" for item in food_data["items"]])
        else:
            inventory = FoodInventory(
                user_id=current_user["id"], 
                items=",".join([f"{item['name']}|{item['quantity']}|{item['desiredQuantity']}|{'|'.join(item['categories'])}" for item in food_data["items"]])
            )
            db.add(inventory)

        db.commit()
        db.refresh(inventory)
        return {"message": "Food inventory updated successfully."}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating food inventory: {str(e)}")

### 🔍 Get User’s Food Inventory
@router.get("/meal-planning/food-inventory")
def get_food_inventory(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).first()
    
    if not inventory:
        return {"items": []}

    # Convert stored format back into a usable structure
    items = []
    for item_str in inventory.items.split(","):
        parts = item_str.split("|")
        if len(parts) >= 4:
            items.append({
                "name": parts[0],
                "quantity": int(parts[1]),
                "desiredQuantity": int(parts[2]),
                "categories": parts[3:].split("|")  # Convert back to list
            })

    return {"items": items}

### 📁 Manage Categories
@router.post("/meal-planning/categories")
def add_category(category_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    """ Add new categories to the database """
    existing_categories = db.query(Category).filter(Category.user_id == current_user["id"]).first()

    if existing_categories:
        existing_categories.categories = ",".join(set(existing_categories.categories.split(",") + category_data["categories"]))
    else:
        new_category_entry = Category(user_id=current_user["id"], categories=",".join(category_data["categories"]))
        db.add(new_category_entry)

    db.commit()
    return {"message": "Categories updated successfully."}

@router.get("/meal-planning/categories")
def get_categories(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    """ Fetch all categories created by the user """
    category_entry = db.query(Category).filter(Category.user_id == current_user["id"]).first()
    if not category_entry:
        return {"categories": []}

    return {"categories": category_entry.categories.split(",")}