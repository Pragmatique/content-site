# src/subscription/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Subscription(Base):
    """Represents a user subscription."""
    __tablename__ = "subscriptions"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    level: str = Column(String, nullable=False)
    expiry_date: datetime = Column(DateTime, nullable=False)
    payment_id: int = Column(Integer, ForeignKey("payments.id"), nullable=False)  # ← ДОБАВИЛИ (last successful payment)

    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment")  # ← ДОБАВИЛИ (no back_populates, one-way)