from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.generation import Generation
from app.security.jwt_handler import verify_token
from typing import List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == payload["user_id"]))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

class UserProfileSchema(BaseModel):
    id: int
    email: str
    credits: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class GenerationHistorySchema(BaseModel):
    id: int
    prompt: str
    output: str
    type: str = "website"
    created_at: datetime
    response_time: int | None

    class Config:
        from_attributes = True

@router.get("/me", response_model=UserProfileSchema)
async def get_my_profile(user: User = Depends(get_current_user)):
    return user

@router.get("/history", response_model=List[GenerationHistorySchema])
async def get_my_history(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        # Fetch generations for this user, ordered by most recent first
        result = await db.execute(
            select(Generation)
            .where(Generation.user_id == user.id)
            .order_by(Generation.created_at.desc())
        )
        generations = result.scalars().all()
        return generations
