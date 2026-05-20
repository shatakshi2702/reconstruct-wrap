from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.security.jwt_handler import verify_token

router = APIRouter(prefix="/admin")

@router.get("/users")
async def get_all_users(request: Request):
    token_header = request.headers.get("Authorization")

    if not token_header:
        raise HTTPException(status_code=401)

    token = token_header.split(" ")[1]
    payload = verify_token(token)

    if not payload or payload["role"] != "admin":
        raise HTTPException(status_code=403)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

    return [{"id": u.id, "email": u.email, "credits": u.credits} for u in users]
