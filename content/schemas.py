# src/content/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PostCreate(BaseModel):
    """Schema for creating a post."""
    media_url: str
    media_type: str  # image, video, gif
    description: Optional[str] = None
    content_type: str = "basic"  # basic, archive

class PostResponse(BaseModel):
    """Schema for post response."""
    id: int
    user_id: int
    media_url: str
    media_type: str
    description: Optional[str]
    likes: int
    created_at: datetime
    is_visible: bool
    content_type: str

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    """Schema for creating a comment."""
    content: str

class CommentResponse(BaseModel):
    """Schema for comment response."""
    id: int
    post_id: int
    user_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True