from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from models import GroceryList, GroceryItem, FoodInventory, Recipe
from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()

@router.post("/grocery-lists/from-recipes")
def generate_grocery_list_from_recipes(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    recipe_ids = payload.get("recipe_ids", [])
    if not recipe_ids:
        raise HTTPException(status_code=400, detail="No recipe IDs provided.")

    recipes = db.query(Recipe).filter(
        Recipe.id.in_(recipe_ids),
        Recipe.user_id == current_user["id"]
    ).all()

    grocery_list = GroceryList(user_id=current_user["id"], name="From Recipes", created_at=datetime.utcnow())
    db.add(grocery_list)
    db.flush()

    ingredient_counts = {}
    for recipe in recipes:
        for item in recipe.ingredients.split(","):
            item = item.strip()
            if item:
                ingredient_counts[item] = ingredient_counts.get(item, 0) + 1

    for ingredient, quantity in ingredient_counts.items():
        db.add(GroceryItem(
            grocery_list_id=grocery_list.id,
            name=ingredient,
            quantity=quantity
        ))

    db.commit()
    return {"grocery_list_id": grocery_list.id, "items": [{"name": k, "quantity": v} for k, v in ingredient_counts.items()]}

@router.post("/grocery-lists/from-inventory")
def generate_grocery_list_from_inventory(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user["id"]).all()
    shortfalls = []

    for item in inventory:
        needed = item.desired_quantity - item.quantity
        if needed > 0:
            shortfalls.append({"name": item.name, "quantity": needed})

    if not shortfalls:
        raise HTTPException(status_code=400, detail="No shortfalls found.")

    grocery_list = GroceryList(user_id=current_user["id"], name="From Inventory", created_at=datetime.utcnow())
    db.add(grocery_list)
    db.flush()

    for item in shortfalls:
        db.add(GroceryItem(
            grocery_list_id=grocery_list.id,
            name=item["name"],
            quantity=item["quantity"]
        ))

    db.commit()
    return {"message": "Grocery list created from inventory", "items": shortfalls}

@router.get("/grocery-lists")
def get_grocery_lists(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    lists = db.query(GroceryList).filter(GroceryList.user_id == current_user["id"]).all()
    return [{"id": gl.id, "name": gl.name, "completed": gl.completed} for gl in lists]

@router.get("/grocery-lists/{list_id}/items")
def get_grocery_list_items(list_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    grocery_list = db.query(GroceryList).filter_by(id=list_id, user_id=current_user["id"]).first()
    if not grocery_list:
        raise HTTPException(status_code=404, detail="Grocery list not found")

    items = db.query(GroceryItem).filter(GroceryItem.grocery_list_id == list_id).all()
    return [
        {"id": item.id, "name": item.name, "quantity": item.quantity, "checked": item.checked}
        for item in items
    ]

@router.put("/grocery-items/{item_id}")
def update_grocery_item(
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    item = db.query(GroceryItem).join(GroceryList).filter(
        GroceryItem.id == item_id,
        GroceryList.user_id == current_user["id"]
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = payload.get("name", item.name)
    item.quantity = payload.get("quantity", item.quantity)
    item.checked = payload.get("checked", item.checked)

    db.commit()
    return {"message": "Item updated"}

@router.post("/grocery-lists/{list_id}/import-to-inventory")
def import_checked_items_to_inventory(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    items = db.query(GroceryItem).join(GroceryList).filter(
        GroceryItem.grocery_list_id == list_id,
        GroceryList.user_id == current_user["id"],
        GroceryItem.checked == True
    ).all()

    for item in items:
        existing = db.query(FoodInventory).filter_by(name=item.name, user_id=current_user["id"]).first()
        if existing:
            existing.quantity += item.quantity
        else:
            db.add(FoodInventory(
                user_id=current_user["id"],
                name=item.name,
                quantity=item.quantity,
                desired_quantity=item.quantity,
                categories=""
            ))

    db.commit()
    return {"message": f"{len(items)} items imported to inventory"}