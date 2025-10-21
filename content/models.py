# src/content/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from typing import Optional

class Post(Base):
    """Represents a media post created by an admin."""
    __tablename__ = "posts"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    media_url: str = Column(String, nullable=False)
    media_type: str = Column(String, nullable=False)  # image, video, gif
    description: Optional[str] = Column(Text, nullable=True)
    likes: int = Column(Integer, default=0)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    is_visible: bool = Column(Boolean, nullable=False, default=True)
    content_type: str = Column(String, nullable=False, default="basic")  # basic, archive

    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")

class Comment(Base):
    """Represents a user comment on a post."""
    __tablename__ = "comments"

    id: int = Column(Integer, primary_key=True, index=True)
    post_id: int = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    content: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")