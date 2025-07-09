from fastapi import APIRouter, Depends, HTTPException, Query
import requests
from bs4 import BeautifulSoup
import openai
import json
from sqlalchemy.orm import Session
from models import Recipe, FoodInventory, Category, user_categories
from database import get_db
from routers.auth import get_current_user_dependency
from sqlalchemy.sql import text

router = APIRouter()

### 🥘 Add a New Recipe
@router.post("/recipes")
def add_or_update_recipe(
    recipe_data: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    recipe_id = recipe_data.get("id")
    ingredients = recipe_data["ingredients"]

    if isinstance(ingredients, list):
        ingredients = ",".join(ingredients)

    if recipe_id:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found.")

        recipe.name = recipe_data["name"]
        recipe.ingredients = ingredients
        recipe.instructions = recipe_data["instructions"]
        recipe.category = recipe_data.get("category")
    else:
        recipe = Recipe(
            user_id=current_user.id,
            name=recipe_data["name"],
            ingredients=ingredients,
            instructions=recipe_data["instructions"],
            category=recipe_data.get("category"),
        )
        db.add(recipe)

    db.commit()
    db.refresh(recipe)
    return {
        "id": recipe.id,
        "name": recipe.name,
        "ingredients": recipe.ingredients.split(","),
        "instructions": recipe.instructions,
        "category": recipe.category
    }

### 📖 Get All Recipes for a User
@router.get("/recipes")
def get_recipes(
    category: str = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    query = db.query(Recipe).filter(Recipe.user_id == current_user.id)

    if category and category.lower() != "all":
        query = query.filter(Recipe.category == category)

    recipes = query.all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "ingredients": r.ingredients.split(","),
            "instructions": r.instructions,
            "category": r.category,
        }
        for r in recipes
    ]

@router.post("/recipes/import")
def import_recipe_from_url(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        response = requests.get(url, timeout=10)
        if not response.ok:
            raise HTTPException(status_code=400, detail="Failed to fetch URL content")

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")

        prompt = f"""
        Extract the recipe from the following webpage content.
        Return a JSON object like:
        {{
            "name": "Recipe Name",
            "ingredients": ["item 1", "item 2", "..."],
            "instructions": "Step-by-step instructions"
        }}

        Webpage:
        {text}
        """

        chat = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You extract recipes from messy webpage content and return clean, structured data in JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        response_text = chat.choices[0].message.content.strip()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="AI returned invalid JSON")

        if not data.get("name") or not data.get("ingredients") or not data.get("instructions"):
            raise HTTPException(status_code=500, detail="Incomplete recipe data from AI")

        return {
            "name": data["name"],
            "ingredients": data["ingredients"],
            "instructions": data["instructions"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing recipe: {str(e)}")

### 🛒 Store User’s Food Inventory
@router.post("/food-inventory")
def update_food_inventory(food_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    try:
        existing_inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user.id).all()
        inventory_by_id = {str(item.id): item for item in existing_inventory}
        inventory_by_name = {item.name: item for item in existing_inventory}

        for item in food_data["items"]:
            item_id = str(item.get("id"))
            name = item["name"]

            if item_id and item_id in inventory_by_id:
                # Update by ID
                existing_item = inventory_by_id[item_id]
            elif name in inventory_by_name:
                # Fall back to name match
                existing_item = inventory_by_name[name]
            else:
                # Create new
                new_item = FoodInventory(
                    user_id=current_user.id,
                    name=name,
                    quantity=item["quantity"],
                    desired_quantity=item["desiredQuantity"],
                    categories=",".join(item["categories"])
                )
                db.add(new_item)
                continue  # skip to next item

            # Update existing item
            existing_item.name = name
            existing_item.quantity = item["quantity"]
            existing_item.desired_quantity = item["desiredQuantity"]
            existing_item.categories = ",".join(item["categories"])

        db.commit()
        return {"message": "Food inventory updated successfully."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating food inventory: {str(e)}")
### 🔍 Get User’s Food Inventory
@router.get("/food-inventory")
def get_food_inventory(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user.id).all()
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "quantity": item.quantity,
                "desiredQuantity": item.desired_quantity,
                "categories": item.categories.split(",") if item.categories else []
            }
            for item in inventory
        ]
    }

### 📁 Manage Categories
@router.post("/categories")
def add_category(category_data: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    try:
        if "categories" not in category_data or not isinstance(category_data["categories"], list):
            raise HTTPException(status_code=400, detail="Invalid request format. Expected 'categories': [list]")

        category_type = category_data.get("type", "food")
        added_categories = []

        for category_name in category_data["categories"]:
            existing_category = db.query(Category).filter(Category.name == category_name).first()

            if not existing_category:
                new_category = Category(name=category_name, type=category_type)
                db.add(new_category)
                db.commit()
                db.refresh(new_category)
                category_id = new_category.id
                added_categories.append(new_category.name)
            else:
                category_id = existing_category.id
                added_categories.append(existing_category.name)

            exists = db.execute(
                text("""
                    SELECT 1 FROM user_categories
                    WHERE user_id = :user_id AND category_id = :category_id
                """),
                {"user_id": current_user.id, "category_id": category_id}
            ).first()

            if not exists:
                db.execute(user_categories.insert().values(user_id=current_user.id, category_id=category_id))
                db.commit()

        return {"message": "Categories updated successfully.", "added_categories": added_categories}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=dict)
def get_user_categories(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    try:
        categories = (
            db.query(Category)
            .join(user_categories, user_categories.c.category_id == Category.id)
            .filter(user_categories.c.user_id == current_user.id)
            .all()
        )

        food = [{"id": c.id, "name": c.name} for c in categories if c.type == "food"]
        recipes = [{"id": c.id, "name": c.name} for c in categories if c.type == "recipe"]

        return {"food": food, "recipes": recipes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    db.delete(recipe)
    db.commit()
    return {"message": "Recipe deleted successfully"}

@router.delete("/food-inventory/{item_id}")
def delete_food_inventory(item_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    item = db.query(FoodInventory).filter(FoodInventory.id == item_id, FoodInventory.user_id == current_user.id).first()
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
    db.execute(user_categories.delete().where(user_categories.c.category_id == category_id))
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}