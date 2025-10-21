# src/subscription/services.py
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Tuple
from subscription.models import Subscription
from subscription.schemas import SubscriptionCreate, SubscriptionResponse
from payment.models import Payment, Discount
from payment.services import PaymentService
from auth.models import User
from config import settings

class SubscriptionService:
    @staticmethod
    def get_discount(promo_code: Optional[str], db: Session) -> Tuple[Optional[int], float, str]:
        """Retrieve discount details if valid promo code is provided."""
        if not promo_code:
            return None, 0.0, ""
        discount = db.query(Discount).filter(
            Discount.code == promo_code,
            Discount.is_active == True,
            Discount.valid_until >= datetime.utcnow()
        ).first()
        if discount:
            return discount.id, discount.discount_percentage / 100.0, f"Applied promo code {promo_code}, discount {discount.discount_percentage}%"
        return None, 0.0, ""

    @staticmethod
    def create_subscription(
        subscription_data: SubscriptionCreate,
        currency: str,
        user: User,
        db: Session
    ) -> dict:
        """Create or extend a subscription with payment."""
        if subscription_data.level not in settings.SUBSCRIPTION_PRICES:
            raise HTTPException(status_code=400, detail="Invalid subscription level")

        today = datetime.utcnow().date()
        dob = user.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise HTTPException(status_code=403, detail="You must be 18 or older to subscribe")

        active_subscription = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.expiry_date >= datetime.utcnow()
        ).first()

        base_price = settings.SUBSCRIPTION_PRICES[subscription_data.level]
        payment_service = PaymentService()
        unique_amount = payment_service.generate_unique_amount(base_price, db)

        if active_subscription:
            if active_subscription.level == subscription_data.level:
                unique_amount = base_price
            elif settings.SUBSCRIPTION_PRICES[active_subscription.level] > settings.SUBSCRIPTION_PRICES[subscription_data.level]:
                raise HTTPException(
                    status_code=400,
                    detail=f"You have an active {active_subscription.level} subscription until {active_subscription.expiry_date}. Downgrading is not allowed."
                )
            else:
                unique_amount = settings.SUBSCRIPTION_PRICES[subscription_data.level] - settings.SUBSCRIPTION_PRICES[active_subscription.level]

        final_price = int(unique_amount * 100)
        discount_id, discount, discount_info = SubscriptionService.get_discount(subscription_data.promo_code, db)
        if discount > 0:
            final_amount = unique_amount * (1 - discount)
            final_price = int(final_amount * 100)
        else:
            final_amount = unique_amount

        if active_subscription and active_subscription.level == subscription_data.level:
            active_subscription.expiry_date = active_subscription.expiry_date + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
            new_subscription = active_subscription
        else:
            expiry_date = datetime.utcnow() + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
            new_subscription = Subscription(
                user_id=user.id,
                level=subscription_data.level,
                expiry_date=expiry_date
            )
            db.add(new_subscription)
            if active_subscription:
                active_subscription.expiry_date = datetime.utcnow()

        db.commit()
        db.refresh(new_subscription)

        expiration_time = datetime.utcnow() + timedelta(minutes=30)
        new_payment = Payment(
            subscription_id=new_subscription.id,
            discount_id=discount_id,
            payment_method="crypto",
            payment_id=f"pay_{new_subscription.id}_{datetime.utcnow().timestamp()}",
            transaction_id=None,
            amount=final_price,
            currency=currency,
            discount_applied=int((unique_amount - final_amount) * 100) if discount_id else 0,
            status="pending",
            expiration_time=expiration_time
        )
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)

        payment_response = payment_service.create_payment(final_amount, currency, db)
        return {
            "payment_id": new_payment.payment_id,
            "payment_url": payment_response["payment_url"],
            "amount": final_amount,
            "final_amount": final_amount,
            "discount_info": discount_info
        }

    @staticmethod
    def get_user_subscriptions(user_id: int, db: Session) -> list[SubscriptionResponse]:
        """Retrieve all subscriptions for a user."""
        subscriptions = db.query(Subscription).filter(Subscription.user_id == user_id).all()
        return [SubscriptionResponse.from_orm(sub) for sub in subscriptions]