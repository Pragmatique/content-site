# src/auth/routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import timedelta, datetime
from auth.services import AuthService
from auth.schemas import UserCreate, UserResponse, UserLogin, Token
from auth.models import User
from config import settings
from database import get_db
from subscription.models import Subscription

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)) -> User:
    """Retrieve the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": True})
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        exp = payload.get("exp")
        if exp is None or datetime.utcfromtimestamp(exp) < datetime.utcnow():
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = AuthService.get_user_by_email(email, db)
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    return AuthService.create_user(user, db)

@router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    """Login and return a JWT token."""
    authenticated_user = AuthService.authenticate_user(user.email, user.password, db)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token(
        data={"sub": authenticated_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user details with the active subscription level."""

    # Ищем САМУЮ СВЕЖУЮ подписку (по expiry_date DESC)
    latest_sub = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).order_by(Subscription.expiry_date.desc()).first()

    # Активная подписка — только если не истекла
    latest_sub = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).order_by(Subscription.expiry_date.desc()).first()

    subscription_level = latest_sub.level if latest_sub else None
    subscription_expires_at = latest_sub.expiry_date if latest_sub else None

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "date_of_birth": current_user.date_of_birth,
        "created_at": current_user.created_at,
        "role": current_user.role,
        "subscription_level": subscription_level,  # null если нет активной
        "subscription_expires_at": subscription_expires_at  # всегда последняя
    }