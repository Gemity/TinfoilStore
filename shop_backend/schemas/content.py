import uuid
from datetime import datetime

from pydantic import BaseModel, field_serializer

from shop_backend.config import VN_TZ


class ContentResponse(BaseModel):
    id: uuid.UUID
    title: str
    storage_key: str
    bucket_override: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    is_protected: bool
    is_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def serialize_to_vn(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            from datetime import timezone
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(VN_TZ).isoformat()


class DownloadResponse(BaseModel):
    content_id: uuid.UUID
    download_url: str
    expires_in_seconds: int


class ContentCreate(BaseModel):
    title: str
    storage_key: str
    bucket_override: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    is_protected: bool = True


class ContentUpdate(BaseModel):
    title: str | None = None
    storage_key: str | None = None
    bucket_override: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    is_protected: bool | None = None
    is_enabled: bool | None = None
