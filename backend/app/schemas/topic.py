from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Keyword ──────────────────────────────────────────────────────────────────

class KeywordCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=500)


class KeywordRead(BaseModel):
    id: uuid.UUID
    mother_keyword_id: uuid.UUID
    owner_id: uuid.UUID | None
    keyword: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── MotherKeyword ────────────────────────────────────────────────────────────

class MotherKeywordCreate(BaseModel):
    names: list[str] = Field(min_length=1)


class MotherKeywordPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class MotherKeywordRead(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    owner_id: uuid.UUID | None
    name: str
    gen_status: str = "idle"
    gen_error: str | None = None
    keywords: list[KeywordRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Topic ────────────────────────────────────────────────────────────────────

class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TopicPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class TopicRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    name: str
    mother_keywords: list[MotherKeywordRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListItem(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID | None
    name: str
    mother_keyword_count: int = 0
    keyword_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    items: list[TopicListItem]
    total: int
    page: int
    page_size: int


class MotherKeywordListResponse(BaseModel):
    items: list[MotherKeywordRead]
    total: int
    page: int
    page_size: int


class TopicGenStatus(BaseModel):
    total: int = 0
    idle: int = 0
    pending: int = 0
    generating: int = 0
    done: int = 0
    failed: int = 0


# ── Keyword gen config ───────────────────────────────────────────────────────

class KeywordGenConfigPayload(BaseModel):
    keyword_gen_model: str | None = None
    keyword_gen_prompt: str | None = None
    keyword_gen_count: int | None = None
    keyword_gen_temperature: float | None = None
