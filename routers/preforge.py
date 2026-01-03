from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import PreForgeTopic, PreForgeItem, PreForgeTag
from schemas import (
    PreForgeTopicCreate,
    PreForgeTopicUpdate,
    PreForgeTopicOut,
    PreForgeItemCreate,
    PreForgeItemOut,
)
from routers.auth import get_current_user_model
from models import User

router = APIRouter(prefix="/preforge", tags=["preforge"])


def normalize_tag(s: str) -> str:
    return (s or "").strip().replace("#", "").replace("  ", " ")


def topic_to_out(t: PreForgeTopic) -> PreForgeTopicOut:
    return PreForgeTopicOut(
        id=t.id,
        title=t.title,
        pinned=t.pinned or "",
        tags=[x.name for x in (t.tags or [])],
        items=sorted(
            [PreForgeItemOut.model_validate(i) for i in (t.items or [])],
            key=lambda x: x.created_at,
            reverse=True,
        ),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )

class TagIn(BaseModel):
    tag: str

@router.get("/topics", response_model=list[PreForgeTopicOut])
def list_topics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    topics = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.user_id == user.id)
        .order_by(PreForgeTopic.updated_at.desc())
        .all()
    )
    return [topic_to_out(t) for t in topics]


@router.post("/topics", response_model=PreForgeTopicOut)
def create_topic(
    payload: PreForgeTopicCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title required")

    topic = PreForgeTopic(user_id=user.id, title=title, pinned=payload.pinned or "")
    db.add(topic)
    db.flush()

    # tags (per-user unique)
    tags = []
    for raw in payload.tags or []:
        name = normalize_tag(raw)
        if not name:
            continue
        tag = (
            db.query(PreForgeTag)
            .filter(PreForgeTag.user_id == user.id, PreForgeTag.name == name)
            .first()
        )
        if not tag:
            tag = PreForgeTag(user_id=user.id, name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)

    topic.tags = list({t.id: t for t in tags}.values())

    db.commit()
    db.refresh(topic)
    return topic_to_out(topic)


@router.put("/topics/{topic_id}", response_model=PreForgeTopicOut)
def update_topic(
    topic_id: int,
    payload: PreForgeTopicUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    topic = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.id == topic_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if payload.title is not None:
        t = payload.title.strip()
        if not t:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        topic.title = t

    if payload.pinned is not None:
        topic.pinned = payload.pinned or ""

    db.commit()
    db.refresh(topic)
    return topic_to_out(topic)


@router.delete("/topics/{topic_id}")
def delete_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    topic = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.id == topic_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    db.delete(topic)
    db.commit()
    return {"ok": True}


@router.post("/topics/{topic_id}/items", response_model=PreForgeItemOut)
def add_item(
    topic_id: int,
    payload: PreForgeItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    topic = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.id == topic_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    kind = (payload.kind or "note").strip()
    if kind not in ("note", "question"):
        raise HTTPException(status_code=400, detail="Invalid kind")

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text required")

    item = PreForgeItem(topic_id=topic.id, kind=kind, text=text)
    db.add(item)
    db.commit()
    db.refresh(item)
    return PreForgeItemOut.model_validate(item)


@router.put("/items/{item_id}", response_model=PreForgeItemOut)
def update_item(
    item_id: int,
    payload: PreForgeItemCreate,  # reuse (kind+text)
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    item = (
        db.query(PreForgeItem)
        .join(PreForgeTopic, PreForgeItem.topic_id == PreForgeTopic.id)
        .filter(PreForgeItem.id == item_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    kind = (payload.kind or item.kind).strip()
    if kind not in ("note", "question"):
        raise HTTPException(status_code=400, detail="Invalid kind")

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text required")

    item.kind = kind
    item.text = text
    db.commit()
    db.refresh(item)
    return PreForgeItemOut.model_validate(item)


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    item = (
        db.query(PreForgeItem)
        .join(PreForgeTopic, PreForgeItem.topic_id == PreForgeTopic.id)
        .filter(PreForgeItem.id == item_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/topics/{topic_id}/tags")
def add_tag(
    topic_id: int,
    payload: TagIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    topic = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.id == topic_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    name = normalize_tag(payload.tag)
    if not name:
        raise HTTPException(status_code=400, detail="Tag required")

    tag_obj = (
        db.query(PreForgeTag)
        .filter(PreForgeTag.user_id == user.id, PreForgeTag.name == name)
        .first()
    )
    if not tag_obj:
        tag_obj = PreForgeTag(user_id=user.id, name=name)
        db.add(tag_obj)
        db.flush()

    if tag_obj not in (topic.tags or []):
        topic.tags.append(tag_obj)

    db.commit()
    return {"ok": True, "tag": name}


@router.delete("/topics/{topic_id}/tags/{tag_name}")
def remove_tag(
    topic_id: int,
    tag_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    topic = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.id == topic_id, PreForgeTopic.user_id == user.id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    name = normalize_tag(tag_name)
    topic.tags = [t for t in (topic.tags or []) if t.name != name]

    db.commit()
    return {"ok": True}