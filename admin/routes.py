# src/admin/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from auth.models import User, AdminActionLog
from auth.schemas import UserResponse, AdminActionLogResponse
from content.models import Post
from content.schemas import PostResponse
from subscription.models import Subscription
from subscription.schemas import SubscriptionResponse
from payment.models import Payment, Discount
from payment.schemas import PaymentResponse, DiscountResponse
from auth.routes import get_current_user
from database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

def check_admin_role(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(check_admin_role)])
def get_users(
    subscription_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Retrieve users with optional subscription level filter."""
    query = db.query(User)
    if subscription_level:
        query = query.filter(User.subscription_level == subscription_level)
    return [UserResponse.from_orm(user) for user in query.all()]

@router.patch("/users/{user_id}/subscription", response_model=UserResponse, dependencies=[Depends(check_admin_role)])
def update_user_subscription(
    user_id: int,
    subscription_level: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Update a user's subscription level."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.subscription_level = subscription_level
    db.commit()
    db.refresh(user)
    log = AdminActionLog(admin_id=current_user.id, action=f"Updated subscription level of user {user_id} to {subscription_level}")
    db.add(log)
    db.commit()
    return UserResponse.from_orm(user)

@router.get("/posts", response_model=List[PostResponse], dependencies=[Depends(check_admin_role)])
def get_posts(
    user_id: Optional[int] = None,
    content_type: Optional[str] = None,
    media_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Retrieve posts with optional filters."""
    query = db.query(Post)
    if user_id:
        query = query.filter(Post.user_id == user_id)
    if content_type:
        query = query.filter(Post.content_type == content_type)
    if media_type:
        query = query.filter(Post.media_type == media_type)
    return [PostResponse.from_orm(post) for post in query.all()]

@router.get("/subscriptions", response_model=List[SubscriptionResponse], dependencies=[Depends(check_admin_role)])
def get_subscriptions(
    level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Retrieve subscriptions with optional level filter."""
    query = db.query(Subscription)
    if level:
        query = query.filter(Subscription.level == level)
    return [SubscriptionResponse.from_orm(sub) for sub in query.all()]

@router.get("/payments", response_model=List[PaymentResponse], dependencies=[Depends(check_admin_role)])
def get_payments(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
):
    """Retrieve payments with optional status filter."""
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == status)
    return [PaymentResponse.from_orm(payment) for payment in query.all()]

@router.get("/logs", response_model=List[AdminActionLogResponse], dependencies=[Depends(check_admin_role)])
def get_admin_logs(db: Session = Depends(get_db), current_user: User = Depends(check_admin_role)):
    """Retrieve admin action logs."""
    return [AdminActionLogResponse.from_orm(log) for log in db.query(AdminActionLog).all()]