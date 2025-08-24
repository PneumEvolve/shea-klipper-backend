from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List
from sqlalchemy import func, distinct

from models import Problem, Solution, InboxMessage, Conversation, ConversationUser, User, ForgeItem, Problem, Solution, ForgeIdea as IdeaModel
from database import get_db
from models import ForgeIdea as IdeaModel

import re

router = APIRouter()

ADMIN_EMAIL = "sheaklipper@gmail.com"

# ========= Schemas =========

class SendMessageIn(BaseModel):
    sender_email: str
    content: str

class DMSendIn(BaseModel):
    sender_email: str
    recipient_email: str
    content: str

class IdeaSendIn(BaseModel):
    sender_email: str
    content: str

class FeedbackIn(BaseModel):
    contact: str
    interests: List[str] = []
    idea: Optional[str] = ""
    bugs: Optional[str] = ""
    skills: Optional[str] = ""
    extra: Optional[str] = ""


# ========= Helpers =========

def get_idea_title(db: Session, idea_id: int) -> str:
    row = db.query(IdeaModel).filter(IdeaModel.id == idea_id).first()
    return (row.title or f"Idea #{idea_id}") if row else f"Idea #{idea_id}"

def get_user_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {email} not found")
    return user

def get_or_create_system_user(db: Session) -> User:
    sys = db.query(User).filter(User.email == "system@domain.com").first()
    if sys:
        return sys
    sys = User(email="system@domain.com", username="System")
    db.add(sys)
    db.commit()
    db.refresh(sys)
    return sys

def get_or_create_system_conversation_for_user(db: Session, user: User, sys_user: User) -> Conversation:
    """
    Ensure the user has a private System conversation named 'system:{user.id}'.
    If we find an old-style convo named 'System' that includes the user, we rename it,
    attach the system user if missing, and seed a welcome if empty.
    """
    key = f"system:{user.id}"

    # Fast path: already migrated to deterministic key
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    # Legacy path: an old conversation literally named "System" that includes this user
    legacy = (
        db.query(Conversation)
        .join(ConversationUser)
        .filter(ConversationUser.user_id == user.id, Conversation.name == "System")
        .first()
    )
    if legacy:
        legacy.name = key

        # Ensure system user is attached
        has_sys = (
            db.query(ConversationUser)
            .filter(
                ConversationUser.conversation_id == legacy.id,
                ConversationUser.user_id == sys_user.id,
            )
            .first()
        )
        if not has_sys:
            db.add(ConversationUser(user_id=sys_user.id, conversation_id=legacy.id))

        # Seed welcome if empty
        has_msg = (
            db.query(InboxMessage.id)
            .filter(InboxMessage.conversation_id == legacy.id)
            .first()
        )
        if not has_msg:
            db.add(
                InboxMessage(
                    user_id=sys_user.id,
                    content="Welcome to your inbox! This is a system-generated message.",
                    timestamp=datetime.utcnow(),
                    conversation_id=legacy.id,
                )
            )

        db.commit()
        db.refresh(legacy)
        return legacy

    # Create fresh conversation with deterministic key
    convo = Conversation(name=key)
    db.add(convo)
    db.flush()  # ensure convo.id is available

    # Attach both participants
    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=sys_user.id, conversation_id=convo.id))

    # Seed welcome
    db.add(
        InboxMessage(
            user_id=sys_user.id,
            content="Welcome to your inbox! This is a system-generated message.",
            timestamp=datetime.utcnow(),
            conversation_id=convo.id,
        )
    )

    db.commit()
    db.refresh(convo)
    return convo

def get_or_create_dm_conversation(db: Session, a: User, b: User) -> Conversation:
    """
    Deterministic key so A↔B always maps to the same DM conversation,
    and we never collide with System or other named convos.
    """
    key = f"dm:{min(a.id, b.id)}:{max(a.id, b.id)}"
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    convo = Conversation(name=key)
    db.add(convo)
    db.flush()

    db.add(ConversationUser(user_id=a.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=b.id, conversation_id=convo.id))

    db.commit()
    db.refresh(convo)
    return convo

