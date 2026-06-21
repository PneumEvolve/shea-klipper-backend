"""
HabitGrid routes. Save as routers/habits.py (or wherever auth.py lives) and
include with: app.include_router(habits.router, prefix="/habits", tags=["habits"])

Every route is scoped to current_user via get_current_user_model, same as
your existing /account routes. Client-generated ids (client_id) are how the
React component refers to records before/after sync — the int `id` columns
never leave the server.
"""

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import (
    Habit, HabitColor, HabitMark, Goal, GoalStage, HabitGoalLink, User,
)
from schemas import (
    HabitColorIn, HabitColorUpdate, HabitColorOut,
    HabitIn, HabitUpdate, HabitOut,
    HabitMarkUpsert, HabitMarkOut,
    GoalIn, GoalUpdate, GoalOut,
    GoalStageIn, GoalStageUpdate, GoalStageOut,
    HabitGoalLinkIn,
    HabitGridState,
)
from sqlalchemy.orm import Session
from typing import List
from routers.auth import get_current_user_model  # adjust import path to wherever this actually lives

router = APIRouter()


# ---------- helpers ----------

def _get_habit_or_404(db: Session, user: User, client_id: str) -> Habit:
    h = db.query(Habit).filter(Habit.user_id == user.id, Habit.client_id == client_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found")
    return h


def _get_goal_or_404(db: Session, user: User, client_id: str) -> Goal:
    g = db.query(Goal).filter(Goal.user_id == user.id, Goal.client_id == client_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Goal not found")
    return g


def _get_stage_or_404(db: Session, goal: Goal, client_id: str) -> GoalStage:
    s = db.query(GoalStage).filter(GoalStage.goal_id == goal.id, GoalStage.client_id == client_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Stage not found")
    return s


# ---------- bulk state (initial load) ----------

@router.get("/state", response_model=HabitGridState)
def get_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    colors = db.query(HabitColor).filter(HabitColor.user_id == current_user.id).order_by(HabitColor.order_index).all()
    habits = db.query(Habit).filter(Habit.user_id == current_user.id, Habit.archived == False).order_by(Habit.order_index).all()  # noqa: E712
    marks = (
        db.query(HabitMark)
        .join(Habit, Habit.id == HabitMark.habit_id)
        .filter(Habit.user_id == current_user.id)
        .all()
    )
    goals = db.query(Goal).filter(Goal.user_id == current_user.id).all()
    links = (
        db.query(HabitGoalLink)
        .join(Habit, Habit.id == HabitGoalLink.habit_id)
        .filter(Habit.user_id == current_user.id)
        .all()
    )

    habit_by_id = {h.id: h for h in habits + db.query(Habit).filter(Habit.user_id == current_user.id).all()}
    goal_by_id = {g.id: g for g in goals}

    return HabitGridState(
        colors=[HabitColorOut.model_validate(c) for c in colors],
        habits=[HabitOut.model_validate(h) for h in habits],
        marks=[
            HabitMarkOut(
                habit_client_id=habit_by_id[m.habit_id].client_id,
                date=m.date,
                color_client_id=m.color_client_id,
            )
            for m in marks if m.habit_id in habit_by_id
        ],
        goals=[GoalOut.model_validate(g) for g in goals],
        habit_goals=[
            HabitGoalLinkIn(
                habit_client_id=habit_by_id[link.habit_id].client_id,
                goal_client_id=goal_by_id[link.goal_id].client_id,
            )
            for link in links if link.habit_id in habit_by_id and link.goal_id in goal_by_id
        ],
    )


# ---------- colors ----------

@router.post("/colors", response_model=HabitColorOut)
def create_color(
    payload: HabitColorIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    existing = db.query(HabitColor).filter(
        HabitColor.user_id == current_user.id, HabitColor.client_id == payload.client_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Color with this client_id already exists")
    color = HabitColor(user_id=current_user.id, **payload.dict())
    db.add(color)
    db.commit()
    db.refresh(color)
    return color


@router.patch("/colors/{client_id}", response_model=HabitColorOut)
def update_color(
    client_id: str,
    payload: HabitColorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    color = db.query(HabitColor).filter(
        HabitColor.user_id == current_user.id, HabitColor.client_id == client_id
    ).first()
    if not color:
        raise HTTPException(status_code=404, detail="Color not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(color, field, value)
    db.commit()
    db.refresh(color)
    return color


@router.delete("/colors/{client_id}")
def delete_color(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    color = db.query(HabitColor).filter(
        HabitColor.user_id == current_user.id, HabitColor.client_id == client_id
    ).first()
    if not color:
        raise HTTPException(status_code=404, detail="Color not found")
    db.delete(color)
    db.commit()
    return {"ok": True}


# ---------- habits ----------

@router.post("", response_model=HabitOut)
def create_habit(
    payload: HabitIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    existing = db.query(Habit).filter(
        Habit.user_id == current_user.id, Habit.client_id == payload.client_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Habit with this client_id already exists")
    habit = Habit(user_id=current_user.id, **payload.dict())
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


@router.patch("/{client_id}", response_model=HabitOut)
def update_habit(
    client_id: str,
    payload: HabitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    habit = _get_habit_or_404(db, current_user, client_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(habit, field, value)
    db.commit()
    db.refresh(habit)
    return habit


@router.delete("/{client_id}")
def delete_habit(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    habit = _get_habit_or_404(db, current_user, client_id)
    db.delete(habit)  # cascades to marks + habit_goal_links
    db.commit()
    return {"ok": True}


# ---------- marks ----------

@router.put("/marks", response_model=HabitMarkOut)
def upsert_mark(
    payload: HabitMarkUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    habit = _get_habit_or_404(db, current_user, payload.habit_client_id)

    mark = db.query(HabitMark).filter(
        HabitMark.habit_id == habit.id, HabitMark.date == payload.date
    ).first()

    if payload.color_client_id is None:
        # clearing a mark
        if mark:
            db.delete(mark)
            db.commit()
        return HabitMarkOut(habit_client_id=habit.client_id, date=payload.date, color_client_id="")

    if mark:
        mark.color_client_id = payload.color_client_id
    else:
        mark = HabitMark(
            user_id=current_user.id,
            habit_id=habit.id,
            date=payload.date,
            color_client_id=payload.color_client_id,
        )
        db.add(mark)
    db.commit()
    db.refresh(mark)
    return HabitMarkOut(habit_client_id=habit.client_id, date=mark.date, color_client_id=mark.color_client_id)


# ---------- goals ----------

@router.post("/goals", response_model=GoalOut)
def create_goal(
    payload: GoalIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    existing = db.query(Goal).filter(
        Goal.user_id == current_user.id, Goal.client_id == payload.client_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Goal with this client_id already exists")
    goal = Goal(user_id=current_user.id, advance_mode="manual", **payload.dict())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/goals/{client_id}", response_model=GoalOut)
def update_goal(
    client_id: str,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    goal = _get_goal_or_404(db, current_user, client_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/goals/{client_id}")
def delete_goal(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    goal = _get_goal_or_404(db, current_user, client_id)
    db.delete(goal)  # cascades to stages + habit_goal_links
    db.commit()
    return {"ok": True}


# ---------- goal stages ----------

@router.post("/goals/{goal_client_id}/stages", response_model=GoalStageOut)
def add_stage(
    goal_client_id: str,
    payload: GoalStageIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    goal = _get_goal_or_404(db, current_user, goal_client_id)
    existing = db.query(GoalStage).filter(
        GoalStage.goal_id == goal.id, GoalStage.client_id == payload.client_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Stage with this client_id already exists")
    stage = GoalStage(goal_id=goal.id, **payload.dict())
    db.add(stage)
    db.flush()
    # first stage on a manual goal becomes the active one, matching addStage() in HabitGrid.jsx
    if goal.advance_mode == "manual" and not goal.current_stage_client_id:
        goal.current_stage_client_id = stage.client_id
    db.commit()
    db.refresh(stage)
    return stage


@router.patch("/goals/{goal_client_id}/stages/{stage_client_id}", response_model=GoalStageOut)
def update_stage(
    goal_client_id: str,
    stage_client_id: str,
    payload: GoalStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    goal = _get_goal_or_404(db, current_user, goal_client_id)
    stage = _get_stage_or_404(db, goal, stage_client_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(stage, field, value)
    db.commit()
    db.refresh(stage)
    return stage


@router.delete("/goals/{goal_client_id}/stages/{stage_client_id}")
def remove_stage(
    goal_client_id: str,
    stage_client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    goal = _get_goal_or_404(db, current_user, goal_client_id)
    stage = _get_stage_or_404(db, goal, stage_client_id)
    db.delete(stage)
    db.flush()
    if goal.current_stage_client_id == stage_client_id:
        remaining = db.query(GoalStage).filter(GoalStage.goal_id == goal.id).order_by(GoalStage.order_index).first()
        goal.current_stage_client_id = remaining.client_id if remaining else None
    db.commit()
    return {"ok": True}


# ---------- habit <-> goal links ----------

@router.put("/{habit_client_id}/goals/{goal_client_id}")
def link_habit_goal(
    habit_client_id: str,
    goal_client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    habit = _get_habit_or_404(db, current_user, habit_client_id)
    goal = _get_goal_or_404(db, current_user, goal_client_id)
    existing = db.query(HabitGoalLink).filter(
        HabitGoalLink.habit_id == habit.id, HabitGoalLink.goal_id == goal.id
    ).first()
    if not existing:
        db.add(HabitGoalLink(habit_id=habit.id, goal_id=goal.id))
        db.commit()
    return {"ok": True}


@router.delete("/{habit_client_id}/goals/{goal_client_id}")
def unlink_habit_goal(
    habit_client_id: str,
    goal_client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    habit = _get_habit_or_404(db, current_user, habit_client_id)
    goal = _get_goal_or_404(db, current_user, goal_client_id)
    link = db.query(HabitGoalLink).filter(
        HabitGoalLink.habit_id == habit.id, HabitGoalLink.goal_id == goal.id
    ).first()
    if link:
        db.delete(link)
        db.commit()
    return {"ok": True}