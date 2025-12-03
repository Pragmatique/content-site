# src/payment/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PaymentResponse(BaseModel):
    """Schema for payment response."""
    id: int
    user_id: int  # ← ДОБАВИЛИ
    purpose: str  # ← ДОБАВИЛИ
    level: Optional[str]  # ← ДОБАВИЛИ
    discount_id: Optional[int]
    payment_method: str
    client_payment_id: Optional[str]  # ← ПЕРЕИМЕНОВАЛИ
    transaction_id: Optional[str]
    amount: int
    currency: str
    # УБРАЛИ payout_currency, discount_applied
    status: str
    created_at: datetime
    expiration_time: datetime

    class Config:
        from_attributes = True

class PaymentCreateResponse(BaseModel):
    """Schema for payment creation response."""
    client_payment_id: str  # ← ПЕРЕИМЕНОВАЛИ
    payment_url: str
    amount: float
    final_amount: float
    discount_info: str
    expires_at: datetime
    currency: str  # ← ДОБАВИЛИ (для фронта)

class PaymentCheckResponse(BaseModel):
    status: str
    amount: float
    currency: str
    payment_url: str
    expires_at: datetime
    time_left_seconds: int

class DiscountCreate(BaseModel):
    """Schema for creating a discount."""
    discount_type: str
    discount_percentage: int
    code: Optional[str] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True

class DiscountResponse(BaseModel):
    """Schema for discount response."""
    id: int
    user_id: Optional[int]
    discount_type: str
    discount_percentage: int
    code: Optional[str]
    valid_until: Optional[datetime]
    is_active: bool
    created_at: datetime
    usage_count: int

    class Config:
        from_attributes = True