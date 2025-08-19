from fastapi import APIRouter, HTTPException, Depends, Security, Request, Response, UploadFile, File
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import timedelta, datetime
from passlib.context import CryptContext
from database import get_db
from models import User
from pydantic import BaseModel, EmailStr
import requests
import os
from typing import Optional, Tuple, Deque, Dict
from utils.email import send_email
from schemas import UserResponse, UserCreate, ProfilePicUpdate
from models import Category, user_categories, User
from sqlalchemy import text, func
from sqlalchemy.exc import IntegrityError
from database import get_db
from schemas import UsernameUpdate
from jose import JWTError
import time
from collections import deque
from settings import settings as app_settings


router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# failure tracking: key = (ip, email_lower)
_FAILED: Dict[Tuple[str, str], Deque[float]] = {}
_CHALLENGED_UNTIL: Dict[Tuple[str, str], float] = {}

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60
CHALLENGE_SECONDS = 60 * 60

def _now() -> float:
    return time.time()

def get_client_ip(request: Request) -> str:
    # Honor proxy header if present (Render/NGINX)
    xfwd = request.headers.get("x-forwarded-for")
    if xfwd:
        # take first ip
        return xfwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"

def record_failure(ip: str, email: str):
    key = (ip, email.lower())
    q = _FAILED.setdefault(key, deque())
    now = _now()
    q.append(now)
    # drop old
    cutoff = now - WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    # if over limit, start a challenge window
    if len(q) >= MAX_ATTEMPTS:
        _CHALLENGED_UNTIL[key] = now + CHALLENGE_SECONDS

def clear_failures(ip: str, email: str):
    key = (ip, email.lower())
    _FAILED.pop(key, None)
    _CHALLENGED_UNTIL.pop(key, None)

def should_require_captcha(ip: str, email: str) -> bool:
    key = (ip, email.lower())
    until = _CHALLENGED_UNTIL.get(key)
    if not until:
        return False
    if _now() > until:
        # challenge expired
        _CHALLENGED_UNTIL.pop(key, None)
        _FAILED.pop(key, None)
        return False
    return True

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_recaptcha(token: str) -> bool:
    url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {"secret": RECAPTCHA_SECRET, "response": token}
    response = requests.post(url, data=payload)
    result = response.json()
    return result.get("success", False)

def _is_prod_env() -> bool:
    env = str(getattr(app_settings, "ENV", "")).lower()
    return env in ("prod", "production")

def set_http_only_cookie(response: Response, *, key: str, value: str, max_age: int) -> None:
    prod = _is_prod_env()
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=prod,                   # ✅ dev=False (HTTP), prod=True (HTTPS)
        samesite="None" if prod else "Lax",
        path="/",
        max_age=max_age,
    )

def clear_cookie(response: Response, key: str) -> None:
    response.delete_cookie(key, path="/")