def get_or_create_idea_conversation(db: Session, idea_id: int) -> Conversation:
    """
    One conversation per idea, named 'idea:{idea_id}'.
    We don't attach participants on creation; we add people when they send or 'follow'.
    """
    key = f"idea:{idea_id}"
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if convo:
        return convo

    convo = Conversation(name=key)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo

def get_or_create_user_by_email_or_create(db: Session, email: str, username: Optional[str] = None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(email=email, username=username or (email.split("@")[0] if "@" in email else email))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_or_create_feedback_conversation(db: Session, system_user: User, admin_user: User) -> Conversation:
    # Try to find an existing "feedback" conversation that includes the admin
    convo = (
        db.query(Conversation)
        .join(ConversationUser)
        .filter(Conversation.name == "feedback", ConversationUser.user_id == admin_user.id)
        .first()
    )
    if convo:
        # Ensure system is in it
        has_sys = (
            db.query(ConversationUser)
            .filter(ConversationUser.conversation_id == convo.id, ConversationUser.user_id == system_user.id)
            .first()
        )
        if not has_sys:
            db.add(ConversationUser(user_id=system_user.id, conversation_id=convo.id))
            db.commit()
        return convo

    # Create fresh
    convo = Conversation(name="feedback")
    db.add(convo)
    db.flush()  # ensure convo.id

    db.add(ConversationUser(user_id=admin_user.id, conversation_id=convo.id))
    db.add(ConversationUser(user_id=system_user.id, conversation_id=convo.id))
    db.commit()
    db.refresh(convo)
    return convo

def resolve_conversation_title(db: Session, convo: Conversation) -> str:
    name = (convo.name or "").strip()

    if name.startswith("system:"):
        return "System"

    if name.startswith("dm:"):
        return "Direct Message"

    if name.startswith("idea:"):
        try:
            idea_id = int(name.split(":", 1)[1])
        except Exception:
            return "Idea"
        return get_idea_title(db, idea_id) or f"Idea #{idea_id}"

    if name.startswith("problem:"):
        try:
            pid = int(name.split(":", 1)[1])
        except Exception:
            return "Problem"
        return get_problem_title(db, pid) or f"Problem #{pid}"

    if name.startswith("solution:"):
        try:
            sid = int(name.split(":", 1)[1])
        except Exception:
            return "Solution"
        return get_solution_title(db, sid) or f"Solution #{sid}"

    return f"Conversation #{convo.id}"

def get_problem_title(db: Session, problem_id: int) -> str:
    row = db.query(Problem).filter(Problem.id == problem_id).first()
    return (row.title or f"Problem #{problem_id}") if row else f"Problem #{problem_id}"

def get_solution_title(db: Session, solution_id: int) -> str:
    row = db.query(Solution).filter(Solution.id == solution_id).first()
    return (row.title or f"Solution #{solution_id}") if row else f"Solution #{solution_id}"

def get_or_create_problem_conversation(db: Session, problem_id: int) -> Conversation:
    """Use Problem.conversation_id if set; else create/attach a 'problem:{id}' conversation."""
    prob = db.query(Problem).filter(Problem.id == problem_id).first()
    if not prob:
        raise HTTPException(status_code=404, detail="Problem not found")

    # Already linked?
    if prob.conversation_id:
        convo = db.query(Conversation).filter(Conversation.id == prob.conversation_id).first()
        if convo:
            return convo

    # Try by deterministic name
    key = f"problem:{problem_id}"
    convo = db.query(Conversation).filter(Conversation.name == key).first()
    if not convo:
        convo = Conversation(name=key)
        db.add(convo)
        db.flush()  # get id

    # Attach to problem and persist
    if prob.conversation_id != convo.id:
        prob.conversation_id = convo.id
    db.commit()
    db.refresh(convo)
    return convo

# ========= Routes =========

@router.post("/inbox/send")
def send_to_system(data: SendMessageIn, db: Session = Depends(get_db)):
    """
    Send a message into the caller's System conversation (auto-creates on first use).
    """
    sender = get_user_by_email(db, data.sender_email)
    system_user = get_or_create_system_user(db)

    convo = get_or_create_system_conversation_for_user(db, sender, system_user)

    msg = InboxMessage(
        user_id=sender.id,
        content=data.content,
        timestamp=datetime.utcnow(),
        conversation_id=convo.id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {"status": "ok", "conversation_id": convo.id, "message_id": msg.id}

@router.get("/inbox/{user_email}")
def get_inbox(user_email: str, db: Session = Depends(get_db)):
    """
    Return ONLY the System conversation for the given user.
    """
    user = get_user_by_email(db, user_email)
    system_user = get_or_create_system_user(db)
    convo = get_or_create_system_conversation_for_user(db, user, system_user)

    # Safety: backfill welcome if somehow empty
    has_any = (
        db.query(InboxMessage.id)
        .filter(InboxMessage.conversation_id == convo.id)
        .first()
    )
    if not has_any:
        db.add(
            InboxMessage(
                user_id=system_user.id,
                content="Welcome to your inbox! This is a system-generated message.",
                timestamp=datetime.utcnow(),
                conversation_id=convo.id,
            )
        )
        db.commit()

    messages = (
        db.query(InboxMessage)
        .filter(InboxMessage.conversation_id == convo.id)
        .order_by(InboxMessage.timestamp.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_system": (m.user_id == system_user.id),
        }
        for m in messages
    ]

@router.get("/inbox/feed/{user_email}")
def get_inbox_feed(user_email: str, db: Session = Depends(get_db)):
    """
    Return a unified feed: System + all DMs for the user.
    Bootstraps the System convo (and welcome) if missing.
    """
    user = get_user_by_email(db, user_email)
    system_user = get_or_create_system_user(db)

    # Ensure System convo exists (and seeded)
    convo = get_or_create_system_conversation_for_user(db, user, system_user)

    # Safety: backfill welcome if somehow empty
    has_any = (
        db.query(InboxMessage.id)
        .filter(InboxMessage.conversation_id == convo.id)
        .first()
    )
    if not has_any:
        db.add(
            InboxMessage(
                user_id=system_user.id,
                content="Welcome to your inbox! This is a system-generated message.",
                timestamp=datetime.utcnow(),
                conversation_id=convo.id,
            )
        )
        db.commit()

    # Collect all conversation IDs the user participates in
    convo_ids = [
        row[0]
        for row in db.query(ConversationUser.conversation_id)
                     .filter(ConversationUser.user_id == user.id)
                     .all()
    ]
    if not convo_ids:
        return []

    msgs = (
        db.query(InboxMessage)
        .filter(InboxMessage.conversation_id.in_(convo_ids))
        .order_by(InboxMessage.timestamp.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "conversation_name": m.conversation.name if getattr(m, "conversation", None) else None,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_system": (m.user_id == system_user.id),
            "from_email": m.user.email if getattr(m, "user", None) else None,
        }
        for m in msgs
    ]

@router.post("/inbox/read/{message_id}")
def mark_read(message_id: int, db: Session = Depends(get_db)):
    msg = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.read:
        return {"status": "ok", "message": "already_read"}
    msg.read = True
    db.commit()
    return {"status": "ok", "message": "updated"}

@router.post("/conversations/dm/send")
def send_dm(payload: DMSendIn, db: Session = Depends(get_db)):
    """
    Send a direct message between two users. Creates or reuses the DM conversation.
    """
    sender = get_user_by_email(db, payload.sender_email)
    recipient = get_user_by_email(db, payload.recipient_email)

    convo = get_or_create_dm_conversation(db, sender, recipient)

    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=convo.id,
        content=payload.content,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {"status": "ok", "conversation_id": convo.id, "message_id": msg.id}

@router.get("/conversations/summaries/{user_email}")
def conversation_summaries(user_email: str, db: Session = Depends(get_db)):
    me = db.query(User).filter(User.email == user_email).first()
    if not me:
        raise HTTPException(status_code=404, detail=f"User {user_email} not found")

    convo_ids = [
        cid for (cid,) in db.query(ConversationUser.conversation_id)
                            .filter(ConversationUser.user_id == me.id)
                            .all()
    ]
    if not convo_ids:
        return []

    sub_last = (
        db.query(
            InboxMessage.conversation_id,
            func.max(InboxMessage.timestamp).label("last_ts"),
        )
        .filter(InboxMessage.conversation_id.in_(convo_ids))
        .group_by(InboxMessage.conversation_id)
        .subquery()
    )

    last_msgs = (
        db.query(InboxMessage)
          .options(
              selectinload(InboxMessage.conversation)
                  .selectinload(Conversation.conversation_users)
                  .selectinload(ConversationUser.user),
              selectinload(InboxMessage.user),
          )
          .join(
              sub_last,
              (InboxMessage.conversation_id == sub_last.c.conversation_id)
              & (InboxMessage.timestamp == sub_last.c.last_ts),
          )
          .all()
    )

    unread_map = {
        cid: cnt
        for cid, cnt in (
            db.query(InboxMessage.conversation_id, func.count(InboxMessage.id))
              .filter(
                  InboxMessage.conversation_id.in_(convo_ids),
                  InboxMessage.read == False,  # noqa: E712
              )
              .group_by(InboxMessage.conversation_id)
              .all()
        )
    }

    # ----- helpers -----
    ID_ANYWHERE = re.compile(r"(?P<id>\d+)")

    def unslug(s: str) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        s = s.replace("_", "-")
        s = re.sub(r"[-\s]+", " ", s).strip()
        return s.title()

    def parse_kind_id_slug(name: str):
        if not name:
            return None, None, ""
        base = name.strip()
        low = base.lower()

        kind = None
        for k in ("idea", "forge", "problem", "solution", "system", "dm"):
            if low.startswith(k):
                kind = k
                break

        rest = low[len(kind):] if kind else low
        mid = ID_ANYWHERE.search(rest)
        parsed_id = int(mid.group("id")) if mid else None

        # slug guess
        if ":" in base:
            after = base.split(":", 1)[1]
        else:
            after = base[len(kind):] if kind else base
        after = re.sub(r"^\s*\d+[:\-_\s]*", "", after).strip()
        return kind, parsed_id, after

    def title_for_item_or_legacy(thing_id: Optional[int], slug: str,
                                 convo_created_at: Optional[datetime],
                                 last_ts: Optional[datetime]) -> str:
        """
        Prefer ForgeItem; but if both ForgeItem and legacy ForgeIdea exist with same id,
        choose the one whose created_at is closer to the conversation creation (or last message) time.
        """
        ref_time = convo_created_at or last_ts

        if thing_id is not None:
            item = db.query(ForgeItem).filter(ForgeItem.id == thing_id).first()
            legacy = db.query(IdeaModel).filter(IdeaModel.id == thing_id).first()

            # Only one exists → use it
            if item and not legacy:
                return item.title or f"Idea #{thing_id}"
            if legacy and not item:
                return legacy.title or f"Idea #{thing_id}"

            # Both exist → pick by proximity to ref_time
            if item and legacy:
                if ref_time:
                    item_dt = getattr(item, "created_at", None)
                    legacy_dt = getattr(legacy, "created_at", None)
                    # default far past if missing timestamps, so we don't falsely prefer one
                    far = datetime(1970, 1, 1)
                    item_dt = item_dt or far
                    legacy_dt = legacy_dt or far
                    if abs(item_dt - ref_time) <= abs(legacy_dt - ref_time):
                        return item.title or f"Idea #{thing_id}"
                    else:
                        return legacy.title or f"Idea #{thing_id}"
                # No ref_time → prefer older (assume older = legacy)
                return (legacy.title or f"Idea #{thing_id}")

            # Neither exists → fall back to slug or “Idea #id”
            return unslug(slug) or f"Idea #{thing_id}"

        # No id → slug or generic
        return unslug(slug) or "Idea"

    def title_for_problem(pid: Optional[int], slug: str) -> str:
        if pid is not None:
            row = db.query(Problem).filter(Problem.id == pid).first()
            return (row.title if row and row.title else f"Problem #{pid}")
        return unslug(slug) or "Problem"

    def title_for_solution(sid: Optional[int], slug: str) -> str:
        if sid is not None:
            row = db.query(Solution).filter(Solution.id == sid).first()
            return (row.title if row and row.title else f"Solution #{sid}")
        return unslug(slug) or "Solution"

    out = []
    for m in last_msgs:
        convo = m.conversation
        cname = (convo.name or "").strip() if convo else ""

        other_email = None
        other_username = None

        idea_id = None
        idea_title = None
        title = None

        problem_id = None
        problem_title = None
        solution_id = None
        solution_title = None

        if cname:
            kind, parsed_id, slug = parse_kind_id_slug(cname)

            if kind == "dm":
                for cu in convo.conversation_users:
                    if cu.user and cu.user.email != user_email:
                        other_email = cu.user.email
                        other_username = cu.user.username
                        break
                title = other_username or other_email or "Direct Message"

            elif kind == "system":
                title = "System"

            elif kind in ("idea", "forge"):
                idea_id = parsed_id
                idea_title = title_for_item_or_legacy(
                    parsed_id, slug,
                    getattr(convo, "created_at", None),
                    m.timestamp
                )
                title = idea_title

            elif kind == "problem":
                problem_id = parsed_id
                problem_title = title_for_problem(parsed_id, slug)
                title = title_for_problem(parsed_id, slug)

            elif kind == "solution":
                solution_id = parsed_id
                solution_title = title_for_solution(parsed_id, slug)
                title = solution_title

            elif cname.isdigit():
                parsed_id = int(cname)
                idea_id = parsed_id
                idea_title = title_for_item_or_legacy(
                    parsed_id, "",
                    getattr(convo, "created_at", None),
                    m.timestamp
                )
                title = idea_title

        if not title:
            title = f"Conversation #{m.conversation_id}"

        out.append({
            "conversation_id": m.conversation_id,
            "conversation_name": cname,
            "title": title,
            "last_content": m.content,
            "last_timestamp": m.timestamp,
            "unread_count": unread_map.get(m.conversation_id, 0),

            "other_email": other_email,
            "other_username": other_username,

            "idea_id": idea_id,
            "idea_title": idea_title,
            "problem_id": problem_id,
            "problem_title": problem_title,
            "solution_id": solution_id,
            "solution_title": solution_title,
        })

    out.sort(key=lambda x: x["last_timestamp"] or datetime.min, reverse=True)
    return out

@router.get("/conversations/dm/thread")
def get_dm_thread(
    me: str, them: str, limit: int = 50, before: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    a = get_user_by_email(db, me)
    b = get_user_by_email(db, them)
    convo = get_or_create_dm_conversation(db, a, b)

    q = db.query(InboxMessage).filter(InboxMessage.conversation_id == convo.id)
    if before:
        q = q.filter(InboxMessage.timestamp < before)
    msgs = q.order_by(InboxMessage.timestamp.desc()).limit(limit).all()
    msgs.reverse()

    return {
        "conversation_id": convo.id,
        "messages": [{
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_email": m.user.email if m.user else None,
        } for m in msgs]
    }

@router.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    msgs = (
        db.query(InboxMessage)
          .options(selectinload(InboxMessage.user))
          .filter(InboxMessage.conversation_id == conversation_id)
          .order_by(InboxMessage.timestamp.asc())
          .all()
    )
    out = []
    for m in msgs:
        from_email = m.user.email if m.user else None
        from_username = m.user.username if m.user else None
        if m.user_id == system_user.id:
            from_display = "System"
        else:
            from_display = from_username or from_email or "User"
        out.append({
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_email": from_email,
            "from_username": from_username,
            "from_display": from_display,
        })
    return out

# ---- Request schema ----
class ConversationSendIn(BaseModel):
    sender_email: str
    content: str

@router.post("/conversations/{conversation_id}/send")
def send_to_conversation(conversation_id: int, data: ConversationSendIn, db: Session = Depends(get_db)):
    sender = get_user_by_email(db, data.sender_email)

    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Ensure sender participates in this conversation
    is_member = (
        db.query(ConversationUser)
        .filter(
            ConversationUser.conversation_id == conversation_id,
            ConversationUser.user_id == sender.id,
        )
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    # Create message
    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=conversation_id,
        content=data.content,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Build a UI-friendly payload (matches /conversations/{id}/messages shape)
    from_email = sender.email
    from_username = sender.username
    from_display = from_username or from_email or "User"

    return {
        "status": "ok",
        "message": {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "read": msg.read,
            "from_email": from_email,
            "from_username": from_username,
            "from_display": from_display,
        },
    }

class LeaveIn(BaseModel):
    user_email: str

@router.post("/conversations/{conversation_id}/leave")
def leave_conversation(conversation_id: int, payload: LeaveIn, db: Session = Depends(get_db)):
    user = get_user_by_email(db, (payload.user_email or "").strip().lower())
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Don’t allow leaving your System conversation
    if convo.name == f"system:{user.id}":
        raise HTTPException(status_code=400, detail="Cannot leave your System conversation")

    link = (
        db.query(ConversationUser)
        .filter(ConversationUser.conversation_id == conversation_id,
                ConversationUser.user_id == user.id)
        .first()
    )
    if not link:
        return {"status": "ok", "message": "not_member"}

    db.delete(link)
    db.commit()

    # If no participants remain, clean up the convo + messages
    still_has_members = (
        db.query(ConversationUser.id)
        .filter(ConversationUser.conversation_id == conversation_id)
        .first()
    )
    if not still_has_members:
        db.query(InboxMessage).filter(InboxMessage.conversation_id == conversation_id).delete()
        db.query(Conversation).filter(Conversation.id == conversation_id).delete()
        db.commit()
        return {"status": "ok", "message": "left_and_deleted"}

    return {"status": "ok", "message": "left"}

@router.get("/conversations/{conversation_id}")
def get_conversation_meta(conversation_id: int, db: Session = Depends(get_db)):
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": convo.id,
        "name": convo.name,
        "title": resolve_conversation_title(db, convo),
    }

@router.delete("/conversations/{conversation_id}")
def admin_delete_conversation(conversation_id: int, user_email: str, db: Session = Depends(get_db)):
    admin = get_user_by_email(db, (user_email or "").strip().lower())
    if admin.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Not authorized")

    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Be conservative: don’t let admin delete other users’ System threads
    if (convo.name or "").startswith("system:") and convo.name != f"system:{admin.id}":
        raise HTTPException(status_code=400, detail="Refusing to delete another user's System conversation")

    db.query(InboxMessage).filter(InboxMessage.conversation_id == conversation_id).delete()
    db.query(ConversationUser).filter(ConversationUser.conversation_id == conversation_id).delete()
    db.query(Conversation).filter(Conversation.id == conversation_id).delete()
    db.commit()
    return {"status": "ok", "message": "deleted"}

@router.get("/ideas/{idea_id}/conversation")
def get_idea_conversation(idea_id: int, db: Session = Depends(get_db)):
    convo = get_or_create_idea_conversation(db, idea_id)
    return {
        "conversation_id": convo.id,
        "conversation_name": convo.name,                 # e.g., "idea:6"
        "conversation_title": get_idea_title(db, idea_id)  # human-friendly title
    }


@router.get("/ideas/{idea_id}/conversation/messages")
def get_idea_conversation_messages(idea_id: int, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    convo = get_or_create_idea_conversation(db, idea_id)

    msgs = (
        db.query(InboxMessage)
        .options(selectinload(InboxMessage.user))
        .filter(InboxMessage.conversation_id == convo.id)
        .order_by(InboxMessage.timestamp.asc())
        .all()
    )

    def safe_display(m):
        if m.user_id == system_user.id:
            return "System"
        if m.user and getattr(m.user, "username", None):
            return m.user.username
        if m.user_id:
            return f"User {m.user_id}"
        return "User"

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_username": (m.user.username if m.user else None),
            "from_user_id": m.user_id,
            "from_system": (m.user_id == system_user.id),
            "from_display": safe_display(m),   # ← never email
        }
        for m in msgs
    ]


@router.post("/ideas/{idea_id}/conversation/send")
def send_to_idea_conversation(
    idea_id: int,
    payload: IdeaSendIn,
    db: Session = Depends(get_db),
):
    """
    Send a message into the idea conversation.
    Automatically enrolls the sender as a participant so it appears in their feed.
    """
    sender = get_user_by_email(db, (payload.sender_email or "").strip().lower())
    if not sender:
        raise HTTPException(status_code=401, detail="User not found")

    convo = get_or_create_idea_conversation(db, idea_id)

    # Ensure membership so convo shows in sender's feed
    link = (
        db.query(ConversationUser)
        .filter(
            ConversationUser.conversation_id == convo.id,
            ConversationUser.user_id == sender.id,
        )
        .first()
    )
    if not link:
        db.add(ConversationUser(user_id=sender.id, conversation_id=convo.id))

    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=convo.id,
        content=(payload.content or "").strip(),
        timestamp=datetime.utcnow(),
    )
    if not msg.content:
        raise HTTPException(status_code=400, detail="Empty message")

    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Build a privacy-safe display (never email)
    display = sender.username if sender.username else f"User {msg.user_id}"

    return {
        "status": "ok",
        "conversation_id": convo.id,
        "message": {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "read": msg.read,
            "from_user_id": msg.user_id,
            "from_username": sender.username if sender.username else None,
            "from_display": display,   # ← username or "User <id>", never email
        },
    }


@router.post("/ideas/{idea_id}/conversation/join")
def join_idea_conversation(idea_id: int, user_email: str, db: Session = Depends(get_db)):
    """
    Optional: let users follow an idea thread without sending a message yet.
    """
    user = get_user_by_email(db, user_email)
    convo = get_or_create_idea_conversation(db, idea_id)

    exists = (
        db.query(ConversationUser)
        .filter(ConversationUser.conversation_id == convo.id, ConversationUser.user_id == user.id)
        .first()
    )
    if exists:
        return {"status": "ok", "message": "already_member", "conversation_id": convo.id}

    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.commit()
    return {"status": "ok", "message": "joined", "conversation_id": convo.id}

@router.get("/ideas/{idea_id}/conversation/following")
def is_following_idea_conversation(idea_id: int, user_email: str, db: Session = Depends(get_db)):
    """
    Return whether the user is a participant of the idea conversation.
    """
    user = get_user_by_email(db, user_email)
    convo = get_or_create_idea_conversation(db, idea_id)
    exists = (
        db.query(ConversationUser.id)
        .filter(
            ConversationUser.conversation_id == convo.id,
            ConversationUser.user_id == user.id,
        )
        .first()
    )
    return {"conversation_id": convo.id, "following": bool(exists)}


@router.post("/ideas/{idea_id}/conversation/unfollow")
def unfollow_idea_conversation(idea_id: int, user_email: str, db: Session = Depends(get_db)):
    """
    Remove the user from the idea conversation participants (their feed won't show it).
    """
    user = get_user_by_email(db, user_email)
    convo = get_or_create_idea_conversation(db, idea_id)
    link = (
        db.query(ConversationUser)
        .filter(
            ConversationUser.conversation_id == convo.id,
            ConversationUser.user_id == user.id,
        )
        .first()
    )
    if not link:
        return {"status": "ok", "message": "not_following", "conversation_id": convo.id}

    db.delete(link)
    db.commit()
    return {"status": "ok", "message": "unfollowed", "conversation_id": convo.id}

@router.post("/feedback")
def receive_feedback(payload: FeedbackIn, request: Request, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    admin_user = get_or_create_user_by_email_or_create(db, ADMIN_EMAIL, username="Admin")

    convo = get_or_create_feedback_conversation(db, system_user, admin_user)

    # Format a readable message
    lines = [
        "📝 New Contribution",
        f"• Contact: {payload.contact or '—'}",
        f"• Interests: {', '.join(payload.interests) if payload.interests else '—'}",
        "",
        f"💡 Idea:\n{payload.idea or '—'}",
        "",
        f"🐞 Bugs:\n{payload.bugs or '—'}",
        "",
        f"🧰 Skills:\n{payload.skills or '—'}",
        "",
        f"➕ Extra:\n{payload.extra or '—'}",
    ]
    content = "\n".join(lines)

    msg = InboxMessage(
        user_id=system_user.id,            # message appears from System
        content=content,
        timestamp=datetime.utcnow(),
        conversation_id=convo.id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {"status": "ok", "message_id": msg.id, "conversation_id": convo.id}

@router.get("/forge/problems/{problem_id}/conversation")
def get_problem_conversation(problem_id: int, db: Session = Depends(get_db)):
    convo = get_or_create_problem_conversation(db, problem_id)
    return {
        "conversation_id": convo.id,
        "conversation_name": convo.name,
        "conversation_title": get_problem_title(db, problem_id),
    }

@router.get("/forge/problems/{problem_id}/conversation/messages")
def get_problem_conversation_messages(problem_id: int, db: Session = Depends(get_db)):
    system_user = get_or_create_system_user(db)
    convo = get_or_create_problem_conversation(db, problem_id)

    msgs = (
        db.query(InboxMessage)
          .options(selectinload(InboxMessage.user))
          .filter(InboxMessage.conversation_id == convo.id)
          .order_by(InboxMessage.timestamp.asc())
          .all()
    )

    def safe_display(m):
        if m.user_id == system_user.id:
            return "System"
        if m.user and getattr(m.user, "username", None):
            return m.user.username
        if m.user_id:
            return f"User {m.user_id}"
        return "User"

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "from_username": (m.user.username if m.user else None),
            "from_user_id": m.user_id,
            "from_system": (m.user_id == system_user.id),
            "from_display": safe_display(m),
        }
        for m in msgs
    ]

class ProblemSendIn(BaseModel):
    sender_email: str
    content: str

@router.post("/forge/problems/{problem_id}/conversation/send")
def send_to_problem_conversation(
    problem_id: int,
    payload: ProblemSendIn,
    db: Session = Depends(get_db),
):
    sender = get_user_by_email(db, (payload.sender_email or "").strip().lower())
    if not sender:
        raise HTTPException(status_code=401, detail="User not found")

    convo = get_or_create_problem_conversation(db, problem_id)

    # Ensure membership so it shows in the sender's feed
    link = (
        db.query(ConversationUser)
          .filter(ConversationUser.conversation_id == convo.id,
                  ConversationUser.user_id == sender.id)
          .first()
    )
    if not link:
        db.add(ConversationUser(user_id=sender.id, conversation_id=convo.id))

    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty message")

    msg = InboxMessage(
        user_id=sender.id,
        conversation_id=convo.id,
        content=content,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    display = sender.username if sender.username else f"User {msg.user_id}"

    return {
        "status": "ok",
        "conversation_id": convo.id,
        "message": {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "read": msg.read,
            "from_user_id": msg.user_id,
            "from_username": sender.username if sender.username else None,
            "from_display": display,
        },
    }

@router.post("/forge/problems/{problem_id}/conversation/join")
def join_problem_conversation(problem_id: int, user_email: str, db: Session = Depends(get_db)):
    user = get_user_by_email(db, user_email)
    convo = get_or_create_problem_conversation(db, problem_id)

    exists = (
        db.query(ConversationUser)
          .filter(ConversationUser.conversation_id == convo.id,
                  ConversationUser.user_id == user.id)
          .first()
    )
    if exists:
        return {"status": "ok", "message": "already_member", "conversation_id": convo.id}

    db.add(ConversationUser(user_id=user.id, conversation_id=convo.id))
    db.commit()
    return {"status": "ok", "message": "joined", "conversation_id": convo.id}

@router.get("/forge/problems/{problem_id}/conversation/following")
def is_following_problem_conversation(problem_id: int, user_email: str, db: Session = Depends(get_db)):
    user = get_user_by_email(db, user_email)
    convo = get_or_create_problem_conversation(db, problem_id)
    exists = (
        db.query(ConversationUser.id)
          .filter(ConversationUser.conversation_id == convo.id,
                  ConversationUser.user_id == user.id)
          .first()
    )
    return {"conversation_id": convo.id, "following": bool(exists)}

@router.post("/forge/problems/{problem_id}/conversation/unfollow")
def unfollow_problem_conversation(problem_id: int, user_email: str, db: Session = Depends(get_db)):
    user = get_user_by_email(db, user_email)
    convo = get_or_create_problem_conversation(db, problem_id)
    link = (
        db.query(ConversationUser)
          .filter(ConversationUser.conversation_id == convo.id,
                  ConversationUser.user_id == user.id)
          .first()
    )
    if not link:
        return {"status": "ok", "message": "not_following", "conversation_id": convo.id}

    db.delete(link)
    db.commit()
    return {"status": "ok", "message": "unfollowed", "conversation_id": convo.id}