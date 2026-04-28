"""视频分类服务：调用 Gemini 对单个视频归类，并按 AI 博主聚合大类比例。"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.account_blogger_binding import AccountBloggerBinding
from app.models.tiktok_blogger import TiktokBlogger
from app.models.video_classification import VideoClassification
from app.models.video_source import VideoSource

logger = logging.getLogger("app.video_classification")

# =============================================================================
# 14 个分类 → 4 大类
# =============================================================================

_CATEGORIES: list[tuple[int, str, str]] = [
    (0, "单套衣服展示美", "display"),
    (1, "换装展示美", "display"),
    (2, "镜头感或表演型展示美", "display"),
    (3, "生活场景中的展示美", "display"),
    (4, "单品语言讲解", "knowledge"),
    (5, "造型选择或对比", "knowledge"),
    (6, "搭配教程或方法论", "knowledge"),
    (7, "单品展示无人讲解", "knowledge"),
    (8, "单品展示字幕讲解", "knowledge"),
    (9, "人生故事", "persona"),
    (10, "人生阶段", "persona"),
    (11, "个人态度表达", "persona"),
    (12, "热门梗段子反转梗流行文案", "trending"),
    (13, "明星影视综艺节日社会话题相关穿搭", "trending"),
]

CATEGORY_LABELS: dict[int, str] = {idx: label for idx, label, _ in _CATEGORIES}
CATEGORY_MAJOR: dict[int, str] = {idx: major for idx, _, major in _CATEGORIES}
MAJOR_LABELS: dict[str, str] = {
    "display": "展示美",
    "knowledge": "知识",
    "persona": "人设",
    "trending": "热点",
}

_DEFAULT_PROMPT = (
    "你将看到一个穿搭/时尚类短视频，请判断视频内容最贴合下面 14 个分类中的哪一个，"
    "只输出该分类的下标整数（0-13），不要输出任何额外文字。\n\n"
    "分类列表：\n"
    + "\n".join(f"{idx} - {label}（大类: {major}）" for idx, label, major in _CATEGORIES)
    + "\n\n输出格式：JSON 对象 {\"category_index\": <整数>}"
)

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "category_index": {
            "type": "INTEGER",
            "minimum": 0,
            "maximum": 13,
        }
    },
    "required": ["category_index"],
}

# =============================================================================
# 聚合规则（默认值，运行时由 pipeline_settings 覆盖）
# =============================================================================

_DEFAULT_MIN_SAMPLE = 3
_DEFAULT_SINGLE_TOP1 = 0.5
_DEFAULT_SINGLE_DIFF = 0.15
_DEFAULT_DUAL_TOP1_LOWER = 0.35
_DEFAULT_DUAL_TOP1_UPPER = 0.5
_DEFAULT_DUAL_TOP2 = 0.2
_MAJOR_KEYS = ("display", "knowledge", "persona", "trending")

# =============================================================================
# 队列 / 内存状态
# =============================================================================

_CONCURRENCY = 17          # 单账号内视频并发数
_PERSIST_INTERVAL = 2.0

classification_states: dict[str, dict] = {}
dirty_classification_ids: set[str] = set()
# 队列以账号为单位：每个元素是 account_id，处理器逐账号串行执行
classification_queue: asyncio.Queue[uuid.UUID] = asyncio.Queue()

_queue_processor_task: asyncio.Task | None = None
_persist_worker_task: asyncio.Task | None = None
_in_flight_accounts: set[str] = set()  # 防止同一账号重复入队


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


# =============================================================================
# 内存状态辅助
# =============================================================================


def _set_state(video_source_id: str, status: str, *, error: str = "") -> None:
    classification_states[video_source_id] = {
        "video_source_id": video_source_id,
        "status": status,
        "error_message": error,
        "updated_at": _utcnow_iso(),
    }
    dirty_classification_ids.add(video_source_id)


def get_state(video_source_id: str) -> dict | None:
    return classification_states.get(video_source_id)


# =============================================================================
# 持久化
# =============================================================================


async def _persist_states(ids: list[str]) -> None:
    if not ids:
        return
    async with SessionLocal() as session:
        for vs_id in ids:
            state = classification_states.get(vs_id)
            if state is None:
                continue
            try:
                vs_uuid = uuid.UUID(vs_id)
            except ValueError:
                continue
            row = await session.scalar(
                select(VideoClassification).where(VideoClassification.video_source_id == vs_uuid)
            )
            if row is None:
                continue
            row.status = state["status"]
            row.error_message = state.get("error_message") or None
        await session.commit()


async def _persist_worker_loop() -> None:
    global _persist_worker_task
    try:
        while True:
            await asyncio.sleep(_PERSIST_INTERVAL)
            ids = list(dirty_classification_ids)
            if not ids:
                continue
            dirty_classification_ids.difference_update(ids)
            try:
                await _persist_states(ids)
            except Exception:
                logger.exception("classification persist worker iteration failed")
    except asyncio.CancelledError:
        ids = list(dirty_classification_ids)
        if ids:
            dirty_classification_ids.difference_update(ids)
            try:
                await _persist_states(ids)
            except Exception:
                logger.exception("classification persist worker final flush failed")
        raise


def _ensure_persist_worker() -> None:
    global _persist_worker_task
    if _persist_worker_task is not None and not _persist_worker_task.done():
        return
    loop = asyncio.get_event_loop()
    _persist_worker_task = loop.create_task(_persist_worker_loop())


# =============================================================================
# 视频级分类
# =============================================================================


async def _classify_one(video_source_id: str) -> None:
    """对单个 video_source 调用 Gemini 进行分类，写库并触发账号聚合。"""
    from app.services.ai_api import call_gemini_api
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings

    try:
        vs_uuid = uuid.UUID(video_source_id)
    except ValueError:
        logger.warning("invalid video_source_id: %s", video_source_id)
        return

    async with SessionLocal() as session:
        row = await session.scalar(
            select(VideoClassification).where(VideoClassification.video_source_id == vs_uuid)
        )
        vs = await session.get(VideoSource, vs_uuid)
        if row is None or vs is None:
            logger.warning("classification row or video_source missing: %s", video_source_id)
            return
        if not vs.local_video_url:
            row.status = "failed"
            row.error_message = "缺少 local_video_url"
            row.classified_at = _utcnow()
            await session.commit()
            _set_state(video_source_id, "failed", error="缺少 local_video_url")
            await _trigger_summary_for_video(vs_uuid)
            return
        owner_id = vs.owner_id
        local_url = vs.local_video_url
        row.status = "processing"
        row.error_message = None
        await session.commit()

    _set_state(video_source_id, "processing")

    # 取配置
    cfg_owner = owner_id if owner_id is not None else uuid.UUID(int=0)
    async with SessionLocal() as session:
        try:
            cfg = await get_or_create_pipeline_settings(session, owner_id=cfg_owner)
        except Exception as exc:
            logger.warning("failed to load pipeline settings, use defaults: %s", exc)
            cfg = None

    model_name = (cfg.video_classify_model if cfg else "") or "gemini-3.1-pro-preview"
    prompt = (cfg.video_classify_prompt if cfg else "") or _DEFAULT_PROMPT
    temperature = float(cfg.video_classify_temperature) if cfg else 0.0

    try:
        text = await call_gemini_api(
            model_name=model_name,
            prompt=prompt,
            temperature=temperature,
            video_url=local_url,
            response_schema=_RESPONSE_SCHEMA,
            timeout=180.0,
        )
        category_index = _parse_category_index(text)
        major = CATEGORY_MAJOR.get(category_index)
        if major is None:
            raise ValueError(f"category_index 越界: {category_index}")

        async with SessionLocal() as session:
            row = await session.scalar(
                select(VideoClassification).where(VideoClassification.video_source_id == vs_uuid)
            )
            if row is None:
                return
            row.status = "success"
            row.category_index = category_index
            row.major_category = major
            row.raw_response = text[:8000] if text else None
            row.error_message = None
            row.classified_at = _utcnow()
            await session.commit()
        _set_state(video_source_id, "success")
        logger.info("[classify] %s -> idx=%d major=%s", video_source_id, category_index, major)
    except Exception as exc:
        err_text = str(exc)[:1000]
        logger.warning("[classify] %s failed: %s", video_source_id, err_text)
        async with SessionLocal() as session:
            row = await session.scalar(
                select(VideoClassification).where(VideoClassification.video_source_id == vs_uuid)
            )
            if row is not None:
                row.status = "failed"
                row.error_message = err_text
                row.classified_at = _utcnow()
                await session.commit()
        _set_state(video_source_id, "failed", error=err_text)

    await _trigger_summary_for_video(vs_uuid)


def _parse_category_index(text: str) -> int:
    if not text:
        raise ValueError("Gemini 返回空响应")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # 兜底：直接抓数字
        import re
        match = re.search(r"category_index\D*(\d+)", text)
        if match:
            return int(match.group(1))
        match = re.search(r"\b(\d{1,2})\b", text)
        if match:
            return int(match.group(1))
        raise ValueError(f"无法解析分类响应：{text[:200]}")
    if isinstance(obj, dict) and "category_index" in obj:
        return int(obj["category_index"])
    if isinstance(obj, int):
        return obj
    raise ValueError(f"分类响应缺少 category_index：{text[:200]}")


async def _trigger_summary_for_video(video_source_id: uuid.UUID) -> None:
    """根据 video_source 反查所有关联账号并重算各账号的聚合。"""
    async with SessionLocal() as session:
        vs = await session.get(VideoSource, video_source_id)
        if vs is None or vs.tiktok_blogger_id is None:
            return
        account_ids = (await session.scalars(
            select(AccountBloggerBinding.account_id).where(
                AccountBloggerBinding.tiktok_blogger_id == vs.tiktok_blogger_id
            )
        )).all()
    for aid in account_ids:
        try:
            await _recompute_account_summary(aid)
        except Exception:
            logger.exception("recompute summary failed for account %s", aid)


# =============================================================================
# 账号聚合
# =============================================================================


async def _recompute_account_summary(account_id: uuid.UUID) -> None:
    """
    统计某账号下所有视频的大类占比并写回 accounts.classification_summary。
    若没有 pending/processing 记录，将 classification_status 切回 idle。
    """
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings

    async with SessionLocal() as session:
        rows = (await session.execute(
            select(
                VideoClassification.status,
                VideoClassification.major_category,
                VideoClassification.category_index,
            )
            .join(VideoSource, VideoSource.id == VideoClassification.video_source_id)
            .join(
                AccountBloggerBinding,
                AccountBloggerBinding.tiktok_blogger_id == VideoSource.tiktok_blogger_id,
            )
            .where(AccountBloggerBinding.account_id == account_id)
        )).all()

        total = len(rows)
        success = sum(1 for r in rows if r.status == "success")
        failed = sum(1 for r in rows if r.status == "failed")
        pending = sum(1 for r in rows if r.status == "pending")
        processing = sum(1 for r in rows if r.status == "processing")

        major_counts: dict[str, int] = {k: 0 for k in _MAJOR_KEYS}
        category_counts: dict[int, int] = {idx: 0 for idx in CATEGORY_LABELS}
        for r in rows:
            if r.status == "success":
                if r.major_category in major_counts:
                    major_counts[r.major_category] += 1
                if r.category_index is not None and r.category_index in category_counts:
                    category_counts[r.category_index] += 1

        # 大类占比：仅供饼图展示
        major_ratios: dict[str, float] = {}
        if success > 0:
            major_ratios = {k: round(v / success, 4) for k, v in major_counts.items()}

        # 小类占比：用于 single/dual/chaos 聚合判断
        category_ratios: dict[str, float] = {}
        if success > 0:
            category_ratios = {str(k): round(v / success, 4) for k, v in category_counts.items()}

        account = await session.get(Account, account_id)
        if account is None:
            return

        cfg_owner = account.owner_id if account.owner_id is not None else uuid.UUID(int=0)
        try:
            cfg = await get_or_create_pipeline_settings(session, owner_id=cfg_owner)
        except Exception:
            cfg = None
        thresholds = _resolve_thresholds(cfg)

        cls_type, primary_key, secondary_key = _classify_aggregation(category_ratios, success, thresholds)

        def _key_to_label(key: str | None) -> str | None:
            if key is None:
                return None
            try:
                return CATEGORY_LABELS[int(key)]
            except (ValueError, KeyError):
                return key

        summary = {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": pending,
            "processing": processing,
            "type": cls_type,
            "primary": _key_to_label(primary_key),
            "primary_index": int(primary_key) if primary_key is not None else None,
            "secondary": _key_to_label(secondary_key),
            "secondary_index": int(secondary_key) if secondary_key is not None else None,
            "ratios": major_ratios,
            "counts": major_counts,
            "category_ratios": category_ratios,
            "category_counts": {str(k): v for k, v in category_counts.items()},
            "thresholds": thresholds,
            "updated_at": _utcnow_iso(),
        }

        account.classification_summary = summary
        account.classification_type = cls_type if success > 0 else None
        if pending == 0 and processing == 0:
            account.classification_status = "idle"
        await session.commit()


def _resolve_thresholds(cfg: Any) -> dict[str, float]:
    return {
        "min_sample": int(getattr(cfg, "classify_min_sample", _DEFAULT_MIN_SAMPLE) or _DEFAULT_MIN_SAMPLE),
        "single_top1": float(getattr(cfg, "classify_single_top1_threshold", _DEFAULT_SINGLE_TOP1) or _DEFAULT_SINGLE_TOP1),
        "single_diff": float(getattr(cfg, "classify_single_diff_threshold", _DEFAULT_SINGLE_DIFF) or _DEFAULT_SINGLE_DIFF),
        "dual_top1_lower": float(getattr(cfg, "classify_dual_top1_lower", _DEFAULT_DUAL_TOP1_LOWER) or _DEFAULT_DUAL_TOP1_LOWER),
        "dual_top1_upper": float(getattr(cfg, "classify_dual_top1_upper", _DEFAULT_DUAL_TOP1_UPPER) or _DEFAULT_DUAL_TOP1_UPPER),
        "dual_top2": float(getattr(cfg, "classify_dual_top2_threshold", _DEFAULT_DUAL_TOP2) or _DEFAULT_DUAL_TOP2),
    }


def _classify_aggregation(
    ratios: dict[str, float],
    success_count: int,
    thresholds: dict[str, float] | None = None,
) -> tuple[str, str | None, str | None]:
    t = thresholds or _resolve_thresholds(None)

    if success_count == 0:
        return ("none", None, None)
    if success_count < t["min_sample"]:
        return ("insufficient", None, None)

    sorted_pairs = sorted(ratios.items(), key=lambda kv: kv[1], reverse=True)
    top1_key, p1 = sorted_pairs[0]
    top2_key, p2 = sorted_pairs[1] if len(sorted_pairs) > 1 else (None, 0.0)

    # 单核心
    if p1 >= t["single_top1"] or (p1 - p2) >= t["single_diff"]:
        return ("single", top1_key, None)

    # 双核心
    if (
        t["dual_top1_lower"] <= p1 < t["dual_top1_upper"]
        and p2 >= t["dual_top2"]
        and (p1 - p2) < t["single_diff"]
    ):
        return ("dual", top1_key, top2_key)

    return ("chaos", None, None)


# =============================================================================
# 队列处理
# =============================================================================


async def _enqueue_account(account_id: uuid.UUID) -> None:
    """将账号入队（去重）。"""
    key = str(account_id)
    if key in _in_flight_accounts:
        return
    _in_flight_accounts.add(key)
    await classification_queue.put(account_id)


async def _process_account_videos(account_id: uuid.UUID) -> None:
    """串行处理单个账号下所有 pending 视频（账号内最多 _CONCURRENCY 并发）。"""
    async with SessionLocal() as session:
        pending_ids: list[str] = (await session.scalars(
            select(VideoClassification.video_source_id)
            .join(VideoSource, VideoSource.id == VideoClassification.video_source_id)
            .join(
                AccountBloggerBinding,
                AccountBloggerBinding.tiktok_blogger_id == VideoSource.tiktok_blogger_id,
            )
            .where(AccountBloggerBinding.account_id == account_id)
            .where(VideoClassification.status.in_(["pending", "processing"]))
        )).all()

    if not pending_ids:
        return

    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def _run_one(vs_id: uuid.UUID) -> None:
        async with semaphore:
            await _classify_one(str(vs_id))

    await asyncio.gather(*[_run_one(vid) for vid in pending_ids], return_exceptions=True)


async def _queue_processor_loop() -> None:
    while True:
        try:
            account_id = await classification_queue.get()
            try:
                await _process_account_videos(account_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("classification _process_account_videos error for %s", account_id)
            finally:
                _in_flight_accounts.discard(str(account_id))
                classification_queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("classification queue processor outer error, continuing")


# =============================================================================
# 公共 API
# =============================================================================


async def enqueue_account_classification(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None,
    *,
    force: bool = False,
) -> dict[str, int]:
    """
    把账号下所有 (有 local_video_url) 的视频入队。
    force=True 时已成功的视频也会重新分类；否则跳过。
    返回 {queued, skipped}.
    """
    _ensure_persist_worker()

    async with SessionLocal() as session:
        account = await _get_account_or_none(session, account_id, owner_id)
        if account is None:
            raise ValueError("账号不存在或无权限")

        videos = await _list_account_videos(session, account_id)
        if not videos:
            return {"queued": 0, "skipped": 0}

        existing_rows = (await session.execute(
            select(VideoClassification).where(
                VideoClassification.video_source_id.in_([v.id for v in videos])
            )
        )).scalars().all()
        existing_by_vs = {r.video_source_id: r for r in existing_rows}

        to_queue: list[uuid.UUID] = []
        skipped = 0
        for vs in videos:
            if not vs.local_video_url:
                skipped += 1
                continue
            existing = existing_by_vs.get(vs.id)
            if existing is None:
                row = VideoClassification(
                    video_source_id=vs.id,
                    owner_id=vs.owner_id,
                    status="pending",
                )
                session.add(row)
                to_queue.append(vs.id)
            elif existing.status == "success" and not force:
                skipped += 1
            else:
                existing.status = "pending"
                existing.error_message = None
                existing.category_index = None
                existing.major_category = None
                existing.classified_at = None
                to_queue.append(vs.id)

        if to_queue:
            account.classification_status = "running"
        await session.commit()

    for vs_id in to_queue:
        _set_state(str(vs_id), "pending")

    # 立刻刷新一次聚合，让前端先看到 pending 计数
    try:
        await _recompute_account_summary(account_id)
    except Exception:
        logger.exception("initial summary recompute failed")

    if to_queue:
        await _enqueue_account(account_id)

    return {"queued": len(to_queue), "skipped": skipped}


async def retry_failed_classifications(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None,
) -> dict[str, int]:
    _ensure_persist_worker()

    async with SessionLocal() as session:
        account = await _get_account_or_none(session, account_id, owner_id)
        if account is None:
            raise ValueError("账号不存在或无权限")

        rows = (await session.execute(
            select(VideoClassification)
            .join(VideoSource, VideoSource.id == VideoClassification.video_source_id)
            .join(
                AccountBloggerBinding,
                AccountBloggerBinding.tiktok_blogger_id == VideoSource.tiktok_blogger_id,
            )
            .where(AccountBloggerBinding.account_id == account_id)
            .where(VideoClassification.status == "failed")
        )).scalars().all()

        ids: list[uuid.UUID] = []
        for r in rows:
            r.status = "pending"
            r.error_message = None
            ids.append(r.video_source_id)
        if ids:
            account.classification_status = "running"
        await session.commit()

    for vs_id in ids:
        _set_state(str(vs_id), "pending")

    if ids:
        try:
            await _recompute_account_summary(account_id)
        except Exception:
            logger.exception("retry summary recompute failed")
        await _enqueue_account(account_id)

    return {"queued": len(ids)}


async def get_account_classification_view(
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None,
) -> dict[str, Any]:
    async with SessionLocal() as session:
        account = await _get_account_or_none(session, account_id, owner_id)
        if account is None:
            raise ValueError("账号不存在或无权限")

        videos = await _list_account_videos(session, account_id)
        if not videos:
            return {
                "summary": _empty_summary(account),
                "videos": [],
            }

        rows = (await session.execute(
            select(VideoClassification).where(
                VideoClassification.video_source_id.in_([v.id for v in videos])
            )
        )).scalars().all()
        by_vs: dict[uuid.UUID, VideoClassification] = {r.video_source_id: r for r in rows}

    items: list[dict[str, Any]] = []
    for vs in videos:
        row = by_vs.get(vs.id)
        if row is None:
            status = "not_started" if vs.local_video_url else "no_local_video"
            category_index = None
            major = None
            error = None
            classified_at = None
        else:
            status = row.status
            category_index = row.category_index
            major = row.major_category
            error = row.error_message
            classified_at = row.classified_at.isoformat() if row.classified_at else None

        items.append({
            "video_source_id": str(vs.id),
            "video_title": vs.video_title,
            "local_video_url": vs.local_video_url,
            "blogger_name": vs.blogger_name,
            "tiktok_blogger_id": str(vs.tiktok_blogger_id) if vs.tiktok_blogger_id else None,
            "has_local_video": bool(vs.local_video_url),
            "status": status,
            "category_index": category_index,
            "category_label": CATEGORY_LABELS.get(category_index) if category_index is not None else None,
            "major_category": major,
            "error_message": error,
            "classified_at": classified_at,
        })

    return {
        "summary": _summary_payload(account),
        "videos": items,
    }


def _empty_summary(account: Account) -> dict[str, Any]:
    base = _summary_payload(account)
    if not base.get("summary"):
        base["summary"] = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "pending": 0,
            "processing": 0,
            "type": "none",
            "primary": None,
            "secondary": None,
            "ratios": {},
            "counts": {k: 0 for k in _MAJOR_KEYS},
            "updated_at": None,
        }
    return base


def _summary_payload(account: Account) -> dict[str, Any]:
    return {
        "account_id": str(account.id),
        "account_name": account.account_name,
        "classification_status": account.classification_status,
        "summary": account.classification_summary,
    }


async def _get_account_or_none(
    session: AsyncSession,
    account_id: uuid.UUID,
    owner_id: uuid.UUID | None,
) -> Account | None:
    account = await session.get(Account, account_id)
    if account is None:
        return None
    if owner_id is not None and account.owner_id != owner_id:
        return None
    return account


async def _list_account_videos(session: AsyncSession, account_id: uuid.UUID) -> list[VideoSource]:
    rows = (await session.execute(
        select(VideoSource)
        .join(
            AccountBloggerBinding,
            AccountBloggerBinding.tiktok_blogger_id == VideoSource.tiktok_blogger_id,
        )
        .where(AccountBloggerBinding.account_id == account_id)
        .order_by(VideoSource.created_at.desc())
    )).scalars().all()
    return list(rows)


# =============================================================================
# 生命周期
# =============================================================================


def start_classification_queue_processor() -> None:
    global _queue_processor_task
    if _queue_processor_task is not None and not _queue_processor_task.done():
        return
    loop = asyncio.get_event_loop()
    _queue_processor_task = loop.create_task(_queue_processor_loop())
    _ensure_persist_worker()
    logger.info("Video classification queue processor started")


async def stop_classification_queue_processor() -> None:
    global _queue_processor_task, _persist_worker_task
    if _queue_processor_task and not _queue_processor_task.done():
        _queue_processor_task.cancel()
        try:
            await _queue_processor_task
        except asyncio.CancelledError:
            pass
    if _persist_worker_task and not _persist_worker_task.done():
        _persist_worker_task.cancel()
        try:
            await _persist_worker_task
        except asyncio.CancelledError:
            pass
    logger.info("Video classification queue processor stopped")


async def recover_classification_on_startup() -> None:
    """启动恢复：把 pending/processing 行重置为 pending，按账号入队。"""
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(
                VideoClassification.video_source_id,
                VideoSource.tiktok_blogger_id,
            )
            .join(VideoSource, VideoSource.id == VideoClassification.video_source_id)
            .where(VideoClassification.status.in_(["pending", "processing"]))
        )).all()

        if not rows:
            logger.info("No stuck classifications to recover on startup")
            return

        vs_ids = [r.video_source_id for r in rows]
        await session.execute(
            VideoClassification.__table__.update()
            .where(VideoClassification.video_source_id.in_(vs_ids))
            .values(status="pending", error_message=None)
        )

        # 查出涉及的 account_ids
        blogger_ids = list({r.tiktok_blogger_id for r in rows if r.tiktok_blogger_id})
        account_ids: list[uuid.UUID] = []
        if blogger_ids:
            account_ids = (await session.scalars(
                select(AccountBloggerBinding.account_id)
                .where(AccountBloggerBinding.tiktok_blogger_id.in_(blogger_ids))
                .distinct()
            )).all()

        await session.commit()

    logger.info("Recovering %d stuck video classifications across %d accounts on startup",
                len(vs_ids), len(account_ids))

    _ensure_persist_worker()
    for vs_id in vs_ids:
        _set_state(str(vs_id), "pending")
    for account_id in account_ids:
        await _enqueue_account(account_id)
