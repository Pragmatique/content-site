# src/payment/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PaymentResponse(BaseModel):
    """Schema for payment response."""
    id: int
    subscription_id: int
    discount_id: Optional[int]
    payment_method: str
    payment_id: Optional[str]
    transaction_id: Optional[str]
    amount: int
    currency: str
    payout_currency: Optional[str]
    discount_applied: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentCreateResponse(BaseModel):
    """Schema for payment creation response."""
    payment_id: str
    payment_url: str
    amount: float
    final_amount: float
    discount_info: str

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