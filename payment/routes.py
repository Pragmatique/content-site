# src/payment/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from payment.services import PaymentService
from payment.schemas import PaymentResponse, DiscountCreate, DiscountResponse, PaymentCheckResponse
from payment.models import Payment
from auth.routes import get_current_user
from auth.models import User
from database import get_db
from datetime import datetime
from config import settings

router = APIRouter(prefix="/payments", tags=["payments"])

def check_admin_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.get("/check-payment/{client_payment_id}", response_model=PaymentCheckResponse)
def check_payment(
    client_payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check payment status and return full UX info."""
    payment = db.query(Payment).filter(Payment.client_payment_id == client_payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == "pending" and datetime.utcnow() > payment.expiration_time:
        payment.status = "expired"
        db.commit()

    if payment.status == "pending":
        payment_service = PaymentService()
        if payment_service.check_payment(payment, db):
            payment_service.confirm_payment(payment, db)
            payment.status = "confirmed"
            db.commit()

    time_left = 0
    if payment.status == "pending":
        time_left = max(0, int((payment.expiration_time - datetime.utcnow()).total_seconds()))

    if payment.currency == "usdttrc20":
        payment_url = settings.TRON_WALLET_ADDRESS
    elif payment.currency == "usdtbep20":
        payment_url = settings.BSC_WALLET_ADDRESS
    else:
        payment_url = ""

    return PaymentCheckResponse(
        status=payment.status,
        amount=payment.amount / 100.0,
        currency=payment.currency,
        payment_url=payment_url,
        expires_at=payment.expiration_time,
        time_left_seconds=time_left
    )

@router.get("/", response_model=List[PaymentResponse])
def get_user_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return PaymentService.get_user_payments(current_user.id, db)

@router.post("/discounts", response_model=DiscountResponse, dependencies=[Depends(check_admin_role)])
def create_discount(discount: DiscountCreate, db: Session = Depends(get_db), current_user: User = Depends(check_admin_role)):
    return PaymentService.create_discount(discount, db)

@router.put("/discounts/{discount_id}", response_model=DiscountResponse, dependencies=[Depends(check_admin_role)])
def update_discount(discount_id: int, discount_data: DiscountCreate, db: Session = Depends(get_db), current_user: User = Depends(check_admin_role)):
    discount = PaymentService.update_discount(discount_id, discount_data, db)
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return discount

@router.delete("/discounts/{discount_id}", dependencies=[Depends(check_admin_role)])
def delete_discount(discount_id: int, db: Session = Depends(get_db), current_user: User = Depends(check_admin_role)):
    if not PaymentService.delete_discount(discount_id, db):
        raise HTTPException(status_code=404, detail="Discount not found")
    return {"message": "Discount deleted"}

@router.get("/discounts", response_model=List[DiscountResponse], dependencies=[Depends(check_admin_role)])
def get_discounts(db: Session = Depends(get_db), current_user: User = Depends(check_admin_role)):
    return PaymentService.get_discounts(db)