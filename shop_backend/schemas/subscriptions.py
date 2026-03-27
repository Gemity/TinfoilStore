import uuid
from datetime import datetime

from pydantic import BaseModel


class GrantSubscriptionRequest(BaseModel):
    days: int


class ExtendSubscriptionRequest(BaseModel):
    days: int
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
