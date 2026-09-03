from pydantic import BaseModel, EmailStr, Field, StringConstraints, ConfigDict, constr
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
    phone_number: Optional[str] = None

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
    created_at: Optional[datetime] = None

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
    deleted_topic_client_ids: List[str] = Field(default_factory=list)
    deleted_item_client_ids: List[str] = Field(default_factory=list)


"""
Pydantic schemas for HabitGrid persistence.
Add this as schemas/habits.py (or append into schemas.py, matching your
existing layout — auth.py imports from a top-level `schemas` module).
"""

from datetime import date as date_, datetime
from typing import List, Optional, Literal
from pydantic import BaseModel


# ---------- Colors ----------

class HabitColorIn(BaseModel):
    client_id: str
    hex: str
    label: str = ""
    order_index: int = 0


class HabitColorUpdate(BaseModel):
    hex: Optional[str] = None
    label: Optional[str] = None
    order_index: Optional[int] = None


class HabitColorOut(BaseModel):
    client_id: str
    hex: str
    label: str
    order_index: int

    class Config:
        from_attributes = True


# ---------- Habits ----------

class HabitIn(BaseModel):
    client_id: str
    name: str
    order_index: int = 0


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    order_index: Optional[int] = None
    archived: Optional[bool] = None


class HabitOut(BaseModel):
    client_id: str
    name: str
    order_index: int
    archived: bool

    class Config:
        from_attributes = True


# ---------- Marks ----------

class HabitMarkUpsert(BaseModel):
    habit_client_id: str
    date: date_
    color_client_id: Optional[str] = None  # None = clear the mark


class HabitMarkOut(BaseModel):
    habit_client_id: str
    date: date_
    color_client_id: str

    class Config:
        from_attributes = True


# ---------- Goals ----------

class GoalIn(BaseModel):
    client_id: str
    title: str
    description: str = ""
    notes: Optional[str] = None
    target_date: Optional[date_] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    target_date: Optional[date_] = None
    advance_mode: Optional[Literal["auto", "manual"]] = None
    current_stage_client_id: Optional[str] = None


class GoalStageIn(BaseModel):
    client_id: str
    label: str
    criteria: str = ""
    start_date: Optional[date_] = None
    order_index: int = 0


class GoalStageUpdate(BaseModel):
    label: Optional[str] = None
    criteria: Optional[str] = None
    start_date: Optional[date_] = None
    order_index: Optional[int] = None


class GoalStageOut(BaseModel):
    client_id: str
    label: str
    criteria: str
    start_date: Optional[date_] = None
    order_index: int

    class Config:
        from_attributes = True


class GoalOut(BaseModel):
    client_id: str
    title: str
    description: str
    notes: Optional[str] = None
    target_date: Optional[date_] = None
    advance_mode: str
    current_stage_client_id: Optional[str] = None
    stages: List[GoalStageOut] = []
 
    class Config:
        from_attributes = True

# ---------- Habit <-> Goal links ----------

class HabitGoalLinkIn(BaseModel):
    habit_client_id: str
    goal_client_id: str


# ---------- Bulk state (initial load) ----------

class HabitGridState(BaseModel):
    colors: List[HabitColorOut]
    habits: List[HabitOut]
    marks: List[HabitMarkOut]
    goals: List[GoalOut]
    habit_goals: List[HabitGoalLinkIn]  # flattened {habit_client_id, goal_client_id} pairs

# ---------- Door Sales ----------

class NeighborhoodIn(BaseModel):
    name: str


class NeighborhoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime
    house_count: int = 0  # populated manually in the route, not a DB column


class DoorHouseIn(BaseModel):
    address: str
    status: str = "no_answer"
    service_interest: Optional[str] = None
    notes: Optional[str] = None
    appointment_at: Optional[datetime] = None


class DoorHouseUpdate(BaseModel):
    address: Optional[str] = None
    status: Optional[str] = None
    service_interest: Optional[str] = None
    notes: Optional[str] = None
    appointment_at: Optional[datetime] = None
    appointment_completed: Optional[bool] = None


class DoorHouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    neighborhood_id: int
    address: str
    status: str
    service_interest: Optional[str] = None
    notes: Optional[str] = None
    appointment_at: Optional[datetime] = None
    appointment_completed: bool
    visited_at: datetime
    updated_at: datetime


class AppointmentOut(BaseModel):
    house_id: int
    neighborhood_id: int
    neighborhood_name: str
    address: str
    status: str
    appointment_at: datetime