@router.post("/signup", response_model=UserResponse)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    email = (user_data.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    if not user_data.password or len(user_data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Skip captcha in dev
    if app_settings.ENV != "dev":
        if not verify_recaptcha(user_data.recaptcha_token):
            raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")

    # ---------- Phase 1: create user (isolated) ----------
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user = User(
            email=email,
            username=email.split("@")[0],
            hashed_password=hash_password(user_data.password),
        )
        db.add(new_user)
        db.commit()      # commit just the user
        db.refresh(new_user)

    except IntegrityError as ie:
        db.rollback()
        msg = str(ie.orig).lower()
        # Only translate if it’s clearly the user email constraint
        if "users" in msg and "email" in msg and "unique" in msg:
            raise HTTPException(status_code=400, detail="Email already registered")
        # Otherwise surface a generic 500 to stop the wild goose chase
        raise HTTPException(status_code=500, detail="Could not create user (DB constraint)")

    # ---------- Phase 2: seed defaults (best effort) ----------
    try:
        default_categories = {
            "food": ["Pantry", "Fridge", "Freezer"],
            "recipe": ["Breakfast", "Lunch", "Dinner"],
        }

        for category_type, names in default_categories.items():
            # get existing
            existing_cats = {
                (c.name, c.type): c
                for c in db.query(Category)
                           .filter(Category.type == category_type, Category.name.in_(names))
                           .all()
            }
            for name in names:
                key = (name, category_type)
                if key not in existing_cats:
                    c = Category(name=name, type=category_type)
                    db.add(c)
                    db.flush()
                    existing_cats[key] = c

                # link (ignore if already present)
                db.execute(
                    text("""
                        INSERT INTO user_categories (user_id, category_id)
                        VALUES (:uid, :cid)
                        ON CONFLICT DO NOTHING
                    """),
                    {"uid": new_user.id, "cid": existing_cats[key].id},
                )
        db.commit()
    except Exception as e:
        # Don’t fail the signup if seeding is noisy
        db.rollback()
        # Log server-side; return success anyway
        print("[signup] category seeding failed:", repr(e))

    return UserResponse(id=new_user.id, email=new_user.email)


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    email = (form_data.username or "").strip().lower()

    # Read form (for optional recaptcha_token)
    form = await request.form()
    recaptcha_token = form.get("recaptcha_token")

    # If this tuple is challenged, require valid CAPTCHA
    if should_require_captcha(ip, email):
        if not recaptcha_token or not verify_recaptcha(recaptcha_token):
            raise HTTPException(status_code=400, detail="reCAPTCHA required (too many recent failures)")

    # Credential check
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        record_failure(ip, email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success — clear failures/challenge
    clear_failures(ip, email)

     # Mint tokens
    access_token = create_access_token({"sub": user.email, "id": user.id})
    refresh_token = create_refresh_token({"sub": user.email, "id": user.id})

    # 🔐 Set cookies (dev-safe / prod-safe)
    set_http_only_cookie(
        response,
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    # Optional but convenient: also set a short-lived access cookie
    set_http_only_cookie(
        response,
        key="access_token",
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {"access_token": access_token, "token_type": "bearer"}

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token found")

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        new_access_token = create_access_token({"sub": user.email, "id": user.id})
        return {"access_token": new_access_token, "token_type": "bearer"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


def get_current_user_dependency(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),   # or Security(oauth2_scheme)
    db: Session = Depends(get_db),
):
    try:
        # Prefer Authorization header; fall back to cookies
        tok = token or request.cookies.get("access_token") or request.cookies.get("refresh_token")
        if not tok:
            raise HTTPException(status_code=401, detail="Not authenticated")

        payload = jwt.decode(tok, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("id")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return UserResponse(id=user.id, email=user.email)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user_model(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),   # or Security(oauth2_scheme)
    db: Session = Depends(get_db),
) -> User:
    try:
        tok = token or request.cookies.get("access_token") or request.cookies.get("refresh_token")
        if not tok:
            raise HTTPException(status_code=401, detail="Not authenticated")

        payload = jwt.decode(tok, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("id")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
def get_current_user_with_db(
    token: str = Security(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Tuple[User, Session]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.query(User).filter(User.id == payload.get("id")).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return user, db
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/user", response_model=UserResponse)
def get_current_user_route(current_user: UserResponse = Depends(get_current_user_dependency)):
    return current_user

class PasswordResetRequest(BaseModel):
    email: EmailStr

@router.post("/request-password-reset")
def request_password_reset(request_data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email")

    reset_token = create_password_reset_token(user.email)
    frontend_url = os.getenv("FRONTEND_URL", "https://sheas-app.netlify.app")
    reset_link = f"{frontend_url}/resetpassword?token={reset_token}"
    send_email(
        to_email=user.email,
        subject="Reset your password",
        body=f"Click here to reset: <a href='{reset_link}'>Reset Password</a>"
    )
    return {
        "message": "Password reset link sent to your email",
        "reset_token": reset_token,
    }

class PasswordResetPayload(BaseModel):
    token: str
    new_password: str

@router.post("/reset-password")
def reset_password(payload: PasswordResetPayload, db: Session = Depends(get_db)):
    email = verify_password_reset_token(payload.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    return {"message": "Password has been reset successfully"}

def create_password_reset_token(email: str, expires_delta: timedelta = timedelta(minutes=30)) -> str:
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")

def decode_token_raw(token: str, db: Session) -> Optional[UserResponse]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.query(User).filter(User.id == payload.get("id")).first()
        if not user:
            return None
        return UserResponse(id=user.id, email=user.email)
    except Exception as e:
        print("Token decode failed:", e)
        return None
    
@router.get("/account/me")
def get_current_user(user: User = Depends(get_current_user_model)):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "profile_pic": user.profile_pic,
    }

@router.put("/account/username")
def update_username(
    payload: UsernameUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_model),
):
    # Optional: Check if username already exists
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="Username already taken")

    current_user.username = payload.username
    db.commit()
    db.refresh(current_user)
    return {"username": current_user.username}

@router.post("/account/upload-profile-pic")
def upload_profile_pic(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_model),
    db: Session = Depends(get_db),
):
    # Construct upload path
    ext = file.filename.split('.')[-1]
    path = f"avatars/{current_user.id}.{ext}"

    # Read file content
    content = file.file.read()

    # Upload to Supabase
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/octet-stream",
        "x-upsert": "true"
    }

    response = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{path}",
        headers=headers,
        data=content
    )

    if response.status_code != 200:
        print("Upload failed:", response.text)
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")

    # Public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{path}"
    current_user.profile_pic = public_url
    db.commit()

    return {"profile_pic": public_url}