# src/auth/services.py
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional
from auth.models import User, VerificationToken
from auth.schemas import UserCreate, UserResponse
from config import settings
import smtplib
from email.mime.text import MIMEText
from uuid import uuid4
from datetime import timedelta

logger = logging.getLogger(__name__)

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
        user = AuthService.get_user_by_email(email, db)
        if not user or not AuthService.verify_password(password, user.password_hash):
            return None
        if user.role == "unverified":
            raise HTTPException(status_code=403, detail="Please verify your email first")
        return user

    @staticmethod
    def create_user(user_data: UserCreate, db: Session) -> UserResponse:
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=AuthService.hash_password(user_data.password),
            date_of_birth=user_data.date_of_birth,
            role="unverified"  # Initial role
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Generate verification token
        token = uuid4().hex
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        ver_token = VerificationToken(user_id=new_user.id, token=token, token_type='verify', expiry=expiry)
        db.add(ver_token)
        db.commit()

        # Send verification email
        verify_url = f"{settings.BASE_FRONT_URL}/verify?token={token}"  # Change to prod URL
        body = f"Click to verify: {verify_url}"
        AuthService.send_email(new_user.email, "Verify Your Email", body)

        return UserResponse.from_orm(new_user)

    @staticmethod
    def send_email(to_email: str, subject: str, body: str):
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = settings.FROM_EMAIL
            msg['To'] = to_email

            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())
        except Exception as e:
            logger.error(f"SMTP error sending to {to_email}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=503, detail="Email service temporarily unavailable, try again later")

    @staticmethod
    def send_password_reset(email: str, db: Session):
        user = AuthService.get_user_by_email(email, db)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        token = uuid4().hex
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        reset_token = VerificationToken(user_id=user.id, token=token, token_type='reset', expiry=expiry)
        db.add(reset_token)
        db.commit()

        reset_url = f"{settings.BASE_FRONT_URL}/reset-password?token={token}"  # Change to prod URL
        body = f"Click to reset password: {reset_url}"
        AuthService.send_email(email, "Reset Your Password", body)
        return {"message": "Password reset email sent"}

    @staticmethod
    def reset_password(token: str, new_password: str, db: Session):
        reset_token = db.query(VerificationToken).filter(
            VerificationToken.token == token,
            VerificationToken.token_type == 'reset',
            VerificationToken.expiry > datetime.now(timezone.utc)
        ).first()
        if not reset_token:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        user = db.query(User).filter(User.id == reset_token.user_id).first()
        user.password_hash = AuthService.hash_password(new_password)
        db.delete(reset_token)
        db.commit()
        return {"message": "Password reset successful"}