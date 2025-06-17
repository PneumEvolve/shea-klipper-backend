from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Table, Boolean, Float, func
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# ✅ Many-to-Many Relationships
user_categories = Table(
    "user_categories",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True)
)

node_membership = Table(
    "node_membership",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("node_id", Integer, ForeignKey("nodes.id"), primary_key=True)
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
    threads = relationship("Thread", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    we_dream_entries = relationship("WeDreamEntry", back_populates="user")

    nodes = relationship("Node", back_populates="user")  # Nodes this user created
    nodes_joined = relationship(  # Nodes this user joined
        "Node",
        secondary=node_membership,
        back_populates="members"
    )


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
    reflection = Column(Text, nullable=True)
    mantra = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)

    user = relationship("User", back_populates="journal_entries")


class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="threads", lazy="joined")
    comments = relationship("Comment", back_populates="thread", cascade="all, delete")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread_id = Column(Integer, ForeignKey("threads.id"))
    thread = relationship("Thread", back_populates="comments")

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="comments", lazy="joined")


class WeDreamEntry(Base):
    __tablename__ = "we_dream_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vision = Column(Text, nullable=False)
    mantra = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="we_dream_entries")


class DreamMachineOutput(Base):
    __tablename__ = "dream_machine_outputs"

    id = Column(Integer, primary_key=True, index=True)
    summary = Column(Text, nullable=False)
    mantra = Column(String, nullable=False)
    entry_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mission = Column(String, nullable=True)
    resources = Column(String, nullable=True)
    skills_needed = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="nodes")  # Creator

    members = relationship(
        "User",
        secondary=node_membership,
        back_populates="nodes_joined"
    )

class Garden(Base):
    __tablename__ = "gardens"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)  # e.g., "private", "community", "school"
    host_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("VolunteerApplication", back_populates="garden", cascade="all, delete-orphan")


# Volunteer Application model
class VolunteerApplication(Base):
    __tablename__ = "volunteer_applications"

    id = Column(Integer, primary_key=True, index=True)
    garden_id = Column(Integer, ForeignKey("gardens.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    approved = Column(Boolean, default=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    garden = relationship("Garden", back_populates="applications")