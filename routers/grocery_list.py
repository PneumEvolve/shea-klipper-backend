from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from models import Recipe, GroceryList, GroceryItem
from database import get_db
from routers.auth import get_current_user_dependency
from schemas import RecipeSelection  # 👈 Add this

router = APIRouter()

@router.post("/generate")
def generate_grocery_list(
    payload: RecipeSelection,  # 👈 Use the Pydantic model
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    recipe_ids = payload.recipe_ids
    if not recipe_ids:
        raise HTTPException(status_code=400, detail="No recipe IDs provided.")

    recipes = db.query(Recipe).filter(Recipe.id.in_(recipe_ids), Recipe.user_id == current_user["id"]).all()
    if not recipes:
        raise HTTPException(status_code=404, detail="Recipes not found.")

    ingredient_counter = {}
    for recipe in recipes:
        ingredients = recipe.ingredients.split(",")
        for ing in ingredients:
            clean_ing = ing.strip().lower()
            if clean_ing:
                ingredient_counter[clean_ing] = ingredient_counter.get(clean_ing, 0) + 1

    grocery_list = GroceryList(user_id=current_user["id"], created_at=datetime.utcnow())
    db.add(grocery_list)
    db.commit()
    db.refresh(grocery_list)

    for name, count in ingredient_counter.items():
        item = GroceryItem(
            grocery_list_id=grocery_list.id,
            name=name,
            quantity=count
        )
        db.add(item)

    db.commit()
    db.refresh(grocery_list)

    return {
        "id": grocery_list.id,
        "created_at": grocery_list.created_at.isoformat(),
        "items": [{"name": i, "quantity": q} for i, q in ingredient_counter.items()]
    }
