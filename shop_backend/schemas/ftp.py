from pydantic import BaseModel, Field


class FtpUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=6, max_length=128)
    is_active: bool = True


class FtpUserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    is_active: bool | None = None


class FtpUserResponse(BaseModel):
    username: str
    is_active: bool
    home: str
    shell: str
    group: str
