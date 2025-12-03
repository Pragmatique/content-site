# src/auth/schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional

class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str
    email: EmailStr
    password: str
    date_of_birth: date

class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    username: str
    email: str
    subscription_level: Optional[str] = None  # basic, pro, premium или None
    subscription_expires_at: Optional[datetime] = None  # последняя подписка
    date_of_birth: date
    created_at: datetime
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str

class AdminActionLogResponse(BaseModel):
    """Schema for admin action log response."""
    id: int
    admin_id: int
    action: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str