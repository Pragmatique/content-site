# src/auth/services.py
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from auth.models import User
from auth.schemas import UserCreate, UserResponse
from config import settings

class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return AuthService.pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return AuthService.pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def get_user_by_email(email: str, db: Session) -> Optional[User]:
        """Retrieve a user by email."""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def authenticate_user(email: str, password: str, db: Session) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = AuthService.get_user_by_email(email, db)
        if not user or not AuthService.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_user(user_data: UserCreate, db: Session) -> UserResponse:
        """Create a new user."""
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=AuthService.hash_password(user_data.password),
            date_of_birth=user_data.date_of_birth
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return UserResponse.from_orm(new_user)