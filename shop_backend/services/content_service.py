import uuid

from sqlalchemy.orm import Session

from shop_backend.db.models import ContentObject
from shop_backend.services.subscription_service import get_active_subscription
from shop_backend.storage.wasabi import generate_presigned_url
from shop_backend.config import settings


def list_content(db: Session, user_id: uuid.UUID) -> list[ContentObject]:
    _require_active_subscription(db, user_id)
    return (
        db.query(ContentObject)
        .filter(ContentObject.is_enabled.is_(True))
        .order_by(ContentObject.created_at.desc())
        .all()
    )


def get_download_url(db: Session, user_id: uuid.UUID, content_id: uuid.UUID) -> tuple[ContentObject, str]:
    _require_active_subscription(db, user_id)
    obj = db.query(ContentObject).filter(ContentObject.id == content_id, ContentObject.is_enabled.is_(True)).first()
    if not obj:
        raise LookupError(f"Content {content_id} not found")
    if obj.is_protected:
        url = generate_presigned_url(
            storage_key=obj.storage_key,
            bucket_override=obj.bucket_override,
            ttl_seconds=settings.WASABI_PRESIGN_TTL_SECONDS,
        )
    else:
        url = f"{settings.WASABI_ENDPOINT_URL}/{obj.bucket_override or settings.WASABI_BUCKET}/{obj.storage_key}"
    return obj, url


def _require_active_subscription(db: Session, user_id: uuid.UUID) -> None:
    sub = get_active_subscription(db, user_id)
    if not sub:
        raise PermissionError("No active subscription")
