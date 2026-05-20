from fastapi import APIRouter, HTTPException
from app.database import AsyncSessionLocal
from app.models.user import User
from app.security.jwt_handler import create_token
from app.schemas.auth_schema import RegisterSchema, LoginSchema
from app.services.auth_service import hash_password, verify_password, get_user_by_email

router = APIRouter(prefix="/auth")

@router.post("/register")
async def register(data: RegisterSchema):
    async with AsyncSessionLocal() as db:
        existing_user = await get_user_by_email(db, data.email)

        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(
            email=data.email,
            password=hash_password(data.password)
        )

        db.add(user)
        await db.commit()

    return {"message": "Registered successfully"}


@router.post("/login")
async def login(data: LoginSchema):
    async with AsyncSessionLocal() as db:
        user = await get_user_by_email(db, data.email)

        if not user or not verify_password(data.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_token({"user_id": user.id, "role": user.role})

    return {"access_token": token}
