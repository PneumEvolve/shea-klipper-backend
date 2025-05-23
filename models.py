from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Table, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

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
    has_active_payment = Column(Boolean, default=False)
    api_balance_dollars = Column(Float, default=0.0)

    payments = relationship("Payment", back_populates="user")
    transcription_usages = relationship("TranscriptionUsage", back_populates="user")
    transcriptions = relationship("Transcription", back_populates="user", cascade="all, delete-orphan")
    recipes = relationship("Recipe", back_populates="user", cascade="all, delete-orphan")
    food_inventory = relationship("FoodInventory", back_populates="user", cascade="all, delete-orphan")
    ramblings = relationship("Rambling", back_populates="user", cascade="all, delete-orphan")
    grocery_lists = relationship("GroceryList", back_populates="user", cascade="all, delete-orphan")
    journal_entries = relationship("JournalEntry", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", secondary=user_categories, back_populates="users")

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    transcription_text = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

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
    categories = Column(Text, nullable=True)

    user = relationship("User", back_populates="food_inventory")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False, default="food")

    users = relationship("User", secondary=user_categories, back_populates="categories")

class GroceryList(Base):
    __tablename__ = "grocery_lists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="grocery_lists")
    items = relationship("GroceryItem", back_populates="grocery_list", cascade="all, delete-orphan")

class GroceryItem(Base):
    __tablename__ = "grocery_items"

    id = Column(Integer, primary_key=True, index=True)
    grocery_list_id = Column(Integer, ForeignKey("grocery_lists.id"), nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=True)
    checked = Column(Boolean, default=False)

    grocery_list = relationship("GroceryList", back_populates="items")

class TranscriptionUsage(Base):
    __tablename__ = "transcription_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tokens_used = Column(Integer)
    cost = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transcription_usages")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="usd")
    stripe_session_id = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    tokens_purchased = Column(Integer)

    user = relationship("User", back_populates="payments")

class Rambling(Base):
    __tablename__ = "ramblings"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    tag = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="ramblings")

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="journal_entries")