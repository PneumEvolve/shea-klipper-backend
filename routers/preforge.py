from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Dict, List
from uuid import uuid4




from database import get_db
from models import PreForgeTopic, PreForgeItem, PreForgeTag
from schemas import (
    PreForgeTopicCreate,
    PreForgeTopicUpdate,
    PreForgeTopicOut,
    PreForgeItemCreate,
    PreForgeItemOut,
    PreForgeSyncIn,
)
from routers.auth import get_current_user_model
from models import User
import re

router = APIRouter(prefix="/preforge", tags=["preforge"])


def normalize_tag(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().replace("#", ""))


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
        client_id=getattr(t, "client_id", None),  # NEW
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

    # NEW: idempotent create if client_id provided
    if payload.client_id:
        existing = (
            db.query(PreForgeTopic)
            .filter(PreForgeTopic.user_id == user.id, PreForgeTopic.client_id == payload.client_id)
            .first()
        )
        if existing:
            return topic_to_out(existing)

    topic = PreForgeTopic(
        user_id=user.id,
        title=title,
        pinned=payload.pinned or "",
        client_id=payload.client_id,  # NEW
    )
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

    # NEW: idempotent create if client_id provided
    if payload.client_id:
        existing = (
            db.query(PreForgeItem)
            .filter(PreForgeItem.topic_id == topic.id, PreForgeItem.client_id == payload.client_id)
            .first()
        )
        if existing:
            return PreForgeItemOut.model_validate(existing)

    item = PreForgeItem(
        topic_id=topic.id,
        kind=kind,
        text=text,
        client_id=payload.client_id,  # NEW
    )
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

@router.get("/topics/by-client/{client_id}", response_model=PreForgeTopicOut)
def get_topic_by_client_id(client_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user_model)):
    topic = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.user_id == user.id, PreForgeTopic.client_id == client_id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Not found")
    return topic_to_out(topic)

@router.post("/sync", response_model=list[PreForgeTopicOut])
def sync_preforge(
    payload: PreForgeSyncIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_model),
):
    """
    Merge client snapshot into server.
    - Upsert topics by (user_id, client_id)
    - Upsert items by (topic_id, client_id)
    - Tags are normalized and attached per-topic
    - Also backfills missing server client_id(s) for older rows so future merges stay stable
    Returns: full server truth (all topics for user)
    """

    incoming_topics = payload.topics or []

    # --- Backfill: ensure existing server topics/items have client_id so merges don't duplicate later ---
    # (This is important if you had topics created before client_id existed.)
    existing_topics_all = db.query(PreForgeTopic).filter(PreForgeTopic.user_id == user.id).all()
    for t in existing_topics_all:
        if not getattr(t, "client_id", None):
            t.client_id = str(uuid4())

    existing_items_all = (
        db.query(PreForgeItem)
        .join(PreForgeTopic, PreForgeItem.topic_id == PreForgeTopic.id)
        .filter(PreForgeTopic.user_id == user.id)
        .all()
    )
    for it in existing_items_all:
        if not getattr(it, "client_id", None):
            it.client_id = str(uuid4())

    db.flush()

    # --- Prefetch existing topics by client_id for quick upsert ---
    client_ids = [t.client_id for t in incoming_topics if t.client_id]
    existing_by_client: Dict[str, PreForgeTopic] = {}
    if client_ids:
        rows = (
            db.query(PreForgeTopic)
            .filter(PreForgeTopic.user_id == user.id, PreForgeTopic.client_id.in_(client_ids))
            .all()
        )
        existing_by_client = {r.client_id: r for r in rows if r.client_id}

    # --- Prefetch tags by name (per user unique) ---
    # Collect all tags we might need
    all_tag_names = set()
    for t in incoming_topics:
        for raw in (t.tags or []):
            name = normalize_tag(raw)
            if name:
                all_tag_names.add(name)

    tags_by_name: Dict[str, PreForgeTag] = {}
    if all_tag_names:
        existing_tags = (
            db.query(PreForgeTag)
            .filter(PreForgeTag.user_id == user.id, PreForgeTag.name.in_(list(all_tag_names)))
            .all()
        )
        tags_by_name = {tg.name: tg for tg in existing_tags}

    # Create missing tags
    for name in all_tag_names:
        if name not in tags_by_name:
            tg = PreForgeTag(user_id=user.id, name=name)
            db.add(tg)
            db.flush()
            tags_by_name[name] = tg

    # --- Upsert topics + their items ---
    for incoming in incoming_topics:
        cid = incoming.client_id
        if not cid:
            # We require client_id for sync to be safe; skip if missing
            continue

        title = (incoming.title or "").strip()
        if not title:
            # ignore empty titles to avoid bad rows
            continue

        topic = existing_by_client.get(cid)
        if not topic:
            topic = PreForgeTopic(
                user_id=user.id,
                client_id=cid,
                title=title,
                pinned=incoming.pinned or "",
            )
            db.add(topic)
            db.flush()
            existing_by_client[cid] = topic
        else:
            # update fields
            topic.title = title
            if incoming.pinned is not None:
                topic.pinned = incoming.pinned or ""

        # set topic tags
        normalized = []
        for raw in (incoming.tags or []):
            name = normalize_tag(raw)
            if name and name in tags_by_name:
                normalized.append(tags_by_name[name])
        # dedupe by id
        topic.tags = list({tg.id: tg for tg in normalized}.values())

        # items upsert for this topic
        incoming_items = incoming.items or []
        item_client_ids = [i.client_id for i in incoming_items if i.client_id]

        existing_items_by_client: Dict[str, PreForgeItem] = {}
        if item_client_ids:
            rows = (
                db.query(PreForgeItem)
                .filter(PreForgeItem.topic_id == topic.id, PreForgeItem.client_id.in_(item_client_ids))
                .all()
            )
            existing_items_by_client = {r.client_id: r for r in rows if r.client_id}

        for it in incoming_items:
            icid = it.client_id
            if not icid:
                continue

            kind = (it.kind or "note").strip()
            if kind not in ("note", "question"):
                kind = "note"

            text = (it.text or "").strip()
            if not text:
                continue

            row = existing_items_by_client.get(icid)
            if not row:
                row = PreForgeItem(
                    topic_id=topic.id,
                    client_id=icid,
                    kind=kind,
                    text=text,
                )
                db.add(row)
                db.flush()
                existing_items_by_client[icid] = row
            else:
                row.kind = kind
                row.text = text

    db.commit()

    # return server truth (all topics)
    topics = (
        db.query(PreForgeTopic)
        .filter(PreForgeTopic.user_id == user.id)
        .order_by(PreForgeTopic.updated_at.desc())
        .all()
    )
    return [topic_to_out(t) for t in topics]