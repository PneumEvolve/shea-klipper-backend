from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Community, CommunityMember, User
from schemas import CommunityCreate, CommunityOut, CommunityMemberOut, CommunityUpdate
from routers.auth import get_current_user_dependency
from typing import List, Optional

router = APIRouter(prefix="/communities", tags=["communities"])

# Create a new community
@router.post("/create", response_model=CommunityOut)
def create_community(
    data: CommunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    # Create the community
    new_community = Community(
        name=data.name,
        description=data.description,
        visibility=data.visibility,
        creator_id=current_user.id
    )
    db.add(new_community)
    db.commit()
    db.refresh(new_community)

    # Add creator as a member
    member = CommunityMember(user_id=current_user.id, community_id=new_community.id)
    db.add(member)
    db.commit()

    return new_community

@router.get("/list", response_model=List[CommunityOut])
def get_communities(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    return db.query(Community).all()

@router.get("/{community_id}", response_model=CommunityOut)
def get_community_by_id(
    community_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return community

@router.put("/{community_id}", response_model=CommunityOut)
def update_community(
    community_id: int,
    update_data: CommunityUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency),
):
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

# Request to join a community
@router.post("/{community_id}/join")
def request_to_join_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    existing = db.query(CommunityMember).filter_by(
        user_id=current_user.id, community_id=community_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already requested or member")

    new_request = CommunityMember(
        user_id=current_user.id,
        community_id=community_id,
        is_approved=False  # Pending
    )
    db.add(new_request)
    db.commit()
    return {"message": "Join request submitted."}


# Approve or reject member (admin only)
@router.post("/{community_id}/members/{user_id}/approve")
def approve_member(
    community_id: int,
    user_id: int,
    approve: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
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


# Get member list (approved only)
@router.get("/{community_id}/members", response_model=List[CommunityMemberOut])
def get_members(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    return db.query(CommunityMember).filter_by(
        community_id=community_id, is_approved=True
    ).all()


# Get pending join requests (admin only)
@router.get("/{community_id}/join-requests", response_model=List[CommunityMemberOut])
def get_pending_requests(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    community = db.query(Community).filter_by(id=community_id).first()
    if not community or community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return db.query(CommunityMember).filter_by(
        community_id=community_id, is_approved=False
    ).all()

@router.delete("/{community_id}")
def delete_community(
    community_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    community = db.query(Community).filter_by(id=community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    if community.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this community")

    # Delete all associated members
    db.query(CommunityMember).filter_by(community_id=community_id).delete()

    db.delete(community)
    db.commit()
    return {"detail": "Community deleted successfully"}

@router.delete("/{community_id}/members/{user_id}")
def remove_member(
    community_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
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

