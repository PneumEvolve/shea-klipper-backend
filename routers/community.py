from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session, joinedload
from database import get_db
from uuid import UUID
from models import Community, CommunityMember, User, CommunityProject, CommunityProjectTask, CommunityChatMessage, Resource, CommunityEvent, InboxMessage
from schemas import CommunityCreate, CommunityOut, CommunityMemberOut, CommunityUpdate, CommunityProjectCreate, CommunityProjectResponse, CommunityProjectTaskCreate, CommunityProjectTaskResponse, TaskUpdate, UserInfo, ChatMessageBase, ChatMessageCreate, ChatMessage, CommunityProjectUpdate, LayoutConfigUpdate, CommunityMemberWithUserOut, ResourceCreate, ResourceOut, ResourceUpdate, CommunityEventCreate, CommunityEventUpdate, CommunityEventOut
from routers.auth import get_current_user_dependency, get_current_user_model, get_current_user_with_db
from typing import List, Optional, Tuple
from datetime import datetime, date

router = APIRouter(prefix="/communities", tags=["communities"])

# Create a new community
@router.post("/create", response_model=CommunityOut)
def create_community(
    data: CommunityCreate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    current_user, db = current

    new_community = Community(
        name=data.name,
        description=data.description,
        visibility=data.visibility,
        creator_id=current_user.id,
        layout_config=["goals", "chat", "resources", "events", "members", "admin", "component_manager"]
    )
    db.add(new_community)
    db.commit()
    db.refresh(new_community)

    # ✅ Add creator as approved admin
    member = CommunityMember(
        user_id=current_user.id,
        community_id=new_community.id,
        is_admin=True,
        is_approved=True
    )
    db.add(member)
    db.commit()

    return new_community

@router.get("/list", response_model=List[CommunityOut])
def get_communities(current: Tuple[User, Session] = Depends(get_current_user_with_db)):
    _, db = current
    return db.query(Community).all()

@router.get("/{community_id}", response_model=CommunityOut)
def get_community_by_id(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    _, db = current
    community = (
        db.query(Community)
        .options(joinedload(Community.members))  # ✅ Load members for frontend admin check
        .filter(Community.id == community_id)
        .first()
    )
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return community

@router.put("/{community_id}", response_model=CommunityOut)
def update_community(
    community_id: int,
    update_data: CommunityUpdate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Allow creator OR approved admin
    is_creator = community.creator_id == current_user.id
    is_admin = (
        db.query(CommunityMember)
        .filter_by(
            community_id=community_id,
            user_id=current_user.id,
            is_admin=True,
            is_approved=True,
        )
        .first()
        is not None
    )

    if not (is_creator or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized")

    community.name = update_data.name
    community.description = update_data.description
    community.visibility = update_data.visibility
    db.commit()
    db.refresh(community)
    return community

@router.put("/{community_id}/layout")
def update_layout_config(
    community_id: int,
    body: LayoutConfigUpdate,
    db: Session = Depends(get_db),
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    user, _ = current
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Check if the user is the creator or an approved admin
    is_creator = community.creator_id == user.id
    is_admin = db.query(CommunityMember).filter_by(
        community_id=community_id,
        user_id=user.id,
        is_admin=True,
        is_approved=True
    ).first()

    if not is_creator and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    community.layout_config = body.layout_config
    db.commit()
    return {"success": True}

@router.post("/{community_id}/join")
def request_to_join_community(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current

    # Check if the user has already requested or joined
    existing = db.query(CommunityMember).filter_by(
        user_id=current_user.id, community_id=community_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already requested or member")

    # Create the join request
    new_request = CommunityMember(
        user_id=current_user.id,
        community_id=community_id,
        is_approved=False
    )
    db.add(new_request)

    # 🔥 Get the community and notify its creator
    community = db.query(Community).filter(Community.id == community_id).first()
    if community:
        creator_id = community.creator_id  # ✅ assumes your Community model has this
        if creator_id and creator_id != current_user.id:
            content = f"👥 {current_user.username} has requested to join your community \"{community.name}\"."
            inbox = InboxMessage(
                user_id=creator_id,
                content=content,
                timestamp=datetime.utcnow()
            )
            db.add(inbox)

    db.commit()

    return {"message": "Join request submitted."}

@router.post("/{community_id}/members/{user_id}/approve")
def approve_member(
    community_id: int,
    user_id: int,
    approve: Optional[bool] = True,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current

    community = db.query(Community).filter_by(id=community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Check if the user is the creator or an admin in the community
    is_creator = community.creator_id == current_user.id

    is_admin = db.query(CommunityMember).filter_by(
        community_id=community_id,
        user_id=current_user.id,
        is_approved=True,
        is_admin=True,
    ).first() is not None

    if not (is_creator or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized")

    member = db.query(CommunityMember).filter_by(
        user_id=user_id, community_id=community_id
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if approve:
        member.is_approved = True
    else:
        db.delete(member)

    db.commit()
    return {"status": "updated"}


@router.get("/{community_id}/members", response_model=List[CommunityMemberOut])
def get_members(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    _, db = current
    return db.query(CommunityMember).filter_by(
        community_id=community_id,
        is_approved=True
    ).all()

@router.get("/{community_id}/join-requests", response_model=List[CommunityMemberWithUserOut])
def get_pending_requests(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current
    community = db.query(Community).filter_by(id=community_id).first()

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    is_creator = community.creator_id == current_user.id
    print(f"Current user ID: {current_user.id}, Creator ID: {community.creator_id}, Is Creator: {is_creator}")

    admin_membership = db.query(CommunityMember).filter_by(
        community_id=community_id,
        user_id=current_user.id,
        is_admin=True,
        is_approved=True
    ).first()

    is_admin = admin_membership is not None
    print(f"Admin membership found: {admin_membership is not None}, Is Admin: {is_admin}")

    if not (is_creator or is_admin):
        raise HTTPException(status_code=403, detail="Unauthorized")

    return (
        db.query(CommunityMember)
        .filter_by(community_id=community_id, is_approved=False)
        .options(joinedload(CommunityMember.user))
        .all()
    )

@router.delete("/{community_id}/members/{user_id}")
def remove_member(
    community_id: int,
    user_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current
    community = db.query(Community).filter_by(id=community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Allow community creator or approved admin to remove members
    is_creator = community.creator_id == current_user.id
    is_admin = db.query(CommunityMember).filter_by(
        community_id=community_id,
        user_id=current_user.id,
        is_approved=True,
        is_admin=True
    ).first() is not None

    if not (is_creator or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to remove members")

    # Prevent removing the creator
    if user_id == community.creator_id:
        raise HTTPException(status_code=403, detail="Cannot remove the community creator")

    member = db.query(CommunityMember).filter_by(
        user_id=user_id, community_id=community_id
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(member)
    db.commit()
    return {"detail": "Member removed"}


@router.put("/{community_id}/members/{user_id}/toggle-admin", response_model=CommunityMemberOut)
def toggle_admin_status(
    community_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model)
):
    membership = db.query(CommunityMember).filter_by(
        community_id=community_id,
        user_id=current_user.id
    ).first()

    if not membership or not membership.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    target = db.query(CommunityMember).filter_by(
        community_id=community_id,
        user_id=user_id
    ).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not a member of this community")

    target.is_admin = not target.is_admin
    db.commit()
    db.refresh(target)
    return target

@router.get("/{community_id}/projects", response_model=list[CommunityProjectResponse])
def get_community_projects(
    community_id: int,
    db: Session = Depends(get_db)
):
    projects = db.query(CommunityProject).filter(CommunityProject.community_id == community_id).all()
    return projects

@router.post("/{community_id}/projects", response_model=CommunityProjectResponse)
def create_community_project(
    community_id: int,
    project: CommunityProjectCreate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    current_user, db = current
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    new_project = CommunityProject(
        title=project.title,
        description=project.description,
        community_id=community_id,
        creator_id=current_user.id
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project

@router.put("/projects/{project_id}", response_model=CommunityProjectResponse)
def update_community_project(
    project_id: int,
    update: CommunityProjectUpdate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    current_user, db = current
    project = db.query(CommunityProject).filter(CommunityProject.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this project")

    if update.title is not None:
        project.title = update.title
    if update.description is not None:
        project.description = update.description

    db.commit()
    db.refresh(project)
    return project

@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_community_project(
    project_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    current_user, db = current
    project = db.query(CommunityProject).filter(CommunityProject.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")

    db.delete(project)
    db.commit()
    return

@router.get("/projects/{project_id}/tasks", response_model=list[CommunityProjectTaskResponse])
def get_project_tasks(
    project_id: int,
    db: Session = Depends(get_db)
):
    tasks = db.query(CommunityProjectTask).filter(CommunityProjectTask.project_id == project_id).all()
    return tasks

@router.post("/projects/{project_id}/tasks", response_model=CommunityProjectTaskResponse)
def create_project_task(
    project_id: int,
    task: CommunityProjectTaskCreate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    user, db = current
    project = db.query(CommunityProject).filter(CommunityProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    new_task = CommunityProjectTask(
        project_id=project_id,
        content=task.content,
        creator_id=user.id
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@router.put("/tasks/{task_id}", response_model=CommunityProjectTaskResponse)
def update_project_task(
    task_id: int,
    update: TaskUpdate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    user, db = current
    task = db.query(CommunityProjectTask).filter(CommunityProjectTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Handle assignment toggling
    if update.assigned_to_user_id is not None:
        if task.assigned_to_user_id is None:
            # Assign to current user
            task.assigned_to_user_id = user.id
        elif task.assigned_to_user_id == user.id:
            # Unassign self
            task.assigned_to_user_id = None
        else:
            # Another user is already assigned
            raise HTTPException(status_code=403, detail="Task is already assigned to another user")

    # Handle completion
    if update.completed is not None:
        task.completed = update.completed
        if update.completed is True and not task.completed_by_user_id:
            task.completed_by_user_id = user.id
        elif update.completed is False and task.completed_by_user_id == user.id:
            task.completed_by_user_id = None

    # Handle general updates
    for key, value in update.dict(exclude_unset=True).items():
        if key not in ["assigned_to_user_id", "completed"]:  # Already handled
            setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task

@router.delete("/tasks/{task_id}")
def delete_project_task(
    task_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db)
):
    _, db = current
    task = db.query(CommunityProjectTask).filter(CommunityProjectTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}

@router.get("/{community_id}/full-members", response_model=List[CommunityMemberWithUserOut])
def get_full_member_list(
    community_id: int,
    db: Session = Depends(get_db)
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    members = (
        db.query(CommunityMember)
        .options(joinedload(CommunityMember.user))
        .filter(
            CommunityMember.community_id == community_id,
            CommunityMember.is_approved == True
        )
        .all()
    )

    result = []
    for member in members:
        result.append({
            "user_id": member.user_id,
            "community_id": member.community_id,
            "is_approved": member.is_approved,
            "is_admin": member.is_admin,
            "user": member.user,
            "is_creator": member.user_id == community.creator_id  # ✅ Flag
        })

    return result

@router.post("/{community_id}/chat", response_model=ChatMessage)
def post_message(
    community_id: int,
    data: ChatMessageCreate,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    user, db = current

    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    new_msg = CommunityChatMessage(
        community_id=community_id,
        user_id=user.id,
        content=data.content,
        timestamp=datetime.utcnow()
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    return ChatMessage(
        id=new_msg.id,
        user_id=user.id,
        username=user.username,
        content=new_msg.content,
        timestamp=new_msg.timestamp
    )

@router.get("/{community_id}/chat", response_model=List[ChatMessage])
def get_messages(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    _, db = current
    messages = (
        db.query(CommunityChatMessage)
        .filter(CommunityChatMessage.community_id == community_id)
        .order_by(CommunityChatMessage.timestamp.desc())
        .limit(50)
        .all()
    )

    result = []
    for msg in reversed(messages):  # Show oldest first
        result.append(
            ChatMessage(
                id=msg.id,
                user_id=msg.user_id,
                username=msg.user.username,
                content=msg.content,
                timestamp=msg.timestamp
            )
        )
    return result

@router.delete("/{community_id}/chat/{message_id}")
def delete_message(
    community_id: int,
    message_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    user, db = current
    message = db.query(CommunityChatMessage).filter_by(id=message_id, community_id=community_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(message)
    db.commit()
    return {"detail": "Message deleted"}


@router.get("/{community_id}/resources", response_model=List[ResourceOut])
def get_resources(community_id: int, db: Session = Depends(get_db)):
    return db.query(Resource).filter(Resource.community_id == community_id).all()

@router.post("/{community_id}/resources", response_model=ResourceOut)
def create_resource(
    community_id: int,
    resource_data: ResourceCreate,
    current: tuple = Depends(get_current_user_with_db),
):
    user, db = current
    community = db.query(Community).filter_by(id=community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    resource = Resource(
        title=resource_data.title,
        url=resource_data.url,
        description=resource_data.description,
        community_id=community_id,
        user_id=user.id,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource

@router.put("/{community_id}/resources/{resource_id}", response_model=ResourceOut)
def update_resource(
    community_id: int,
    resource_id: int,
    update_data: ResourceUpdate,
    current: tuple = Depends(get_current_user_with_db),
):
    user, db = current
    resource = db.query(Resource).filter_by(id=resource_id, community_id=community_id).first()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Check permission
    is_creator = resource.community.creator_id == user.id
    is_admin = db.query(CommunityMember).filter_by(
        community_id=community_id, user_id=user.id, is_admin=True
    ).first()

    if resource.user_id != user.id and not is_creator and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    resource.title = update_data.title
    resource.url = update_data.url
    resource.description = update_data.description
    db.commit()
    db.refresh(resource)
    return resource

@router.delete("/{community_id}/resources/{resource_id}")
def delete_resource(
    community_id: int,
    resource_id: int,
    current: tuple = Depends(get_current_user_with_db),
):
    user, db = current
    resource = db.query(Resource).filter_by(id=resource_id, community_id=community_id).first()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    is_creator = resource.community.creator_id == user.id
    is_admin = db.query(CommunityMember).filter_by(
        community_id=community_id, user_id=user.id, is_admin=True
    ).first()

    if resource.user_id != user.id and not is_creator and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(resource)
    db.commit()
    return {"detail": "Resource deleted"}

# Get events for a given community
@router.get("/{community_id}/events", response_model=List[CommunityEventOut])
def list_events(
    community_id: int,
    db: Session = Depends(get_db)
):
    return db.query(CommunityEvent).filter_by(community_id=community_id).all()

# Create a new event
@router.post("/{community_id}/events", response_model=CommunityEventOut)
def create_event(
    community_id: int,
    data: CommunityEventCreate,
    current: tuple = Depends(get_current_user_with_db),
):
    user, db = current

    membership = db.query(CommunityMember).filter_by(
        user_id=user.id, community_id=community_id, is_approved=True
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member")

    new_event = CommunityEvent(
        community_id=community_id,
        user_id=user.id,
        title=data.title,
        description=data.description,
        date=data.date,
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

# Edit event
@router.put("/{community_id}/events/{event_id}", response_model=CommunityEventOut)
def update_event(
    community_id: int,
    event_id: int,
    data: CommunityEventUpdate,
    current: tuple = Depends(get_current_user_with_db),
):
    user, db = current

    event = db.query(CommunityEvent).filter_by(id=event_id, community_id=community_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get creator and admins
    community = db.query(Community).filter_by(id=community_id).first()
    membership = db.query(CommunityMember).filter_by(user_id=user.id, community_id=community_id).first()

    if not (event.user_id == user.id or membership and membership.is_admin or user.id == community.creator_id):
        raise HTTPException(status_code=403, detail="Not authorized to edit")

    event.title = data.title
    event.description = data.description
    event.date = data.date
    db.commit()
    db.refresh(event)
    return event

# Delete event
@router.delete("/{community_id}/events/{event_id}")
def delete_event(
    community_id: int,
    event_id: int,
    current: tuple = Depends(get_current_user_with_db),
):
    user, db = current

    event = db.query(CommunityEvent).filter_by(id=event_id, community_id=community_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    community = db.query(Community).filter_by(id=community_id).first()
    membership = db.query(CommunityMember).filter_by(user_id=user.id, community_id=community_id).first()

    if not (event.user_id == user.id or membership and membership.is_admin or user.id == community.creator_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete")

    db.delete(event)
    db.commit()
    return {"detail": "Event deleted"}