from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base  # Import Base model from database.py

# ✅ Association Table for Many-to-Many Relationship Between Users and Categories
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

    # ✅ Many-to-Many relationship with categories
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Link recipes to specific users
    name = Column(String, nullable=False)
    ingredients = Column(Text, nullable=False)  # Store as comma-separated values
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="recipes")  # Connect recipes to users

class FoodInventory(Base):
    __tablename__ = "food_inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Link inventory to specific users
    items = Column(Text, nullable=True)  # Store food inventory items as a JSON-like string

    user = relationship("User", back_populates="food_inventory")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # Category name should be unique

    # ✅ Many-to-Many relationship with users
    users = relationship("User", secondary=user_categories, back_populates="categories")