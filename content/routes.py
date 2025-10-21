# src/content/routes.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from content.services import PostService, CommentService
from content.models import Post, Comment
from content.schemas import PostCreate, PostResponse, CommentCreate, CommentResponse
from auth.routes import get_current_user
from database import get_db
from auth.models import User
from typing import Optional

router = APIRouter(prefix="/content", tags=["content"])

def check_admin_role(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.post("/posts", response_model=PostResponse, dependencies=[Depends(check_admin_role)])
async def create_post(
    file: UploadFile = File(...),
    media_type: str = "image",
    content_type: str = "basic",
    description: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
) -> PostResponse:
    """Create a new post with media uploaded to GCore."""
    return await PostService.create_post(
        file=file,
        media_type=media_type,
        content_type=content_type,
        description=description,
        user_id=current_user.id,
        db=db
    )

@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Session = Depends(get_db)) -> PostResponse:
    """Retrieve a post by ID."""
    post = PostService.get_post(post_id, db)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.put("/posts/{post_id}", response_model=PostResponse, dependencies=[Depends(check_admin_role)])
async def update_post(
    post_id: int,
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
) -> PostResponse:
    """Update a post."""
    post = PostService.update_post(post_id, post_data, db)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.delete("/posts/{post_id}", dependencies=[Depends(check_admin_role)])
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
) -> dict:
    """Delete a post."""
    if not PostService.delete_post(post_id, db):
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted"}

@router.patch("/posts/{post_id}/visibility", response_model=PostResponse, dependencies=[Depends(check_admin_role)])
async def toggle_post_visibility(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_role)
) -> PostResponse:
    """Toggle post visibility."""
    post = PostService.toggle_visibility(post_id, db)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.get("/posts", response_model=List[PostResponse])
async def get_posts(
    user_id: Optional[int] = None,
    content_type: Optional[str] = None,
    media_type: Optional[str] = None,
    db: Session = Depends(get_db)
) -> List[PostResponse]:
    """Retrieve posts with optional filters."""
    return PostService.get_posts(user_id, content_type, media_type, db)

@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
async def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CommentResponse:
    """Create a comment on a post."""
    return CommentService.create_comment(post_id, comment_data, current_user.id, db)

@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_comments(post_id: int, db: Session = Depends(get_db)) -> List[CommentResponse]:
    """Retrieve comments for a post."""
    return CommentService.get_comments(post_id, db)

@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CommentResponse:
    """Update a comment."""
    comment = CommentService.update_comment(comment_id, comment_data, current_user.id, db)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """Delete a comment."""
    if not CommentService.delete_comment(comment_id, current_user.id, db):
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"message": "Comment deleted"}

@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """Like a post."""
    PostService.like_post(post_id, db)
    return {"message": "Post liked"}