# src/subscription/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""
    level: str
    promo_code: Optional[str] = None

class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    id: int
    user_id: int
    level: str
    expiry_date: datetime
    payment_id: int  # ← ДОБАВИЛИ

    class Config:
        from_attributes = True