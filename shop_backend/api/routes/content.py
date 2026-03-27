import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shop_backend.api.deps import get_current_user, get_db
from shop_backend.db.models import User
from shop_backend.schemas.content import ContentResponse, DownloadResponse
from shop_backend.services import content_service
from shop_backend.config import settings

router = APIRouter(tags=["content"])


@router.get("", response_model=list[ContentResponse])
def list_content(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        items = content_service.list_content(db, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return items


@router.get("/{content_id}/download", response_model=DownloadResponse)
def download_content(
    content_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        obj, url = content_service.get_download_url(db, current_user.id, content_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return DownloadResponse(
        content_id=obj.id,
        download_url=url,
        expires_in_seconds=settings.WASABI_PRESIGN_TTL_SECONDS,
    )
