from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from uuid import UUID
from models import Community, CommunityMember, User, CommunityProject, CommunityProjectTask, CommunityChatMessage
from schemas import CommunityCreate, CommunityOut, CommunityMemberOut, CommunityUpdate, CommunityProjectCreate, CommunityProjectResponse, CommunityProjectTaskCreate, CommunityProjectTaskResponse, TaskUpdate, UserInfo, ChatMessageBase, ChatMessageCreate, ChatMessage, CommunityProjectUpdate
from routers.auth import get_current_user_dependency, get_current_user_model, get_current_user_with_db
from typing import List, Optional, Tuple
from datetime import datetime

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
        creator_id=current_user.id
    )
    db.add(new_community)
    db.commit()
    db.refresh(new_community)

    member = CommunityMember(user_id=current_user.id, community_id=new_community.id)
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
    community = db.query(Community).filter(Community.id == community_id).first()
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

    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    community.name = update_data.name
    community.description = update_data.description
    community.visibility = update_data.visibility
    db.commit()
    db.refresh(community)
    return community

@router.put("/communities/{community_id}/layout")
def update_layout_config(
    community_id: int,
    layout_config: list,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    community.layout_config = layout_config
    db.commit()
    return {"success": True}

@router.post("/{community_id}/join")
def request_to_join_community(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current
    existing = db.query(CommunityMember).filter_by(
        user_id=current_user.id, community_id=community_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already requested or member")

    new_request = CommunityMember(
        user_id=current_user.id,
        community_id=community_id,
        is_approved=False
    )
    db.add(new_request)
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
    if community.creator_id != current_user.id:
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

@router.get("/{community_id}/join-requests", response_model=List[CommunityMemberOut])
def get_pending_requests(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current
    community = db.query(Community).filter_by(id=community_id).first()
    if not community or community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return db.query(CommunityMember).filter_by(
        community_id=community_id, is_approved=False
    ).all()

@router.delete("/{community_id}")
def delete_community(
    community_id: int,
    current: Tuple[User, Session] = Depends(get_current_user_with_db),
):
    current_user, db = current
    community = db.query(Community).filter_by(id=community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this community")

    db.query(CommunityMember).filter_by(community_id=community_id).delete()

    db.delete(community)
    db.commit()
    return {"detail": "Community deleted successfully"}

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

    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can remove members")

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

@router.get("/{community_id}/full-members", response_model=List[UserInfo])
def get_full_member_list(
    community_id: int,
    db: Session = Depends(get_db)
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    creator_id = community.creator_id
    approved_members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.is_approved == True
    ).all()

    user_ids = set([m.user_id for m in approved_members])
    user_ids.add(creator_id)

    users = db.query(User).filter(User.id.in_(user_ids)).all()

    result = []
    for user in users:
        result.append({
            "user_id": user.id,
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_creator": user.id == creator_id
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
