# src/auth/models.py
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    """Represents a user in the system."""
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    username: str = Column(String, unique=True, index=True, nullable=False)
    email: str = Column(String, unique=True, index=True, nullable=False)
    password_hash: str = Column(String, nullable=False)
    subscription_level: str = Column(String, default="free")
    date_of_birth: datetime = Column(Date, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    role: str = Column(String, nullable=False, default="user")

    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    discounts = relationship("Discount", back_populates="user")
    admin_actions = relationship("AdminActionLog", back_populates="admin")

class AdminActionLog(Base):
    """Represents a log of admin actions."""
    __tablename__ = "admin_action_logs"

    id: int = Column(Integer, primary_key=True, index=True)
    admin_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    action: str = Column(String, nullable=False)
    timestamp: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    admin = relationship("User", back_populates="admin_actions")