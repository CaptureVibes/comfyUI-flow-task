from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class SocialBindingYouTube(BaseModel):
    platform: Literal["youtube"]
    channel_id: str = ""
    api_key: str = ""
    refresh_token: str = ""


class SocialBindingTikTok(BaseModel):
    platform: Literal["tiktok"]
    open_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_in: int = 0


class SocialBindingInstagram(BaseModel):
    platform: Literal["instagram"]
    user_id: str = ""
    access_token: str = ""
    account_type: str = ""


SocialBinding = Annotated[
    Union[SocialBindingYouTube, SocialBindingTikTok, SocialBindingInstagram],
    Field(discriminator="platform"),
]


class AccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=200)
    style_description: str | None = None
    model_appearance: str | None = None
    avatar_url: str | None = None
    social_bindings: list[dict] | None = None


class AccountPatch(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=200)
    style_description: str | None = None
    model_appearance: str | None = None
    avatar_url: str | None = None
    social_bindings: list[dict] | None = None


class AccountRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    account_name: str
    style_description: str | None
    model_appearance: str | None
    avatar_url: str | None
    social_bindings: list | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountListResponse(BaseModel):
    items: list[AccountRead]
    total: int
    page: int
    page_size: int
