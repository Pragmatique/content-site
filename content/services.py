# src/content/services.py
import hashlib
import hmac
import aiofiles
import logging
import mimetypes
import os
import shutil
import tempfile
import urllib.parse
import requests
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from content.models import Post, Comment
from content.schemas import PostCreate, PostResponse, CommentCreate, CommentResponse
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostService:
    @staticmethod
    async def create_post(
            file: UploadFile,
            media_type: str,
            content_type: str,
            description: Optional[str],
            user_id: int,
            db: Session
    ) -> PostResponse:
        """Create a new post with media uploaded to GCore."""
        if content_type not in ["basic", "pro", "premium"]:
            raise HTTPException(status_code=400, detail="Invalid content_type")
        if media_type not in ["image", "video", "gif"]:
            raise HTTPException(status_code=400, detail="Invalid media_type")

        mime_type, _ = mimetypes.guess_type(file.filename)
        if not mime_type or not (mime_type.startswith("image/") or mime_type.startswith("video/")):
            raise HTTPException(status_code=400, detail="File must be an image, video, or gif")

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        if file_size > 4 * 1024 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 4GB")

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        try:
            file_key = f"media/{user_id}/{datetime.utcnow().timestamp()}_{urllib.parse.quote(file.filename)}"
            cdn_url = await PostService._upload_to_gcore(temp_file_path, file_key,
                                                         mime_type or "application/octet-stream")

            db_post = Post(
                user_id=user_id,
                media_url=cdn_url,
                media_type=media_type,
                content_type=content_type,
                description=description,
                is_visible=True
            )
            db.add(db_post)
            db.commit()
            db.refresh(db_post)
            return PostResponse.from_orm(db_post)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    @staticmethod
    async def _upload_to_gcore(file_path: str, file_key: str, mime_type: str) -> str:
        """Upload file to GCore and return CDN URL."""
        method = 'PUT'
        service = 's3'
        region = settings.GCORE_REGION_NAME
        host = f"{settings.GCORE_BUCKET_NAME}.s-ed1.cloud.gcore.lu"
        canonical_uri = f"/{file_key}"
        querystring = ''
        amz_date = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        date_stamp = datetime.utcnow().strftime('%Y%m%d')
        payload_hash = PostService._calculate_payload_hash(file_path)
        headers = PostService._create_auth_headers(
            method, service, region, host, canonical_uri, querystring, payload_hash,
            settings.GCORE_ACCESS_KEY, settings.GCORE_SECRET_KEY, mime_type, amz_date, date_stamp,
            os.path.getsize(file_path)
        )
        url = f"https://{host}{canonical_uri}"
        with open(file_path, 'rb') as f:
            response = requests.put(url, data=f, headers=headers)
        if response.status_code != 200:
            logger.error(f"GCore upload failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500,
                                detail=f"GCore upload failed: {response.status_code} - {response.text}")
        return f"{settings.GCORE_ENDPOINT_URL}/{settings.GCORE_BUCKET_NAME}/{file_key}"

    @staticmethod
    def _calculate_payload_hash(file_path: str) -> str:
        """Calculate SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _create_auth_headers(
            method: str, service: str, region: str, host: str, canonical_uri: str, querystring: str,
            payload_hash: str, access_key: str, secret_key: str, content_type: str, amz_date: str, date_stamp: str,
            file_size: int
    ) -> dict:
        """Create AWS Signature V4 headers for GCore upload."""
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        def get_signature_key(key, date_stamp, region_name, service_name):
            k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
            k_region = sign(k_date, region_name)
            k_service = sign(k_region, service_name)
            k_signing = sign(k_service, 'aws4_request')
            return k_signing

        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = 'host;x-amz-content-sha256;x-amz-date'
        canonical_request = f'{method}\n{canonical_uri}\n{querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f'{date_stamp}/{region}/{service}/aws4_request'
        string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
        signing_key = get_signature_key(secret_key, date_stamp, region, service)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        authorization_header = f'{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
        headers = {
            'Authorization': authorization_header,
            'x-amz-content-sha256': payload_hash,
            'x-amz-date': amz_date,
            'Content-Type': content_type,
            'Content-Length': str(file_size)
        }
        return headers

    @staticmethod
    def get_post(post_id: int, db: Session) -> Optional[PostResponse]:
        """Retrieve a post by ID."""
        post = db.query(Post).filter(Post.id == post_id).first()
        return PostResponse.from_orm(post) if post else None

    @staticmethod
    def update_post(post_id: int, post_data: PostCreate, db: Session) -> Optional[PostResponse]:
        """Update a post."""
        db_post = db.query(Post).filter(Post.id == post_id).first()
        if not db_post:
            return None
        if post_data.content_type not in ["basic", "pro", "premium"]:
            raise HTTPException(status_code=400, detail="Invalid content_type")
        if post_data.media_type not in ["image", "video", "gif"]:
            raise HTTPException(status_code=400, detail="Invalid media_type")
        db_post.media_url = post_data.media_url
        db_post.media_type = post_data.media_type
        db_post.description = post_data.description
        db_post.content_type = post_data.content_type
        db.commit()
        db.refresh(db_post)
        return PostResponse.from_orm(db_post)

    @staticmethod
    def delete_post(post_id: int, db: Session) -> bool:
        """Delete a post and its GCore media."""
        db_post = db.query(Post).filter(Post.id == post_id).first()
        if not db_post:
            return False
        file_key = db_post.media_url.replace(f"{settings.GCORE_ENDPOINT_URL}/{settings.GCORE_BUCKET_NAME}/", "")
        method = 'DELETE'
        service = 's3'
        region = settings.GCORE_REGION_NAME
        host = f"{settings.GCORE_BUCKET_NAME}.s-ed1.cloud.gcore.lu"
        canonical_uri = f"/{file_key}"
        querystring = ''
        amz_date = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        date_stamp = datetime.utcnow().strftime('%Y%m%d')
        payload_hash = hashlib.sha256(b'').hexdigest()
        headers = PostService._create_auth_headers(
            method, service, region, host, canonical_uri, querystring, payload_hash,
            settings.GCORE_ACCESS_KEY, settings.GCORE_SECRET_KEY, None, amz_date, date_stamp, 0
        )
        url = f"https://{host}{canonical_uri}"
        response = requests.delete(url, headers=headers)
        if response.status_code != 204:
            logger.error(f"GCore delete failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500,
                                detail=f"GCore delete failed: {response.status_code} - {response.text}")
        db.delete(db_post)
        db.commit()
        return True

    @staticmethod
    def toggle_visibility(post_id: int, db: Session) -> Optional[PostResponse]:
        """Toggle post visibility."""
        db_post = db.query(Post).filter(Post.id == post_id).first()
        if not db_post:
            return None
        db_post.is_visible = not db_post.is_visible
        db.commit()
        db.refresh(db_post)
        return PostResponse.from_orm(db_post)

    @staticmethod
    def get_posts(
            user_id: Optional[int],
            content_type: Optional[str],
            media_type: Optional[str],
            db: Session
    ) -> List[PostResponse]:
        """Retrieve posts with optional filters."""
        query = db.query(Post)
        if user_id:
            query = query.filter(Post.user_id == user_id)
        if content_type:
            query = query.filter(Post.content_type == content_type)  # fresh, archive, hard
        if media_type:
            query = query.filter(Post.media_type == media_type)

        return_list = [PostResponse.from_orm(post) for post in query.all()]
        for post in return_list:
            print(post.media_url)

        return return_list

    @staticmethod
    def like_post(post_id: int, db: Session) -> None:
        """Increment post likes."""
        db_post = db.query(Post).filter(Post.id == post_id).first()
        if not db_post:
            raise HTTPException(status_code=404, detail="Post not found")
        db_post.likes = (db_post.likes or 0) + 1
        db.commit()

class CommentService:
    @staticmethod
    def create_comment(post_id: int, comment_data: CommentCreate, user_id: int, db: Session) -> CommentResponse:
        """Create a comment on a post."""
        db_post = db.query(Post).filter(Post.id == post_id).first()
        if not db_post:
            raise HTTPException(status_code=404, detail="Post not found")
        db_comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=comment_data.content
        )
        db.add(db_comment)
        db.commit()
        db.refresh(db_comment)
        return CommentResponse.from_orm(db_comment)

    @staticmethod
    def get_comments(post_id: int, db: Session) -> List[CommentResponse]:
        """Retrieve comments for a post."""
        db_post = db.query(Post).filter(Post.id == post_id).first()
        if not db_post:
            raise HTTPException(status_code=404, detail="Post not found")
        return [CommentResponse.from_orm(comment) for comment in db_post.comments]

    @staticmethod
    def update_comment(comment_id: int, comment_data: CommentCreate, user_id: int, db: Session) -> Optional[CommentResponse]:
        """Update a comment."""
        db_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.user_id == user_id).first()
        if not db_comment:
            return None
        db_comment.content = comment_data.content
        db.commit()
        db.refresh(db_comment)
        return CommentResponse.from_orm(db_comment)

    @staticmethod
    def delete_comment(comment_id: int, user_id: int, db: Session) -> bool:
        """Delete a comment."""
        db_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.user_id == user_id).first()
        if not db_comment:
            return False
        db.delete(db_comment)
        db.commit()
        return True