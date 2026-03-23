from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.pipeline_setting import PipelineSetting
from app.models.system_setting import SystemSetting
from app.models.topic import Keyword, MotherKeyword, Topic
from app.services.evolink_api import call_evolink_gemini_api

logger = logging.getLogger("app.topics")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Topic CRUD ───────────────────────────────────────────────────────────────

async def create_topic(session: AsyncSession, name: str, owner_id: uuid.UUID) -> Topic:
    now = _utcnow()
    topic = Topic(name=name, owner_id=owner_id, created_at=now, updated_at=now)
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


async def list_topics(
    session: AsyncSession, *, page: int = 1, page_size: int = 20, owner_id: uuid.UUID | None = None
) -> tuple[list[Topic], int]:
    base = select(Topic)
    if owner_id is not None:
        base = base.where(Topic.owner_id == owner_id)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))

    stmt = (
        base
        .options(selectinload(Topic.mother_keywords).selectinload(MotherKeyword.keywords))
        .order_by(Topic.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total or 0


async def get_topic_or_404(
    session: AsyncSession, topic_id: uuid.UUID, owner_id: uuid.UUID | None = None
) -> Topic:
    stmt = (
        select(Topic)
        .options(selectinload(Topic.mother_keywords).selectinload(MotherKeyword.keywords))
        .where(Topic.id == topic_id)
    )
    topic = await session.scalar(stmt)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    if owner_id is not None and topic.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic


async def patch_topic(session: AsyncSession, topic: Topic, name: str | None) -> Topic:
    if name is not None:
        topic.name = name
    await session.commit()
    await session.refresh(topic)
    return topic


async def delete_topic(session: AsyncSession, topic_id: uuid.UUID, owner_id: uuid.UUID | None = None) -> None:
    topic = await get_topic_or_404(session, topic_id, owner_id)
    await session.delete(topic)
    await session.commit()


# ── MotherKeyword CRUD ───────────────────────────────────────────────────────

async def create_mother_keywords(
    session: AsyncSession, topic_id: uuid.UUID, names: list[str], owner_id: uuid.UUID
) -> list[MotherKeyword]:
    now = _utcnow()
    mks = []
    for name in names:
        stripped = name.strip()
        if not stripped:
            continue
        mk = MotherKeyword(topic_id=topic_id, name=stripped, owner_id=owner_id, created_at=now, updated_at=now)
        session.add(mk)
        mks.append(mk)
    await session.commit()
    for mk in mks:
        await session.refresh(mk)
    return mks


async def get_mother_keyword_or_404(
    session: AsyncSession, mk_id: uuid.UUID, owner_id: uuid.UUID | None = None
) -> MotherKeyword:
    stmt = (
        select(MotherKeyword)
        .options(selectinload(MotherKeyword.keywords))
        .where(MotherKeyword.id == mk_id)
    )
    mk = await session.scalar(stmt)
    if not mk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MotherKeyword not found")
    if owner_id is not None and mk.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MotherKeyword not found")
    return mk


async def patch_mother_keyword(session: AsyncSession, mk: MotherKeyword, name: str | None) -> MotherKeyword:
    if name is not None:
        mk.name = name
    await session.commit()
    await session.refresh(mk)
    return mk


async def delete_mother_keyword(session: AsyncSession, mk_id: uuid.UUID, owner_id: uuid.UUID | None = None) -> None:
    mk = await get_mother_keyword_or_404(session, mk_id, owner_id)
    await session.delete(mk)
    await session.commit()


async def list_mother_keywords(
    session: AsyncSession, topic_id: uuid.UUID, *,
    page: int = 1, page_size: int = 20, owner_id: uuid.UUID | None = None,
) -> tuple[list[MotherKeyword], int]:
    """Paginated mother keywords for a topic."""
    base = select(MotherKeyword).where(MotherKeyword.topic_id == topic_id)
    if owner_id is not None:
        base = base.where(MotherKeyword.owner_id == owner_id)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))

    stmt = (
        base
        .options(selectinload(MotherKeyword.keywords))
        .order_by(MotherKeyword.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total or 0


async def get_topic_gen_status(
    session: AsyncSession, topic_id: uuid.UUID, owner_id: uuid.UUID | None = None,
) -> dict:
    """Return generation status counts for a topic's mother keywords."""
    base = select(MotherKeyword.gen_status, func.count()).where(
        MotherKeyword.topic_id == topic_id
    )
    if owner_id is not None:
        base = base.where(MotherKeyword.owner_id == owner_id)
    base = base.group_by(MotherKeyword.gen_status)

    rows = (await session.execute(base)).all()
    counts = {status: cnt for status, cnt in rows}
    return {
        "total": sum(counts.values()),
        "idle": counts.get("idle", 0),
        "pending": counts.get("pending", 0),
        "generating": counts.get("generating", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
    }


# ── Keyword CRUD ─────────────────────────────────────────────────────────────

async def create_keyword(
    session: AsyncSession, mother_keyword_id: uuid.UUID, keyword_text: str, owner_id: uuid.UUID
) -> Keyword:
    kw = Keyword(
        mother_keyword_id=mother_keyword_id,
        keyword=keyword_text,
        owner_id=owner_id,
        created_at=_utcnow(),
    )
    session.add(kw)
    await session.commit()
    await session.refresh(kw)
    return kw


async def delete_keyword(session: AsyncSession, kw_id: uuid.UUID, owner_id: uuid.UUID | None = None) -> None:
    stmt = select(Keyword).where(Keyword.id == kw_id)
    kw = await session.scalar(stmt)
    if not kw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    if owner_id is not None and kw.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    await session.delete(kw)
    await session.commit()


# ── AI Keyword Generation (queue-based) ─────────────────────────────────────

_JSON_SUFFIX = """

你必须严格以以下 JSON 格式输出，不要输出任何其他内容：
{"keywords": ["关键词1", "关键词2", ...]}
"""

_CONCURRENCY = 3
_semaphore = asyncio.Semaphore(_CONCURRENCY)


async def _load_gen_config(session: AsyncSession, owner_id: uuid.UUID) -> dict:
    """Load EvoLink + pipeline config needed for keyword generation."""
    system_row = await session.scalar(select(SystemSetting).limit(1))
    if not system_row or not system_row.evolink_api_key:
        raise ValueError("EvoLink API key not configured")

    pipeline_row = await session.scalar(
        select(PipelineSetting).where(PipelineSetting.owner_id == owner_id)
    )
    if not pipeline_row or not pipeline_row.keyword_gen_prompt:
        raise ValueError("Keyword generation prompt not configured")

    return {
        "api_key": system_row.evolink_api_key,
        "api_base_url": system_row.evolink_api_base_url,
        "model_name": pipeline_row.keyword_gen_model,
        "prompt_template": pipeline_row.keyword_gen_prompt,
        "keyword_count": pipeline_row.keyword_gen_count,
        "temperature": pipeline_row.keyword_gen_temperature,
    }


def _parse_keywords_from_text(text: str) -> list[str]:
    """Parse keyword list from AI response (handles markdown code fences)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    result = json.loads(cleaned)
    keyword_list = result.get("keywords", [])
    if not isinstance(keyword_list, list):
        raise ValueError("AI returned invalid keyword format")
    return [kw.strip() for kw in keyword_list if isinstance(kw, str) and kw.strip()]


async def _generate_one(mk_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    """Generate keywords for a single mother keyword (runs in background with semaphore)."""
    async with _semaphore:
        async with SessionLocal() as session:
            # Mark as generating
            mk = await session.scalar(
                select(MotherKeyword).options(selectinload(MotherKeyword.keywords)).where(MotherKeyword.id == mk_id)
            )
            if not mk:
                return
            mk.gen_status = "generating"
            mk.gen_error = None
            await session.commit()

            try:
                config = await _load_gen_config(session, owner_id)

                prompt = config["prompt_template"].replace("{keyword}", mk.name)
                prompt = prompt.replace("{count}", str(config["keyword_count"]))
                prompt += _JSON_SUFFIX

                text = await call_evolink_gemini_api(
                    api_base_url=config["api_base_url"],
                    api_key=config["api_key"],
                    model_name=config["model_name"],
                    prompt=prompt,
                    temperature=config["temperature"],
                )

                logger.info("Keyword gen response for [%s]: %s", mk.name, text[:500])
                keyword_list = _parse_keywords_from_text(text)

                now = _utcnow()
                for kw_text in keyword_list:
                    session.add(Keyword(
                        mother_keyword_id=mk_id,
                        keyword=kw_text,
                        owner_id=owner_id,
                        created_at=now,
                    ))

                mk.gen_status = "done"
                mk.gen_error = None
                await session.commit()
                logger.info("Generated %d keywords for mother_keyword [%s]", len(keyword_list), mk.name)

            except Exception as exc:
                logger.error("Keyword gen failed for [%s]: %s", mk.name, exc)
                mk.gen_status = "failed"
                mk.gen_error = str(exc)[:500]
                await session.commit()


async def generate_keywords_for_mother_keyword(
    session: AsyncSession, mk_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Enqueue a single mother keyword for AI generation (fire-and-forget)."""
    mk = await get_mother_keyword_or_404(session, mk_id, owner_id)
    if mk.gen_status == "generating" or mk.gen_status == "pending":
        return  # already in progress
    mk.gen_status = "pending"
    mk.gen_error = None
    await session.commit()
    asyncio.create_task(_generate_one(mk_id, owner_id))


async def batch_generate_keywords_for_topic(
    session: AsyncSession, topic_id: uuid.UUID, owner_id: uuid.UUID
) -> int:
    """Enqueue all mother keywords that need generation. Returns count enqueued."""
    topic = await get_topic_or_404(session, topic_id, owner_id)
    count = 0
    for mk in topic.mother_keywords:
        # Skip if already has keywords (done) or is in progress
        if mk.keywords and mk.gen_status == "done":
            continue
        if mk.gen_status in ("generating", "pending"):
            continue
        mk.gen_status = "pending"
        mk.gen_error = None
        count += 1
    await session.commit()

    # Fire background tasks for each pending mk
    for mk in topic.mother_keywords:
        if mk.gen_status == "pending":
            asyncio.create_task(_generate_one(mk.id, owner_id or mk.owner_id))

    return count


async def recover_stuck_keyword_gen_on_startup() -> None:
    """Reset 'generating'/'pending' mother keywords to 'idle' and re-enqueue them."""
    async with SessionLocal() as session:
        stmt = (
            select(MotherKeyword)
            .where(MotherKeyword.gen_status.in_(["generating", "pending"]))
        )
        stuck = (await session.execute(stmt)).scalars().all()
        if not stuck:
            logger.info("No stuck keyword gen tasks found on startup")
            return

        logger.info("Found %d stuck keyword gen tasks, re-enqueueing...", len(stuck))
        for mk in stuck:
            mk.gen_status = "pending"
            mk.gen_error = None
        await session.commit()

        for mk in stuck:
            asyncio.create_task(_generate_one(mk.id, mk.owner_id))
