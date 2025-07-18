# crud/farmgame.py
from sqlalchemy.orm import Session
from models import FarmGameState
from schemas import FarmGameStateCreate

def get_game_state_by_user(db: Session, user_id: int):
    return db.query(FarmGameState).filter(FarmGameState.user_id == user_id).first()

def create_or_update_game_state(db: Session, user_id: int, state: FarmGameStateCreate):
    existing = get_game_state_by_user(db, user_id)
    if existing:
        existing.data = state.data  # ✅ changed from state.state_json
    else:
        existing = FarmGameState(user_id=user_id, data=state.data)  # ✅ changed from state.state_json
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing