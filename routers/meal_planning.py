from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Recipe, FoodInventory, Category, user_categories
from database import get_db
from routers.auth import get_current_user_dependency

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
    """ Updates food inventory with item name, quantity, desired quantity, and categories """
    try:
        inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).all()

        # Remove existing inventory
        for item in inventory:
            db.delete(item)

        # Add new inventory
        for item in food_data["items"]:
            new_inventory = FoodInventory(
                user_id=current_user["id"],
                name=item["name"],
                quantity=item["quantity"],
                desired_quantity=item["desiredQuantity"],
                categories=",".join(map(str, item["categories"]))  # Store category IDs as a string
            )
            db.add(new_inventory)

        db.commit()
        return {"message": "Food inventory updated successfully."}

    except Exception as e:
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
                "categories": list(map(int, item.categories.split(","))) if item.categories else []
            }
            for item in inventory
        ]
    }

### 📁 Manage Categories
@router.post("/categories")
def add_category(category_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    """ Add new categories to the database and associate them with the user """
    try:
        if "categories" not in category_data or not isinstance(category_data["categories"], list):
            raise HTTPException(status_code=400, detail="Invalid request format. Expected 'categories': [list]")

        added_categories = []
        for category_name in category_data["categories"]:
            existing_category = db.query(Category).filter(Category.name == category_name).first()
            if not existing_category:
                new_category = Category(name=category_name)
                db.add(new_category)
                db.commit()
                db.refresh(new_category)
                added_categories.append(new_category.name)
            else:
                added_categories.append(existing_category.name)

            # Associate user with category
            db.execute(user_categories.insert().values(user_id=current_user["id"], category_id=new_category.id if not existing_category else existing_category.id))
            db.commit()

        return {"message": "Categories updated successfully.", "added_categories": added_categories}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

### 📁 Get All Categories for a User
@router.get("/categories")
def get_user_categories(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    """ Fetch all categories linked to the user """
    user_categories_query = db.execute(
        f"SELECT c.name FROM categories c JOIN user_categories uc ON c.id = uc.category_id WHERE uc.user_id = {current_user['id']}"
    ).fetchall()

    return {"categories": [row[0] for row in user_categories_query]}