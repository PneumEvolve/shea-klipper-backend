from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from models import Recipe, GroceryList, GroceryItem
from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()

@router.post("/grocery-list/generate")
def generate_grocery_list(
    recipe_ids: list[int],
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    if not recipe_ids:
        raise HTTPException(status_code=400, detail="No recipe IDs provided.")

    # Get selected recipes
    recipes = db.query(Recipe).filter(Recipe.id.in_(recipe_ids), Recipe.user_id == current_user["id"]).all()
    if not recipes:
        raise HTTPException(status_code=404, detail="Recipes not found.")

    # Collect ingredients
    ingredient_counter = {}
    for recipe in recipes:
        ingredients = recipe.ingredients.split(",")
        for ing in ingredients:
            clean_ing = ing.strip().lower()
            if clean_ing:
                ingredient_counter[clean_ing] = ingredient_counter.get(clean_ing, 0) + 1

    # Create grocery list
    grocery_list = GroceryList(user_id=current_user["id"], created_at=datetime.utcnow())
    db.add(grocery_list)
    db.commit()
    db.refresh(grocery_list)

    # Add items
    for name, count in ingredient_counter.items():
        item = GroceryItem(
            grocery_list_id=grocery_list.id,
            name=name,
            quantity=count  # You can customize this logic
        )
        db.add(item)

    db.commit()
    db.refresh(grocery_list)

    return {
        "id": grocery_list.id,
        "created_at": grocery_list.created_at.isoformat(),
        "items": [{"name": i, "quantity": q} for i, q in ingredient_counter.items()]
    }