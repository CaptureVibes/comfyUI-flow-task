from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfile(BaseModel):
    """User profile for display."""
    id: uuid.UUID
    username: str
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """Request body for updating user's own profile."""
    display_name: str | None = Field(None, max_length=80)
    bio: str | None = Field(None, max_length=500)
    avatar_url: str | None = Field(None, max_length=500_000)  # base64 data-url can be long


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6)
    is_admin: bool = False


class UserChangePassword(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class UserListResponse(BaseModel):
    items: list[UserRead]
    total: int


class UserDeleteResponse(BaseModel):
    ok: bool = True
