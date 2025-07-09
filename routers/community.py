from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Community, CommunityMember, User
from schemas import CommunityCreate, CommunityOut
from routers.auth import get_current_user_dependency
from typing import List

router = APIRouter(prefix="/communities", tags=["communities"])

# Create a new community
@router.post("/", response_model=CommunityOut)
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

@router.get("/communities/", response_model=List[CommunityOut])
def get_communities(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    return db.query(Community).all()