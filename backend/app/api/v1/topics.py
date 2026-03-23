from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.topic import (
    KeywordCreate,
    KeywordRead,
    MotherKeywordCreate,
    MotherKeywordListResponse,
    MotherKeywordPatch,
    MotherKeywordRead,
    TopicCreate,
    TopicGenStatus,
    TopicListItem,
    TopicListResponse,
    TopicPatch,
    TopicRead,
)
from app.services.topic_service import (
    batch_generate_keywords_for_topic,
    create_keyword,
    create_mother_keywords,
    create_topic,
    delete_keyword,
    delete_mother_keyword,
    delete_topic,
    generate_keywords_for_mother_keyword,
    get_mother_keyword_or_404,
    get_topic_or_404,
    get_topic_gen_status,
    list_mother_keywords,
    list_topics,
    patch_mother_keyword,
    patch_topic,
)

router = APIRouter(prefix="/topics", tags=["topics"])


def _get_owner_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID | None:
    return None if current_user.is_admin else current_user.user_id


def _get_creator_id(current_user: TokenData = Depends(get_current_user)) -> uuid.UUID:
    return current_user.user_id


# ── Topic CRUD ───────────────────────────────────────────────────────────────

@router.post("", response_model=TopicRead, status_code=201)
async def create_topic_endpoint(
    payload: TopicCreate,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> TopicRead:
    topic = await create_topic(session, payload.name, creator_id)
    return TopicRead.model_validate(topic)


@router.get("", response_model=TopicListResponse)
async def list_topics_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=9999),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TopicListResponse:
    items, total = await list_topics(session, page=page, page_size=page_size, owner_id=owner_id)
    list_items = []
    for t in items:
        mk_count = len(t.mother_keywords)
        kw_count = sum(len(mk.keywords) for mk in t.mother_keywords)
        list_items.append(TopicListItem(
            id=t.id,
            owner_id=t.owner_id,
            name=t.name,
            mother_keyword_count=mk_count,
            keyword_count=kw_count,
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))
    return TopicListResponse(items=list_items, total=total, page=page, page_size=page_size)


@router.get("/{topic_id}", response_model=TopicRead)
async def get_topic_endpoint(
    topic_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TopicRead:
    topic = await get_topic_or_404(session, topic_id, owner_id)
    return TopicRead.model_validate(topic)


@router.patch("/{topic_id}", response_model=TopicRead)
async def patch_topic_endpoint(
    topic_id: uuid.UUID,
    payload: TopicPatch,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TopicRead:
    topic = await get_topic_or_404(session, topic_id, owner_id)
    topic = await patch_topic(session, topic, payload.name)
    topic = await get_topic_or_404(session, topic_id, owner_id)
    return TopicRead.model_validate(topic)


@router.delete("/{topic_id}")
async def delete_topic_endpoint(
    topic_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await delete_topic(session, topic_id, owner_id)
    return Response(status_code=204)


# ── Mother Keywords (paginated list + gen status) ────────────────────────────

@router.get("/{topic_id}/mother-keywords", response_model=MotherKeywordListResponse)
async def list_mother_keywords_endpoint(
    topic_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=9999),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> MotherKeywordListResponse:
    items, total = await list_mother_keywords(
        session, topic_id, page=page, page_size=page_size, owner_id=owner_id,
    )
    return MotherKeywordListResponse(
        items=[MotherKeywordRead.model_validate(mk) for mk in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{topic_id}/gen-status", response_model=TopicGenStatus)
async def get_gen_status_endpoint(
    topic_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> TopicGenStatus:
    counts = await get_topic_gen_status(session, topic_id, owner_id)
    return TopicGenStatus(**counts)


# ── MotherKeyword CRUD ───────────────────────────────────────────────────────

@router.post("/{topic_id}/mother-keywords", response_model=list[MotherKeywordRead], status_code=201)
async def create_mother_keyword_endpoint(
    topic_id: uuid.UUID,
    payload: MotherKeywordCreate,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> list[MotherKeywordRead]:
    await get_topic_or_404(session, topic_id, owner_id)
    mks = await create_mother_keywords(session, topic_id, payload.names, creator_id)
    return [MotherKeywordRead.model_validate(mk) for mk in mks]


@router.patch("/mother-keywords/{mk_id}", response_model=MotherKeywordRead)
async def patch_mother_keyword_endpoint(
    mk_id: uuid.UUID,
    payload: MotherKeywordPatch,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> MotherKeywordRead:
    mk = await get_mother_keyword_or_404(session, mk_id, owner_id)
    mk = await patch_mother_keyword(session, mk, payload.name)
    mk = await get_mother_keyword_or_404(session, mk_id, owner_id)
    return MotherKeywordRead.model_validate(mk)


@router.delete("/mother-keywords/{mk_id}")
async def delete_mother_keyword_endpoint(
    mk_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await delete_mother_keyword(session, mk_id, owner_id)
    return Response(status_code=204)


# ── Keyword CRUD ─────────────────────────────────────────────────────────────

@router.post("/mother-keywords/{mk_id}/keywords", response_model=KeywordRead, status_code=201)
async def create_keyword_endpoint(
    mk_id: uuid.UUID,
    payload: KeywordCreate,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> KeywordRead:
    await get_mother_keyword_or_404(session, mk_id, owner_id)
    kw = await create_keyword(session, mk_id, payload.keyword, creator_id)
    return KeywordRead.model_validate(kw)


@router.delete("/keywords/{kw_id}")
async def delete_keyword_endpoint(
    kw_id: uuid.UUID,
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await delete_keyword(session, kw_id, owner_id)
    return Response(status_code=204)


# ── AI Keyword Generation ────────────────────────────────────────────────────

@router.post("/mother-keywords/{mk_id}/generate-keywords")
async def generate_keywords_endpoint(
    mk_id: uuid.UUID,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await generate_keywords_for_mother_keyword(session, mk_id, creator_id)
    return {"status": "queued"}


@router.post("/{topic_id}/batch-generate-keywords")
async def batch_generate_keywords_endpoint(
    topic_id: uuid.UUID,
    creator_id: uuid.UUID = Depends(_get_creator_id),
    owner_id: uuid.UUID | None = Depends(_get_owner_id),
    session: AsyncSession = Depends(get_db),
) -> dict:
    count = await batch_generate_keywords_for_topic(session, topic_id, creator_id)
    return {"queued": count}
