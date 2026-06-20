from datetime import datetime

from pydantic import BaseModel, Field


class AdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class AdminPasswordUpdate(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class AdminResponse(BaseModel):
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime | None = None
