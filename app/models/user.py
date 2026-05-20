from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    credits = Column(Integer, default=10)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
