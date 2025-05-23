from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from models import GroceryList, GroceryItem, FoodInventory, Recipe, User
from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()


@router.get("/grocery-list")
def get_or_create_grocery_list(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    grocery_list = db.query(GroceryList).filter(
        GroceryList.user_id == current_user.id
    ).order_by(GroceryList.created_at.desc()).first()

    if not grocery_list:
        grocery_list = GroceryList(
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )
        db.add(grocery_list)
        db.commit()
        db.refresh(grocery_list)

    items = db.query(GroceryItem).filter(GroceryItem.grocery_list_id == grocery_list.id).all()
    return {
        "id": grocery_list.id,
        "items": [
            {"id": item.id, "name": item.name, "quantity": item.quantity, "checked": item.checked}
            for item in items
        ]
    }


@router.post("/grocery-list/item")
def add_item_to_grocery_list(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    grocery_list = db.query(GroceryList).filter(
        GroceryList.user_id == current_user.id
    ).order_by(GroceryList.created_at.desc()).first()

    if not grocery_list:
        raise HTTPException(status_code=404, detail="No grocery list found")

    item = GroceryItem(
        grocery_list_id=grocery_list.id,
        name=payload.get("name"),
        quantity=payload.get("quantity", 1),
        checked=False
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {"message": "Item added", "item": {"id": item.id, "name": item.name, "quantity": item.quantity, "checked": item.checked}}


@router.put("/grocery-list/item/{item_id}")
def update_item(
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    item = db.query(GroceryItem).join(GroceryList).filter(
        GroceryItem.id == item_id,
        GroceryList.user_id == current_user.id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = payload.get("name", item.name)
    item.quantity = payload.get("quantity", item.quantity)
    item.checked = payload.get("checked", item.checked)

    db.commit()
    return {"message": "Item updated"}


@router.delete("/grocery-list/item/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    item = db.query(GroceryItem).join(GroceryList).filter(
        GroceryItem.id == item_id,
        GroceryList.user_id == current_user.id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}

@router.post("/grocery-list/import-to-inventory")
def import_checked_items_to_inventory(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    grocery_list = db.query(GroceryList).filter(
        GroceryList.user_id == current_user.id
    ).order_by(GroceryList.created_at.desc()).first()

    if not grocery_list:
        raise HTTPException(status_code=404, detail="No grocery list found")

    checked_items = db.query(GroceryItem).filter(
        GroceryItem.grocery_list_id == grocery_list.id,
        GroceryItem.checked == True
    ).all()

    if not checked_items:
        return {"message": "No items marked as 'in cart'"}

    added_count = 0
    for item in checked_items:
        # Add to inventory or update existing
        existing = db.query(FoodInventory).filter_by(
            user_id=current_user.id,
            name=item.name
        ).first()

        if existing:
            existing.quantity += item.quantity or 1
        else:
            db.add(FoodInventory(
                user_id=current_user.id,
                name=item.name,
                quantity=item.quantity or 1,
                desired_quantity=item.quantity or 1,
                categories=""
            ))
        # Delete item from grocery list
        db.delete(item)
        added_count += 1

    db.commit()
    return {"message": f"{added_count} items imported and removed from grocery list"}

@router.post("/grocery-list/from-inventory")
def add_shortfalls_to_grocery_list(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    # Fetch user inventory
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user.id).all()

    if not inventory:
        raise HTTPException(status_code=404, detail="No inventory found.")

    # Calculate what needs to be added to the list
    shortfalls = [
        {
            "name": item.name,
            "quantity": item.desired_quantity - item.quantity
        }
        for item in inventory
        if item.quantity < item.desired_quantity
    ]

    if not shortfalls:
        return {"message": "All inventory items are fully stocked."}

    # Get or create grocery list
    grocery_list = (
        db.query(GroceryList)
        .filter(GroceryList.user_id == current_user.id)
        .order_by(GroceryList.created_at.desc())
        .first()
    )

    if not grocery_list:
        grocery_list = GroceryList(
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )
        db.add(grocery_list)
        db.flush()

    # Add items to list
    for item in shortfalls:
        grocery_item = GroceryItem(
            grocery_list_id=grocery_list.id,
            name=item["name"],
            quantity=item["quantity"]
        )
        db.add(grocery_item)

    db.commit()

    return {
        "message": f"{len(shortfalls)} shortfall item(s) added to grocery list.",
        "items_added": shortfalls
    }

@router.post("/from-recipes")
def add_ingredients_from_recipes(recipe_ids: list[int], db: Session = Depends(get_db), current_user: User = Depends(get_current_user_dependency)):
    try:
        # Find or create user's grocery list
        grocery_list = db.query(GroceryList).filter_by(user_id=current_user.id).first()
        if not grocery_list:
            grocery_list = GroceryList(user_id=current_user.id, created_at=datetime.utcnow())
            db.add(grocery_list)
            db.commit()
            db.refresh(grocery_list)

        added_items = []

        for recipe_id in recipe_ids:
            recipe = db.query(Recipe).filter_by(id=recipe_id, user_id=current_user.id).first()
            if not recipe:
                continue

            ingredients = [i.strip() for i in recipe.ingredients.split(",") if i.strip()]
            for ingredient in ingredients:
                grocery_item = GroceryItem(
                    grocery_list_id=grocery_list.id,
                    name=ingredient,
                    quantity=1,
                    checked=False
                )
                db.add(grocery_item)
                added_items.append(ingredient)

        db.commit()
        return {"message": f"✅ Added ingredients from {len(recipe_ids)} recipe(s) to grocery list.", "added": added_items}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to import ingredients from recipes: {str(e)}")
