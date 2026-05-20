from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.config import settings

ALGORITHM = "HS256"

def create_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=12)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        return None
