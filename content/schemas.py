# src/content/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from config import settings

class PostCreate(BaseModel):
    """Schema for creating a post."""
    media_url: str
    media_type: str  # image, video, gif
    description: Optional[str] = None
    content_type: str = "basic"  # fresh, archive, hard



def s3_to_cdn(url: str) -> str:
    """Convert S3 URL to CDN URL"""
    if not url:
        return url
    return url.replace(f"https://{settings.GCORE_S3_DOMAIN}", settings.CDN_URL)


class PostResponse(BaseModel):
    """Schema for post response."""
    id: int
    user_id: int
    media_url: str # CDN URL
    media_type: str
    description: Optional[str]
    likes: int
    created_at: datetime
    is_visible: bool
    content_type: str # fresh, archive, hard

    @classmethod
    def from_orm(cls, obj):
        # НЕ используй super().from_orm(obj) → он не знает про likes_rel
        return cls(
            id=obj.id,
            user_id=obj.user_id,
            media_url=s3_to_cdn(obj.media_url),
            media_type=obj.media_type,
            description=obj.description,
            created_at=obj.created_at,
            is_visible=obj.is_visible,
            content_type=obj.content_type,
            likes=len(obj.likes_rel)  # ← ВЫЧИСЛЯЕМ ЗДЕСЬ
        )

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    """Schema for creating a comment."""
    content: str

class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    username: str
    content: str
    created_at: datetime

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            post_id=obj.post_id,
            user_id=obj.user_id,
            username=obj.user.username,
            content=obj.content,
            created_at=obj.created_at,
        )

    class Config:
        from_attributes = True