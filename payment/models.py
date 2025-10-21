# src/payment/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Payment(Base):
    """Represents a payment for a subscription."""
    __tablename__ = "payments"

    id: int = Column(Integer, primary_key=True, index=True)
    subscription_id: int = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    discount_id: int = Column(Integer, ForeignKey("discounts.id"), nullable=True)
    payment_method: str = Column(String, nullable=False)
    payment_id: str = Column(String, nullable=True)
    transaction_id: str = Column(String, nullable=True)
    amount: int = Column(Integer, nullable=False)
    currency: str = Column(String, nullable=False)
    payout_currency: str = Column(String, default="USDT")
    discount_applied: int = Column(Integer, default=0)
    status: str = Column(String, default="pending")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    expiration_time: datetime = Column(DateTime, nullable=False)

    subscription = relationship("Subscription", back_populates="payments")
    discount = relationship("Discount", back_populates="payments")

class Discount(Base):
    """Represents a discount for payments."""
    __tablename__ = "discounts"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=True)
    discount_type: str = Column(String, nullable=False)
    discount_percentage: int = Column(Integer, nullable=False)
    code: str = Column(String, nullable=True)
    valid_until: datetime = Column(DateTime, nullable=True)
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="discounts")
    payments = relationship("Payment", back_populates="discount")