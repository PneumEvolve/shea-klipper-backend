from fastapi import APIRouter, Depends, HTTPException, Query, Request
import requests
from bs4 import BeautifulSoup
import openai
import json
from sqlalchemy.orm import Session
from models import Recipe, FoodInventory, Category, GroceryList, GroceryItem, user_categories
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
        # 🟢 Step 1: Fetch the webpage
        response = requests.get(url, timeout=10)
        if not response.ok:
            raise HTTPException(status_code=400, detail="Failed to fetch URL content")

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")

        # 🧠 Step 2: Send to OpenAI for parsing
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

        # ✅ Try to parse result as JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="AI returned invalid JSON")

        # ✅ Ensure basic fields exist
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
        # Fetch existing inventory
        existing_inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user.id).all()

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
                    user_id=current_user.id,
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
    inventory = db.query(FoodInventory).filter(FoodInventory.user_id == current_user.id).all()

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
        if "categories" not in category_data or not isinstance(category_data["categories"], list):
            raise HTTPException(status_code=400, detail="Invalid request format. Expected 'categories': [list]")

        category_type = category_data.get("type", "food")  # default to "food" if missing
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

            # ✅ Check if user-category link already exists
            exists = db.execute(
                text("""
                    SELECT 1 FROM user_categories
                    WHERE user_id = :user_id AND category_id = :category_id
                """),
                {"user_id=current_user.id, "category_id": category_id}
            ).first()

            if not exists:
                db.execute(user_categories.insert().values(user_id=current_user.id, category_id=category_id))
                db.commit()

        return {"message": "Categories updated successfully.", "added_categories": added_categories}

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
    
    # Remove associations from user_categories table
    db.execute(user_categories.delete().where(user_categories.c.category_id == category_id))
    
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}

@router.post("/grocery-lists/from-recipes")
def generate_grocery_list_from_recipes(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    recipe_ids = payload.get("recipe_ids", [])
    if not recipe_ids:
        raise HTTPException(status_code=400, detail="No recipe IDs provided")

    recipes = db.query(Recipe).filter(
        Recipe.id.in_(recipe_ids),
        Recipe.user_id == current_user.id
    ).all()

    grocery_list = GroceryList(
        user_id=current_user.id,
        name=payload.get("name", "New Grocery List")
    )
    db.add(grocery_list)
    db.flush()  # So we can get grocery_list.id

    # Aggregate ingredients
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
    db.refresh(grocery_list)

    return {
        "grocery_list_id": grocery_list.id,
        "items": [{"name": k, "quantity": v} for k, v in ingredient_counts.items()]
    }
@router.get("/grocery-lists")
def get_grocery_lists(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    lists = db.query(GroceryList).filter(GroceryList.user_id == current_user.id).all()
    return [{"id": gl.id, "name": gl.name, "completed": gl.completed} for gl in lists]


@router.get("/grocery-lists/{list_id}/items")
def get_grocery_list_items(list_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user_dependency)):
    grocery_list = db.query(GroceryList).filter_by(id=list_id, user_id=current_user.id).first()
    if not grocery_list:
        raise HTTPException(status_code=404, detail="Grocery list not found")

    items = db.query(GroceryItem).filter(GroceryItem.grocery_list_id == list_id).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "checked": item.checked
        } for item in items
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
        GroceryList.user_id == current_user.id
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
        GroceryList.user_id == current_user.id,
        GroceryItem.checked == True
    ).all()

    for item in items:
        existing = db.query(FoodInventory).filter_by(
            name=item.name,
            user_id=current_user.id
        ).first()

        if existing:
            existing.quantity += item.quantity
        else:
            new_food = FoodInventory(
                user_id=current_user.id,
                name=item.name,
                quantity=item.quantity,
                desired_quantity=item.quantity,
                categories=""
            )
            db.add(new_food)

    db.commit()
    return {"message": f"{len(items)} items added to inventory"}
