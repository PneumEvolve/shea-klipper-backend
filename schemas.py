from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# User Schema
class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    

    class Config:
        from_attributes = True  # ✅ Fix for Pydantic V2

# Transcription Schema
class TranscriptionCreate(BaseModel):
    filename: str
    transcription_text: str

    class Config:
        from_attributes = True  # ✅ Fix for Pydantic V2

class FoodInventoryUpdateSchema(BaseModel):
    items: List[str]

class RecipeSelection(BaseModel):
    recipe_ids: List[int]

class RamblingCreate(BaseModel):
    content: str
    tag: Optional[str] = None

class RamblingOut(RamblingCreate):
    id: int

    class Config:
        from_attributes = True

class User(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True  # or orm_mode = True if you're using Pydantic v1

class JournalEntryCreate(BaseModel):
    title: str
    content: str

class JournalEntryOut(JournalEntryCreate):
    id: int
    created_at: datetime
    reflection: Optional[str] = None
    mantra: Optional[str] = None
    next_action: Optional[str] = None

    class Config:
        orm_mode = True