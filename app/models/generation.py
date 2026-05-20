from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from app.database import Base

class Generation(Base):
    __tablename__ = "generations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    prompt = Column(String)
    output = Column(String)
    type = Column(String, default="website")  # website | backend | fullstack
    response_time = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
