import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_serializer

from shop_backend.config import VN_TZ


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
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
