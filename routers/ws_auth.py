# routers/ws_auth.py
import logging
from fastapi import WebSocket
from database import SessionLocal
import jwt
import os

logger = logging.getLogger("ws_auth")

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")
ALGORITHM  = "HS256"


async def get_ws_user(websocket: WebSocket) -> dict | None:
    """
    Validate the JWT token from the WebSocket query string.
    Returns a simple dict with 'id' and 'email' on success, None on failure.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return None

    db = SessionLocal()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("id")
        if not uid:
            await websocket.close(code=4001, reason="Invalid token")
            return None

        from models import User
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return None

        return {"id": user.id, "email": user.email}

    except jwt.ExpiredSignatureError:
        logger.warning("[ws_auth] Token expired")
        await websocket.close(code=4001, reason="Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"[ws_auth] Invalid token: {e}")
        await websocket.close(code=4001, reason="Invalid token")
        return None
    except Exception as e:
        logger.warning(f"[ws_auth] Unexpected error: {e}")
        await websocket.close(code=4001, reason="Auth error")
        return None
    finally:
        db.close()