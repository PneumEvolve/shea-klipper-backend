from pydantic import BaseModel, EmailStr, Field, StringConstraints, constr
from typing import List, Optional, Annotated
from datetime import datetime, date
from uuid import UUID

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=30,
        pattern=r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
    ),
]

# User Schema
class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    username: Username                      # ← required, validated
    recaptcha_token: Optional[str] = None   # ← optional in dev
    accept_terms: bool
    terms_version: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str | None = None
    profile_pic: Optional[str] = None

    accepted_terms: bool
    accepted_terms_at: Optional[datetime] = None
    accepted_terms_version: Optional[str] = None
    

    class Config:
        from_attributes = True  # ✅ Fix for Pydantic V2
    
class AcceptTermsPayload(BaseModel):
    version: str
    accepted_at: Optional[datetime] = None

class UserInfo(UserResponse):
    user_id: int
    username: Optional[str]
    email: EmailStr
    is_creator: bool

    class Config:
        from_attributes = True

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
        from_attributes = True  # or from_attributes = True if you're using Pydantic v1

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
        from_attributes = True

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
        from_attributes = True

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
        from_attributes = True
    
class CommunityCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    visibility: str = "public"

class CommunityMemberOut(BaseModel):
    user_id: int
    community_id: int
    is_approved: bool
    is_admin: bool

    class Config:
        from_attributes = True

class CommunityOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    visibility: str
    creator_id: int
    created_at: datetime
    component_order: Optional[List[str]] = Field(None, alias="layout_config")
    members: List[CommunityMemberOut]

    class Config:
        from_attributes = True
        populate_by_name = True



class CommunityUpdate(BaseModel):
    name: str
    description: Optional[str]
    visibility: str
    layout_config: Optional[list] = None

class LayoutConfigUpdate(BaseModel):
    layout_config: List[str]

class UsernameUpdate(BaseModel):
    username: str

class ProfilePicUpdate(BaseModel):
    imageUrl: str

class CommunityProjectBase(BaseModel):
    title: str
    description: Optional[str] = None

class CommunityProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class CommunityProjectCreate(CommunityProjectBase):
    pass

class CommunityProjectResponse(CommunityProjectBase):
    id: int
    community_id: int
    creator_id: int

    class Config:
        from_attributes = True


class CommunityProjectTaskBase(BaseModel):
    content: str

class CommunityProjectTaskCreate(CommunityProjectTaskBase):
    pass

class UserSimple(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class CommunityProjectTaskResponse(CommunityProjectTaskBase):
    id: int
    project_id: int
    completed: bool
    creator_id: int
    assigned_to_user_id: Optional[int]
    completed_by_user_id: Optional[int] = None

    assigned_to: Optional[UserSimple] = None
    completed_by: Optional[UserSimple] = None

    class Config:
        from_attributes = True

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    completed: Optional[bool] = None
    assigned_to_user_id: Optional[int] = None
    completed_by_user_id: Optional[int] = None

class ChatMessageBase(BaseModel):
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: int
    user_id: int
    username: str
    timestamp: datetime

    class Config:
        from_attributes = True

class CommunityMemberWithUserOut(BaseModel):
    user_id: int
    community_id: int
    is_approved: bool
    is_admin: bool
    is_creator: bool = False
    user: UserResponse  # <-- nested user info

    class Config:
        from_attributes = True

# schemas/resource.py

class ResourceBase(BaseModel):
    title: str
    url: str
    description: Optional[str] = ""

class ResourceCreate(ResourceBase):
    pass

class ResourceUpdate(ResourceBase):
    pass

class ResourceOut(ResourceBase):
    id: int
    user_id: int
    community_id: int

    class Config:
        from_attributes = True

class CommunityEventBase(BaseModel):
    title: str
    description: Optional[str] = ""
    date: date

class CommunityEventCreate(CommunityEventBase):
    pass

class CommunityEventUpdate(CommunityEventBase):
    pass

class CommunityEventOut(CommunityEventBase):
    id: int
    user_id: int
    community_id: int

    class Config:
        from_attributes = True


# schemas/farmgame.py

class FarmGameStateBase(BaseModel):
    data: str

class FarmGameStateCreate(FarmGameStateBase):
    pass

class FarmGameStateResponse(FarmGameStateBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


# schemas/LivingPlan.py

class LivingPlanSectionSchema(BaseModel):
    title: str
    description: str
    tasks: List[str]
    notes: str = ""

    class Config:
        from_attributes = True


# --- PreForge Schemas ---------------------------------------------------------
from enum import Enum

class PreForgeItemKind(str, Enum):
    note = "note"
    question = "question"

class PreForgeItemCreate(BaseModel):
    kind: PreForgeItemKind = PreForgeItemKind.note
    text: str
    client_id: Optional[str] = None  # for offline merge

class PreForgeItemOut(BaseModel):
    id: int
    kind: PreForgeItemKind
    text: str
    created_at: datetime
    updated_at: datetime
    client_id: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

class PreForgeTopicCreate(BaseModel):
    title: str
    pinned: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)
    client_id: Optional[str] = None  # for offline merge

class PreForgeTopicUpdate(BaseModel):
    title: Optional[str] = None
    pinned: Optional[str] = None

class PreForgeTopicOut(BaseModel):
    id: int
    title: str
    pinned: str
    tags: List[str] = Field(default_factory=list)
    items: List[PreForgeItemOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    client_id: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

class PreForgeSyncItemIn(BaseModel):
    client_id: str
    kind: PreForgeItemKind = PreForgeItemKind.note
    text: str

class PreForgeSyncTopicIn(BaseModel):
    client_id: str
    title: str
    pinned: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)
    items: List[PreForgeSyncItemIn] = Field(default_factory=list)

class PreForgeSyncIn(BaseModel):
    topics: List[PreForgeSyncTopicIn] = Field(default_factory=list)