from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# User Schema
class UserCreate(BaseModel):
    email: str
    password: str
    recaptcha_token: str

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
        from_attributes = True

class CommentOut(BaseModel):
    id: int
    text: str
    user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

class ThreadOut(BaseModel):
    id: int
    text: str
    user_id: Optional[int]
    created_at: datetime
    comments: List[CommentOut] = []

    class Config:
        from_attributes = True

class ThreadCreate(BaseModel):
    text: str

class CommentCreate(BaseModel):
    thread_id: int
    text: str

class WeDreamEntrySchema(BaseModel):
    vision: str
    mantra: str


# Garden Schemas
class GardenCreate(BaseModel):
    type: str
    host_name: str
    location: str
    description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class GardenOut(GardenCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Volunteer Application Schemas
class VolunteerApplicationCreate(BaseModel):
    garden_id: int
    name: str
    email: str
    message: Optional[str] = None

class VolunteerApplicationOut(VolunteerApplicationCreate):
    id: int
    approved: Optional[bool]
    submitted_at: datetime

    class Config:
        from_attributes = True


class VolunteerRequestCreate(BaseModel):
    garden_id: int
    volunteer_name: str
    volunteer_email: Optional[str] = None

class VolunteerRequestResponse(BaseModel):
    id: int
    garden_id: int
    volunteer_name: str
    volunteer_email: Optional[str]
    status: str
    created_at: datetime

    class Config:
        orm_mode = True

class VolunteerRequestUpdate(BaseModel):
    status: str