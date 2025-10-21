# src/payment/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from payment.services import PaymentService
from payment.schemas import PaymentResponse, DiscountCreate, DiscountResponse
from payment.models import Payment
from subscription.models import Subscription
from auth.routes import get_current_user
from auth.models import User
from database import get_db
from datetime import datetime
from config import settings

router = APIRouter(prefix="/payments", tags=["payments"])

def check_admin_role(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.get("/check-payment/{payment_id}")
def check_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check payment status."""
    expired_payments = db.query(Payment).filter(
        Payment.status == "pending",
        Payment.expiration_time < datetime.utcnow()
    ).all()
    for payment in expired_payments:
        payment.status = "expired"
    db.commit()

    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == "pending" and datetime.utcnow() > payment.expiration_time:
        payment.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Payment expired")

    payment_service = PaymentService()
    if payment_service.check_payment(payment, db):
        subscription = payment.subscription
        subscription.expiry_date = datetime.utcnow() + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
        current_user.subscription_level = subscription.level
        db.commit()
        return {"status": "confirmed"}
    return {"status": payment.status}

@router.get("/", response_model=List[PaymentResponse])
def get_user_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve user payments."""
    return PaymentService.get_user_payments(current_user.id, db)

@router.post("/discounts", response_model=DiscountResponse, dependencies=[Depends(check_admin_role)])
def create_discount(
    discount: DiscountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Create a new discount."""
    return PaymentService.create_discount(discount, db)

@router.put("/discounts/{discount_id}", response_model=DiscountResponse, dependencies=[Depends(check_admin_role)])
def update_discount(
    discount_id: int,
    discount_data: DiscountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Update a discount."""
    discount = PaymentService.update_discount(discount_id, discount_data, db)
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return discount

@router.delete("/discounts/{discount_id}", dependencies=[Depends(check_admin_role)])
def delete_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Delete a discount."""
    if not PaymentService.delete_discount(discount_id, db):
        raise HTTPException(status_code=404, detail="Discount not found")
    return {"message": "Discount deleted"}

@router.get("/discounts", response_model=List[DiscountResponse], dependencies=[Depends(check_admin_role)])
def get_discounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Retrieve all discounts."""
    return PaymentService.get_discounts(db)