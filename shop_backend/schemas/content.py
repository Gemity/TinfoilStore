import uuid
from datetime import datetime

from pydantic import BaseModel


class ContentResponse(BaseModel):
    id: uuid.UUID
    title: str
    mime_type: str | None
    size_bytes: int | None
    is_protected: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DownloadResponse(BaseModel):
    content_id: uuid.UUID
    download_url: str
    expires_in_seconds: int
