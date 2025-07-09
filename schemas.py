from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from uuid import UUID

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
    username: str | None = None

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

# Blog Post Schemas
class BlogPostCreate(BaseModel):
    title: str
    content: str


class BlogPostOut(BlogPostCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    user_id: int

    class Config:
        from_attributes = True


# Blog Comment Schemas
class BlogCommentCreate(BaseModel):
    post_id: int
    content: str


class BlogCommentOut(BlogCommentCreate):
    id: int
    created_at: datetime
    user_id: Optional[int]

    class Config:
        from_attributes = True

# Projects

class ProjectTaskBase(BaseModel):
    content: str
    completed: bool = False

class ProjectTaskCreate(ProjectTaskBase):
    pass

class ProjectTask(ProjectTaskBase):
    id: UUID

    class Config:
        orm_mode = True

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = ""
    links: List[str] = []

class ProjectCreate(ProjectBase):
    pass

class Project(ProjectBase):
    id: UUID
    tasks: List[ProjectTask]

    class Config:
        orm_mode = True
    
class CommunityCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    visibility: str = "public"

class CommunityOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    visibility: str
    creator_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class CommunityMemberOut(BaseModel):
    user_id: int
    community_id: int
    is_approved: bool

    class Config:
        orm_mode = True

class CommunityUpdate(BaseModel):
    name: str
    description: Optional[str]
    visibility: str

class UsernameUpdate(BaseModel):
    username: str