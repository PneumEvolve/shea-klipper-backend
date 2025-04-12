from fastapi import APIRouter, HTTPException, Depends, Security, Request
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import timedelta, datetime
from passlib.context import CryptContext
from database import get_db
from models import User
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv

load_dotenv()

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")  # 🔒 Load from .env
print("🔍 Loaded RECAPTCHA_SECRET:", RECAPTCHA_SECRET)
SECRET_KEY = "your_secret_key"
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
    
    return {"id": new_user.id, "email": new_user.email}

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
        return {"id": user.id, "email": user.email}
    except jwt.ExpiredSignatureError:
        print("🔴 Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        print("🔴 Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")

# ✅ GET CURRENT USER Endpoint
@router.get("/user")
def get_current_user_route(current_user: dict = Depends(get_current_user_dependency)):
    """Fetch the currently authenticated user."""
    return {"id": current_user["id"], "email": current_user["email"]}