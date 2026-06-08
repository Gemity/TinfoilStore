import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shop_backend.api.deps import get_db, require_admin
from shop_backend.db.models import User
from shop_backend.schemas.content import ContentCreate, ContentResponse, ContentUpdate
from shop_backend.schemas.ftp import FtpUserCreate, FtpUserResponse, FtpUserUpdate
from shop_backend.schemas.subscriptions import (
    ExtendSubscriptionRequest,
    GrantSubscriptionRequest,
    RevokeSubscriptionRequest,
    SubscriptionResponse,
)
from shop_backend.schemas.users import UserCreate, UserResponse
from shop_backend.services import content_admin_service, ftp_user_service, subscription_service, user_service
from shop_backend.services.subscription_service import get_effective_status

router = APIRouter(tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def admin_list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        user = user_service.create_user(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return user


@router.get("/users/search", response_model=list[UserResponse])
def admin_search_users(username: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).filter(User.username.ilike(f"%{username}%")).all()


@router.post("/subscriptions/{user_id}/grant", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def admin_grant_subscription(
    user_id: uuid.UUID,
    body: GrantSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    try:
        sub = subscription_service.grant_subscription(
            db,
            user_id,
            body.days,
            actor.id,
            hours=body.hours,
            minutes=body.minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _sub_response(sub)


@router.post("/subscriptions/{user_id}/extend", response_model=SubscriptionResponse)
def admin_extend_subscription(
    user_id: uuid.UUID,
    body: ExtendSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    try:
        sub = subscription_service.extend_subscription(
            db,
            user_id,
            body.days,
            body.notes,
            actor.id,
            hours=body.hours,
            minutes=body.minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _sub_response(sub)


@router.post("/subscriptions/{user_id}/revoke", response_model=SubscriptionResponse)
def admin_revoke_subscription(
    user_id: uuid.UUID,
    body: RevokeSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    try:
        sub = subscription_service.revoke_subscription(db, user_id, body.reason, actor.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _sub_response(sub)




# FTP user management


@router.get("/ftp-users", response_model=list[FtpUserResponse])
def admin_list_ftp_users(_: User = Depends(require_admin)):
    return ftp_user_service.list_ftp_users()


@router.post("/ftp-users", response_model=FtpUserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_ftp_user(body: FtpUserCreate, _: User = Depends(require_admin)):
    try:
        return ftp_user_service.create_ftp_user(body.username, body.password, body.is_active)
    except ftp_user_service.FtpUserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/ftp-users/{username}", response_model=FtpUserResponse)
def admin_get_ftp_user(username: str, _: User = Depends(require_admin)):
    try:
        return ftp_user_service.get_ftp_user(username)
    except (LookupError, ftp_user_service.FtpUserError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/ftp-users/{username}", response_model=FtpUserResponse)
def admin_update_ftp_user(username: str, body: FtpUserUpdate, _: User = Depends(require_admin)):
    try:
        return ftp_user_service.update_ftp_user(username, password=body.password, is_active=body.is_active)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ftp_user_service.FtpUserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/ftp-users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_ftp_user(username: str, _: User = Depends(require_admin)):
    try:
        ftp_user_service.delete_ftp_user(username)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ftp_user_service.FtpUserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

# Content management


@router.get("/content", response_model=list[ContentResponse])
def admin_list_content(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return content_admin_service.list_all_content(db)


@router.post("/content", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
def admin_create_content(body: ContentCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return content_admin_service.create_content(db, body)


@router.get("/content/{content_id}", response_model=ContentResponse)
def admin_get_content(content_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        return content_admin_service.get_content(db, content_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/content/{content_id}", response_model=ContentResponse)
def admin_update_content(
    content_id: uuid.UUID,
    body: ContentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        return content_admin_service.update_content(db, content_id, body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/content/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_content(content_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        content_admin_service.delete_content(db, content_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/icon-debug/{title_id}")
def admin_icon_debug(title_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    from shop_backend.services.shop_service import build_icon_debug_info

    return build_icon_debug_info(db, title_id)


# Sync Wasabi -> DB


@router.post("/sync")
def admin_sync_content(
    prefix: str = "",
    cleanup: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Scan Wasabi bucket, sync game files to DB, then warm local icon cache."""
    from shop_backend.sync_content import sync_with_session
    from shop_backend.services.shop_service import cache_titledb_assets_for_content

    sync_result = sync_with_session(db, prefix=prefix, cleanup=cleanup)
    asset_cache = cache_titledb_assets_for_content(db)
    return {
        "message": "Sync completed and local icon cache warmed.",
        "sync": sync_result,
        "asset_cache": asset_cache,
    }


# Helpers


def _sub_response(sub) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        status=sub.status.value,
        starts_at=sub.starts_at,
        ends_at=sub.ends_at,
        revoked_at=sub.revoked_at,
        revoked_reason=sub.revoked_reason,
        effective_status=get_effective_status(sub),
    )

