import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from shop_backend.api.deps import get_db, require_admin
from shop_backend.db.models import User, UserRole
from shop_backend.schemas.ftp import FtpUserCreate, FtpUserUpdate
from shop_backend.schemas.subscriptions import (
    ExtendSubscriptionRequest,
    GrantSubscriptionRequest,
    RevokeSubscriptionRequest,
    SubscriptionResponse,
)
from shop_backend.services import ftp_index_service, ftp_user_service, subscription_service
from shop_backend.services.subscription_service import get_effective_status
from shop_backend.security.password import hash_password

router = APIRouter(tags=["admin"])


@router.get("/content")
def admin_list_content(max_items: int = 500, _: User = Depends(require_admin)):
    return ftp_index_service.list_ftp_content(max_items=max_items)


@router.post("/sync")
def admin_sync_content(prefix: str = "", cleanup: bool = False, _: User = Depends(require_admin)):
    try:
        result = ftp_index_service.refresh_ftp_index()
    except ftp_index_service.FtpIndexError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    result["legacy_parameters"] = {
        "prefix": prefix,
        "cleanup": cleanup,
        "note": "Ignored for FTP shop. This endpoint refreshes the FTP index.",
    }
    return result


@router.get("/ftp-users")
def admin_list_ftp_users(
    username: str = Query(default="", description="Optional partial username search"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ftp_users = ftp_user_service.list_ftp_users()
    if username:
        needle = username.casefold()
        ftp_users = [item for item in ftp_users if needle in item["username"].casefold()]
    return [_ftp_user_with_subscription(db, item) for item in ftp_users]


@router.post("/ftp-users", status_code=status.HTTP_201_CREATED)
def admin_create_ftp_user(body: FtpUserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        ftp_user = ftp_user_service.create_ftp_user(body.username, body.password, body.is_active)
    except ftp_user_service.FtpUserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _ensure_subscription_user(db, body.username, password=body.password)
    return _ftp_user_with_subscription(db, ftp_user)


@router.post(
    "/ftp-users/{username}/subscription/grant",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_grant_ftp_user_subscription(
    username: str,
    body: GrantSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    user = _ensure_subscription_user(db, username)
    try:
        sub = subscription_service.grant_subscription(
            db,
            user.id,
            body.days,
            actor.id,
            hours=body.hours,
            minutes=body.minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _sub_response(sub)


@router.post("/ftp-users/{username}/subscription/extend", response_model=SubscriptionResponse)
def admin_extend_ftp_user_subscription(
    username: str,
    body: ExtendSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    user = _ensure_subscription_user(db, username)
    try:
        sub = subscription_service.extend_subscription(
            db,
            user.id,
            body.days,
            body.notes,
            actor.id,
            hours=body.hours,
            minutes=body.minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _sub_response(sub)


@router.post("/ftp-users/{username}/subscription/revoke", response_model=SubscriptionResponse)
def admin_revoke_ftp_user_subscription(
    username: str,
    body: RevokeSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    user = _ensure_subscription_user(db, username)
    try:
        sub = subscription_service.revoke_subscription(db, user.id, body.reason, actor.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _sub_response(sub)


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


@router.get("/ftp-users/{username}", include_in_schema=False)
def admin_get_ftp_user(username: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        return _ftp_user_with_subscription(db, ftp_user_service.get_ftp_user(username))
    except (LookupError, ftp_user_service.FtpUserError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/ftp-users/{username}")
def admin_update_ftp_user(username: str, body: FtpUserUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        ftp_user = ftp_user_service.update_ftp_user(username, password=body.password, is_active=body.is_active)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ftp_user_service.FtpUserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if body.password is not None:
        _ensure_subscription_user(db, username, password=body.password)
    return _ftp_user_with_subscription(db, ftp_user)


@router.delete("/ftp-users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_ftp_user(username: str, _: User = Depends(require_admin)):
    try:
        ftp_user_service.delete_ftp_user(username)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ftp_user_service.FtpUserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _ensure_subscription_user(db: Session, username: str, password: str | None = None) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user

    user = User(
        username=username,
        email=f"{username}@ftp.local",
        password_hash=hash_password(password or f"ftp-{uuid.uuid4()}"),
        role=UserRole.user,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _subscription_snapshot(user: User | None) -> dict | None:
    if not user or not user.subscriptions:
        return {
            "subscription_status": "none",
            "ends_at": None,
            "days_remaining": None,
            "revoked_reason": None,
        }
    sub = user.subscriptions[0]
    status = get_effective_status(sub)
    ends_at = sub.ends_at
    days_remaining = None
    if ends_at:
        ends_at_aware = ends_at if ends_at.tzinfo else ends_at.replace(tzinfo=timezone.utc)
        remaining_seconds = (ends_at_aware - datetime.now(tz=timezone.utc)).total_seconds()
        days_remaining = max(0, int(remaining_seconds // 86400))
    return {
        "subscription_status": status,
        "ends_at": ends_at,
        "days_remaining": days_remaining,
        "revoked_reason": sub.revoked_reason,
    }


def _ftp_user_with_subscription(db: Session, ftp_user: dict) -> dict:
    user = db.query(User).filter(User.username == ftp_user["username"]).first()
    subscription = _subscription_snapshot(user)
    return {
        "username": ftp_user["username"],
        "ftp_active": ftp_user["is_active"],
        **subscription,
    }
