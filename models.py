from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base  # Import Base model from database.py

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    transcriptions = relationship("Transcription", back_populates="user", cascade="all, delete-orphan")
    recipes = relationship("Recipe", back_populates="user", cascade="all, delete-orphan")

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    transcription_text = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)  # ✅ Store the upload time

    # ✅ Ensure this relationship exists
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="transcriptions")

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # Link recipes to specific users
    name = Column(String, nullable=False)
    ingredients = Column(Text, nullable=False)  # Store as comma-separated values
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="recipes")  # Connect recipes to users

class FoodInventory(Base):
    __tablename__ = "food_inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # Link inventory to specific users
    ingredients = Column(Text, nullable=True)  # Store as comma-separated values

    user = relationship("User", back_populates="food_inventory")