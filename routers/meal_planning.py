from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import Recipe, FoodInventory
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
            "ingredients": r.ingredients.split(","),  # Convert back to list
            "instructions": r.instructions
        }
        for r in recipes
    ]

### 📝 Edit a Recipe
@router.put("/recipes/{recipe_id}")
def edit_recipe(recipe_id: int, recipe_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user["id"]).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    
    recipe.name = recipe_data["name"]
    recipe.ingredients = ",".join(recipe_data["ingredients"])
    recipe.instructions = recipe_data["instructions"]
    
    db.commit()
    db.refresh(recipe)
    return recipe

### ❌ Delete a Recipe
@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user["id"]).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    
    db.delete(recipe)
    db.commit()
    return {"message": "Recipe deleted successfully."}

### 🏡 Store User’s Food Inventory
@router.post("/food-inventory")
def update_food_inventory(ingredients: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).first()
    
    if inventory:
        inventory.ingredients = ",".join(ingredients["items"])
    else:
        inventory = FoodInventory(user_id=current_user["id"], ingredients=",".join(ingredients["items"]))
        db.add(inventory)
    
    db.commit()
    db.refresh(inventory)
    return inventory

### 🔍 Get User’s Food Inventory
@router.get("/food-inventory")
def get_food_inventory(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).first()
    if not inventory:
        return {"items": []}
    
    return {"items": inventory.ingredients.split(",")}