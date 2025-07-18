# routers/farmgame.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import get_current_user_dependency
from crud.farmgame import farmgame as crud
from schemas import FarmGameStateCreate, FarmGameStateResponse

router = APIRouter()

@router.get("/farmgame/state", response_model=FarmGameStateResponse)
def get_game_state(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_dependency)):
    state = crud.get_game_state_by_user(db, user_id.id)
    if not state:
        raise HTTPException(status_code=404, detail="No saved game state found.")
    return state

@router.post("/farmgame/state", response_model=FarmGameStateResponse)
def save_game_state(state: FarmGameStateCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_dependency)):
    return crud.create_or_update_game_state(db, user_id.id, state)