from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Table, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base  # Import Base model from database.py

# ✅ Many-to-Many Relationship Between Users and Categories
user_categories = Table(
    "user_categories",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    transcriptions = relationship("Transcription", back_populates="user", cascade="all, delete-orphan")
    recipes = relationship("Recipe", back_populates="user", cascade="all, delete-orphan")
    food_inventory = relationship("FoodInventory", back_populates="user", cascade="all, delete-orphan")

    # ✅ Many-to-Many relationship with categories (via user_categories table)
    categories = relationship("Category", secondary=user_categories, back_populates="users")

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    transcription_text = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)  # ✅ Store the upload time

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="transcriptions")

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    ingredients = Column(Text, nullable=False)
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    category = Column(String, nullable=True)

    user = relationship("User", back_populates="recipes")

class FoodInventory(Base):
    __tablename__ = "food_inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    desired_quantity = Column(Integer, nullable=False, default=0)
    categories = Column(Text, nullable=True)  # Storing category IDs as comma-separated values

    user = relationship("User", back_populates="food_inventory")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False, default="food")  # 🔥 NEW: 'food' or 'recipe'

    # ✅ Many-to-Many relationship with users (via user_categories table)
    users = relationship("User", secondary=user_categories, back_populates="categories")

class GroceryList(Base):
    __tablename__ = "grocery_lists"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("GroceryItem", back_populates="list", cascade="all, delete-orphan")


class GroceryItem(Base):
    __tablename__ = "grocery_items"
    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("grocery_lists.id"), nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(String, nullable=True)
    have = Column(Boolean, default=False)  # ✅ whether the item is already in your inventory
    note = Column(String, nullable=True)

    list = relationship("GroceryList", back_populates="items")