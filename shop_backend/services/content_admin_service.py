"""Admin operations for content objects (CRUD)."""

import uuid

from sqlalchemy.orm import Session

from shop_backend.db.models import ContentObject
from shop_backend.schemas.content import ContentCreate, ContentUpdate


def create_content(db: Session, data: ContentCreate) -> ContentObject:
    obj = ContentObject(
        title=data.title,
        storage_key=data.storage_key,
        bucket_override=data.bucket_override,
        mime_type=data.mime_type,
        size_bytes=data.size_bytes,
        sha256=data.sha256,
        is_protected=data.is_protected,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_content(db: Session, content_id: uuid.UUID, data: ContentUpdate) -> ContentObject:
    obj = db.query(ContentObject).filter(ContentObject.id == content_id).first()
    if not obj:
        raise LookupError(f"Content {content_id} not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_content(db: Session, content_id: uuid.UUID) -> None:
    obj = db.query(ContentObject).filter(ContentObject.id == content_id).first()
    if not obj:
        raise LookupError(f"Content {content_id} not found")
    db.delete(obj)
    db.commit()


def get_content(db: Session, content_id: uuid.UUID) -> ContentObject:
    obj = db.query(ContentObject).filter(ContentObject.id == content_id).first()
    if not obj:
        raise LookupError(f"Content {content_id} not found")
    return obj


def list_all_content(db: Session) -> list[ContentObject]:
    return (
        db.query(ContentObject)
        .order_by(ContentObject.created_at.desc())
        .all()
    )
