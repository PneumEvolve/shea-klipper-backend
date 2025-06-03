from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from database import get_db
from models import Node, User
from routers.auth import get_current_user_dependency

router = APIRouter(prefix="/nodes", tags=["Nodes"])

class NodeCreate(BaseModel):
    name: str
    mission: Optional[str] = None
    resources: Optional[str] = None
    skills_needed: Optional[str] = None

class NodeOut(BaseModel):
    id: int
    name: str
    mission: Optional[str]
    resources: Optional[str]
    skills_needed: Optional[str]
    user_id: int

    class Config:
        orm_mode = True

@router.post("/create", response_model=NodeOut)
def create_node(
    node_data: NodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    new_node = Node(
        name=node_data.name,
        mission=node_data.mission,
        resources=node_data.resources,
        skills_needed=node_data.skills_needed,
        user_id=current_user.id
    )
    db.add(new_node)
    db.commit()
    db.refresh(new_node)
    return new_node

@router.get("/", response_model=List[NodeOut])
def get_all_nodes(db: Session = Depends(get_db)):
    return db.query(Node).all()

@router.get("/my-nodes", response_model=List[NodeOut])
def get_user_nodes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    return db.query(Node).filter(Node.user_id == current_user.id).all()

@router.post("/join/{node_id}")
def join_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency)
):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if node in current_user.nodes_joined:
        raise HTTPException(status_code=400, detail="Already joined this node")

    current_user.nodes_joined.append(node)
    db.commit()
    return {"message": "Successfully joined node."}
