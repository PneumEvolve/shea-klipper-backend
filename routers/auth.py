from fastapi import APIRouter, HTTPException, Depends, Security, Request
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import timedelta, datetime
from passlib.context import CryptContext
from database import get_db
from models import User
from pydantic import BaseModel, EmailStr
import requests
from dotenv import load_dotenv
import os
from pathlib import Path
from typing import Optional
from utils.email import send_email
from schemas import UserResponse
from models import Category, user_categories
from sqlalchemy import text

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

print("RECAPTCHA_SECRET:", os.getenv("RECAPTCHA_SECRET"))

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")  # 🔒 Load from .env
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ✅ Define User Schema for Signup
class UserCreate(BaseModel):
    email: str
    password: str

# ✅ Hash password
def hash_password(password: str):
    return pwd_context.hash(password)

# ✅ Verify password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# ✅ Create JWT token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_recaptcha(token: str) -> bool:
    url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        "secret": RECAPTCHA_SECRET,
        "response": token,
    }
    response = requests.post(url, data=payload)
    result = response.json()
    print("🔍 reCAPTCHA verification result:", result)  # ✅ ADD THIS
    return result.get("success", False)

# 🔐 Generate Password Reset Token
def create_password_reset_token(email: str, expires_delta: timedelta = timedelta(minutes=30)) -> str:
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ Verify Password Reset Token
def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")  # should be the email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")

# ✅ SIGNUP Endpoint
@router.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 🟡 Auto-create default categories for this new user
    default_categories = {
    "food": ["Pantry", "Fridge", "Freezer"],
    "recipe": ["Breakfast", "Lunch", "Dinner"]
    }

    for category_type, names in default_categories.items():
        for name in names:
            # Check if the category exists globally
            category = db.query(Category).filter_by(name=name, type=category_type).first()
            if not category:
                category = Category(name=name, type=category_type)
                db.add(category)
                db.commit()
                db.refresh(category)

            # Link to user if not already linked
            exists = db.execute(
                text("""
                    SELECT 1 FROM user_categories
                    WHERE user_id = :user_id AND category_id = :category_id
                """),
                {"user_id": new_user.id, "category_id": category.id}
            ).first()

            if not exists:
                db.execute(user_categories.insert().values(user_id=new_user.id, category_id=category.id))
                db.commit()

    return UserResponse(id=new_user.id, email=new_user.email)

# ✅ LOGIN Endpoint
@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # 🔒 Step 1: Extract and verify reCAPTCHA token
    form = await request.form()
    recaptcha_token = form.get("recaptcha_token")
    if not recaptcha_token or not verify_recaptcha(recaptcha_token):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")

    # 🔐 Step 2: Continue with your normal login logic
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token({"sub": user.email, "id": user.id}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

# ✅ Dependency to Get Current User
def get_current_user_dependency(token: str = Security(oauth2_scheme), db: Session = Depends(get_db)):
    print(f"🔹 Received token: {token}")  # ✅ Log incoming token for debugging
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.query(User).filter(User.id == payload.get("id")).first()
        if not user:
            print("🔴 Invalid authentication: User not found")
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return UserResponse(id=user.id, email=user.email)
    except jwt.ExpiredSignatureError:
        print("🔴 Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        print("🔴 Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")

# ✅ GET CURRENT USER Endpoint
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
# ✅ Send the email with reset link
    frontend_url = os.getenv("FRONTEND_URL", "https://sheas-app.netlify.app")
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"
    send_email(
        to_email=user.email,
        subject="Reset your password",
        body=f"Click here to reset: <a href='{reset_link}'>Reset Password</a>"
    )
    return {
        "message": "Password reset link sent to your email",
        "reset_token": reset_token,
        # eventually: "reset_link": f"https://your-frontend/reset-password?token={reset_token}"
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
