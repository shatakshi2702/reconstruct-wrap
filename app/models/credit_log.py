from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from datetime import datetime
from app.database import Base

class CreditLog(Base):
    __tablename__ = "credit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    change_amount = Column(Integer)
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
