import uuid
from datetime import datetime

from pydantic import BaseModel, field_serializer

from shop_backend.config import VN_TZ


class GrantSubscriptionRequest(BaseModel):
    days: int = 0
    hours: int = 0
    minutes: int = 0


class ExtendSubscriptionRequest(BaseModel):
    days: int = 0
    hours: int = 0
    minutes: int = 0
    notes: str = ""


class RevokeSubscriptionRequest(BaseModel):
    reason: str = ""


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    starts_at: datetime
    ends_at: datetime
    revoked_at: datetime | None
    revoked_reason: str | None
    effective_status: str

    model_config = {"from_attributes": True}

    @field_serializer("starts_at", "ends_at", "revoked_at")
    def serialize_to_vn(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            from datetime import timezone
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(VN_TZ).isoformat()
