from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt

SECRET_KEY = "prompcorp-war-room-secret-key-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory user store (simple stub)
users_db: dict[str, str] = {
    "admin": pwd_context.hash("prompcorp123")
}

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str

def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    if req.username in users_db:
        raise HTTPException(status_code=400, detail="Username already exists")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    users_db[req.username] = pwd_context.hash(req.password)
    token = create_token(req.username)
    return TokenResponse(access_token=token, token_type="bearer", username=req.username)

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    hashed = users_db.get(req.username)
    if not hashed or not pwd_context.verify(req.password, hashed):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(req.username)
    return TokenResponse(access_token=token, token_type="bearer", username=req.username)
