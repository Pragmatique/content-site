# src/subscription/services.py
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Tuple
from subscription.models import Subscription
from subscription.schemas import SubscriptionCreate, SubscriptionResponse
from payment.schemas import PaymentCreateResponse
from payment.models import Discount
from payment.services import PaymentService
from auth.models import User
from config import settings

class SubscriptionService:
    @staticmethod
    def get_discount(promo_code: Optional[str], db: Session) -> Tuple[Optional[int], float, str]:
        if not promo_code:
            return None, 0.0, ""
        discount = db.query(Discount).filter(
            Discount.code == promo_code,
            Discount.is_active == True,
            (Discount.valid_until.is_(None) | (Discount.valid_until >= datetime.utcnow()))
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
    ) -> PaymentCreateResponse:
        if subscription_data.level not in settings.SUBSCRIPTION_PRICES:
            raise HTTPException(status_code=400, detail="Invalid subscription level")

        today = datetime.utcnow().date()
        dob = user.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise HTTPException(status_code=403, detail="You must be 18 or older")

        active_sub = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.expiry_date > datetime.utcnow()
        ).first()

        base_price = settings.SUBSCRIPTION_PRICES[subscription_data.level]

        discount_id, discount_rate, discount_info = SubscriptionService.get_discount(subscription_data.promo_code, db)
        final_price = base_price * (1 - discount_rate)

        if active_sub:
            if active_sub.level == subscription_data.level:
                final_price = base_price
            elif settings.SUBSCRIPTION_PRICES[active_sub.level] > base_price:
                raise HTTPException(status_code=400, detail="Downgrade not allowed")
            else:
                final_price = base_price - settings.SUBSCRIPTION_PRICES[active_sub.level]

        payment_service = PaymentService()
        unique_amount = payment_service.generate_unique_amount(final_price, db)

        # Создаём Payment через service
        payment_resp = payment_service.create_payment(
            user_id=user.id,
            purpose="subscription",
            level=subscription_data.level,
            amount=unique_amount,
            currency=currency,
            db=db
        )

        payment_resp.discount_info = discount_info  # Добавляем, если нужно (расширяем response если discount)

        return payment_resp

    @staticmethod
    def get_user_subscriptions(user_id: int, db: Session) -> list[SubscriptionResponse]:
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.expiry_date > datetime.utcnow()
        ).all()
        return [SubscriptionResponse.from_orm(s) for s in subs]