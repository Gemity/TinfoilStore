import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shop_backend.api.deps import get_db, require_admin
from shop_backend.db.models import User
from shop_backend.schemas.subscriptions import (
    ExtendSubscriptionRequest,
    GrantSubscriptionRequest,
    RevokeSubscriptionRequest,
    SubscriptionResponse,
)
from shop_backend.schemas.users import UserCreate, UserResponse
from shop_backend.services import subscription_service, user_service
from shop_backend.services.subscription_service import get_effective_status

router = APIRouter(tags=["admin"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        user = user_service.create_user(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
def admin_get_user(user_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        user = user_service.get_user_by_id(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return user


@router.post("/subscriptions/{user_id}/grant", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def admin_grant_subscription(
    user_id: uuid.UUID,
    body: GrantSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    sub = subscription_service.grant_subscription(db, user_id, body.days, actor.id)
    return _sub_response(sub)


@router.post("/subscriptions/{user_id}/extend", response_model=SubscriptionResponse)
def admin_extend_subscription(
    user_id: uuid.UUID,
    body: ExtendSubscriptionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
):
    try:
        sub = subscription_service.extend_subscription(db, user_id, body.days, body.notes, actor.id)
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
