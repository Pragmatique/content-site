# src/subscription/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from subscription.services import SubscriptionService
from subscription.schemas import SubscriptionCreate, SubscriptionResponse
from payment.schemas import PaymentCreateResponse
from auth.routes import get_current_user
from database import get_db
from auth.models import User

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.post("/", response_model=PaymentCreateResponse)
def create_subscription(
    subscription_data: SubscriptionCreate,
    currency: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or extend a subscription."""
    return SubscriptionService.create_subscription(subscription_data, currency, current_user, db)

@router.get("/", response_model=List[SubscriptionResponse])
def get_user_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve user subscriptions."""
    return SubscriptionService.get_user_subscriptions(current_user.id, db)