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
# 分类体系：6 大类 × N 小类，用字符串 key 存储，与顺序解耦
# =============================================================================
# 每条记录：(category_key, label, major_key)
_CATEGORIES: list[tuple[str, str, str]] = [
    # ── 美美展示类 ────────────────────────────────────────────────────────────
    ("beauty_static_pose",    "静态 Pose / 镜头展示类",   "beauty"),
    ("beauty_light_action",   "轻动作展示类",              "beauty"),
    ("beauty_dance",          "音乐跳舞类",                "beauty"),
    ("beauty_lipsync",        "歌曲对口型类",              "beauty"),
    ("beauty_drama_light",    "影视 / 台词轻演绎类",       "beauty"),
    # ── 穿搭方法类 ────────────────────────────────────────────────────────────
    ("method_single_silent",  "不带语音单套逐件穿搭型",    "method"),
    ("method_multi_look",     "不带语音多套完整 Look 切换型", "method"),
    ("method_multi_build",    "不带语音多套逐件搭建型",    "method"),
    ("method_base_replace",   "不带语音 Base Look 替换单品型", "method"),
    ("method_multiway",       "不带语音单品多穿型",        "method"),
    ("method_before_after",   "不带语音 Before & After 优化型", "method"),
    ("method_compare",        "不带语音左右对比 / 并列对比型", "method"),
    ("method_voice_formula",  "带语音公式规则讲解型",      "method"),
    ("method_voice_steps",    "带语音步骤流程讲解型",      "method"),
    ("method_voice_diagnose", "带语音问题诊断 / 优化讲解型", "method"),
    ("method_voice_compare",  "带语音对比判断讲解型",      "method"),
    ("method_voice_case",     "带语音案例拆解讲解型",      "method"),
    ("method_voice_standard", "带语音选择标准讲解型",      "method"),
    ("method_voice_system",   "带语音系统规划讲解型",      "method"),
    # ── 购物决策类 ────────────────────────────────────────────────────────────
    ("shopping_brand",        "品牌导向型",                "shopping"),
    ("shopping_single_item",  "单品种草型",                "shopping"),
    ("shopping_dupe",         "大牌平替 / Dupe 型",        "shopping"),
    ("shopping_scene",        "场景需求型",                "shopping"),
    ("shopping_list",         "清单合集型",                "shopping"),
    ("shopping_compare",      "对比选择型",                "shopping"),
    # ── 人设生活类 ────────────────────────────────────────────────────────────
    ("lifestyle",             "人设生活类",                "lifestyle"),
    # ── 情景剧情类 ────────────────────────────────────────────────────────────
    ("drama",                 "情景剧情类",                "drama"),
    # ── 不能分类 ─────────────────────────────────────────────────────────────
    ("unclassifiable",        "不能分类",                  "unclassifiable"),
]

# 快查表
CATEGORY_LABELS: dict[str, str] = {key: label for key, label, _ in _CATEGORIES}
CATEGORY_MAJOR: dict[str, str] = {key: major for key, _, major in _CATEGORIES}
MAJOR_LABELS: dict[str, str] = {
    "beauty":         "美美展示类",
    "method":         "穿搭方法类",
    "shopping":       "购物决策类",
    "lifestyle":      "人设生活类",
    "drama":          "情景剧情类",
    "unclassifiable": "不能分类",
}

_ALL_KEYS: list[str] = [key for key, _, _ in _CATEGORIES]

_DEFAULT_PROMPT = (
    "你将看到一个穿搭/时尚类短视频，请判断视频内容最贴合下列分类中的哪一个，"
    "只输出对应的 category_key 字符串，不要输出任何额外文字。\n\n"
    "分类列表（格式：key — 名称 [大类]）：\n"
    + "\n".join(
        f"{key} — {label} [{MAJOR_LABELS[major]}]"
        for key, label, major in _CATEGORIES
    )
    + "\n\n输出格式：JSON 对象 {\"category_key\": \"<key>\"}"
)

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "category_key": {
            "type": "STRING",
            "enum": _ALL_KEYS,
        }
    },
    "required": ["category_key"],
}

# =============================================================================
# 聚合规则（默认值，运行时由 pipeline_settings 覆盖）
# =============================================================================

_DEFAULT_MIN_SAMPLE = 3
# 各大类独立单核心阈值（占比 >= 该值即判为单核心）
_DEFAULT_MAJOR_THRESHOLDS: dict[str, float] = {
    "beauty":    0.75,
    "method":    0.60,
    "shopping":  0.55,
    "lifestyle": 0.55,
    "drama":     0.65,
}
# 双核心：Top1+Top2 合计占比 >= 该值（且均未达各自单核心阈值）
_DEFAULT_DUAL_COMBINED = 0.80
# unclassifiable 不参与判断，排除在外
_MAJOR_KEYS = ("beauty", "method", "shopping", "lifestyle", "drama", "unclassifiable")
_RANKABLE_MAJOR_KEYS = ("beauty", "method", "shopping", "lifestyle", "drama")

# =============================================================================
# 队列 / 内存状态
# =============================================================================

_CONCURRENCY = 100         # 单账号内视频并发数
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
        # GCS 签名 URL 续签（过期前自动刷新）
        from app.utils.gcs_signing import ensure_video_source_signed_urls
        await ensure_video_source_signed_urls(session, vs)
        local_url = vs.local_video_url or vs.local_gcs_video_url
        if not local_url:
            row.status = "failed"
            row.error_message = "缺少 local_video_url / local_gcs_video_url"
            row.classified_at = _utcnow()
            await session.commit()
            _set_state(video_source_id, "failed", error="缺少 local_video_url / local_gcs_video_url")
            await _trigger_summary_for_video(vs_uuid)
            return
        owner_id = vs.owner_id
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
        category_key = _parse_category_key(text)
        major = CATEGORY_MAJOR.get(category_key)
        if major is None:
            raise ValueError(f"未知 category_key: {category_key}")

        async with SessionLocal() as session:
            row = await session.scalar(
                select(VideoClassification).where(VideoClassification.video_source_id == vs_uuid)
            )
            if row is None:
                return
            row.status = "success"
            row.category_key = category_key
            row.major_category = major
            row.raw_response = text[:8000] if text else None
            row.error_message = None
            row.classified_at = _utcnow()
            await session.commit()
        _set_state(video_source_id, "success")
        logger.info("[classify] %s -> key=%s major=%s", video_source_id, category_key, major)
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


_VALID_KEYS_SET: frozenset[str] = frozenset(_ALL_KEYS)


def _parse_category_key(text: str) -> str:
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
        # 兜底：直接在文本中找合法 key
        import re
        for key in _ALL_KEYS:
            if re.search(r'\b' + re.escape(key) + r'\b', text):
                return key
        raise ValueError(f"无法解析分类响应：{text[:200]}")
    if isinstance(obj, dict) and "category_key" in obj:
        key = str(obj["category_key"]).strip()
        if key not in _VALID_KEYS_SET:
            raise ValueError(f"无效 category_key: {key}")
        return key
    raise ValueError(f"分类响应缺少 category_key：{text[:200]}")


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
                VideoClassification.category_key,
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
        category_counts: dict[str, int] = {key: 0 for key in CATEGORY_LABELS}
        for r in rows:
            if r.status == "success" and r.category_key:
                major = CATEGORY_MAJOR.get(r.category_key)
                if major and major in major_counts:
                    major_counts[major] += 1
                if r.category_key in category_counts:
                    category_counts[r.category_key] += 1

        # unclassifiable 不计入占比分母
        unclassifiable_count = major_counts.get("unclassifiable", 0)
        rankable_success = success - unclassifiable_count

        # 大类占比（含 unclassifiable，供饼图展示，分母用全部 success）
        major_ratios: dict[str, float] = {}
        if success > 0:
            major_ratios = {k: round(v / success, 4) for k, v in major_counts.items()}

        # 可排名大类占比（排除 unclassifiable，分母为 rankable_success，供聚合判断）
        rankable_ratios: dict[str, float] = {}
        if rankable_success > 0:
            rankable_ratios = {
                k: round(major_counts.get(k, 0) / rankable_success, 4)
                for k in _RANKABLE_MAJOR_KEYS
            }

        # 小类占比（供展示）
        category_ratios: dict[str, float] = {}
        if success > 0:
            category_ratios = {k: round(v / success, 4) for k, v in category_counts.items()}

        account = await session.get(Account, account_id)
        if account is None:
            return

        cfg_owner = account.owner_id if account.owner_id is not None else uuid.UUID(int=0)
        try:
            cfg = await get_or_create_pipeline_settings(session, owner_id=cfg_owner)
        except Exception:
            cfg = None
        thresholds = _resolve_thresholds(cfg)

        cls_type, primary_key, secondary_key = _classify_aggregation(rankable_ratios, rankable_success, thresholds)

        summary = {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": pending,
            "processing": processing,
            "type": cls_type,
            "primary": MAJOR_LABELS.get(primary_key) if primary_key else None,
            "primary_key": primary_key,
            "secondary": MAJOR_LABELS.get(secondary_key) if secondary_key else None,
            "secondary_key": secondary_key,
            "ratios": major_ratios,
            "rankable_ratios": rankable_ratios,
            "counts": major_counts,
            "category_ratios": category_ratios,
            "category_counts": category_counts,
            "thresholds": thresholds,
            "updated_at": _utcnow_iso(),
        }

        account.classification_summary = summary
        account.classification_type = cls_type if success > 0 else None
        if pending == 0 and processing == 0:
            account.classification_status = "idle"
        await session.commit()


def _resolve_thresholds(cfg: Any) -> dict[str, Any]:
    def _f(attr: str, default: float) -> float:
        return float(getattr(cfg, attr, default) or default)

    return {
        "min_sample": int(getattr(cfg, "classify_min_sample", _DEFAULT_MIN_SAMPLE) or _DEFAULT_MIN_SAMPLE),
        "major": {
            major: _f(f"classify_{major}_threshold", _DEFAULT_MAJOR_THRESHOLDS[major])
            for major in _RANKABLE_MAJOR_KEYS
        },
        "dual_combined": _f("classify_dual_combined_threshold", _DEFAULT_DUAL_COMBINED),
    }


def _classify_aggregation(
    major_ratios: dict[str, float],
    success_count: int,
    thresholds: dict[str, Any] | None = None,
) -> tuple[str, str | None, str | None]:
    """
    按大类占比判断账号分类类型。
    major_ratios: 仅含 _RANKABLE_MAJOR_KEYS（已排除 unclassifiable）的占比，总和 <= 1.0。
    返回 (cls_type, primary_major_key, secondary_major_key)
    """
    t = thresholds or _resolve_thresholds(None)

    if success_count == 0:
        return ("none", None, None)
    if success_count < t["min_sample"]:
        return ("insufficient", None, None)

    major_thresholds: dict[str, float] = t["major"]

    # 只排名可计算的大类，按占比降序
    ranked = sorted(
        [(k, major_ratios.get(k, 0.0)) for k in _RANKABLE_MAJOR_KEYS],
        key=lambda kv: kv[1],
        reverse=True,
    )
    top1_key, p1 = ranked[0]
    top2_key, p2 = ranked[1] if len(ranked) > 1 else (None, 0.0)

    # 单核心：任何大类占比 >= 该大类的阈值
    for major_key, ratio in ranked:
        if ratio >= major_thresholds.get(major_key, 1.0):
            return ("single", major_key, None)

    # 双核心：Top1+Top2 合计 >= dual_combined 且两者均未达各自阈值
    if (
        top2_key is not None
        and (p1 + p2) >= t["dual_combined"]
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
            if not (vs.local_video_url or vs.local_gcs_video_url):
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
                existing.category_key = None
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
        playable_url = vs.local_video_url or vs.local_gcs_video_url
        row = by_vs.get(vs.id)
        if row is None:
            status = "not_started" if playable_url else "no_local_video"
            cat_key = None
            major = None
            error = None
            classified_at = None
        else:
            status = row.status
            cat_key = row.category_key
            major = row.major_category
            error = row.error_message
            classified_at = row.classified_at.isoformat() if row.classified_at else None

        items.append({
            "video_source_id": str(vs.id),
            "video_title": vs.video_title,
            "local_video_url": vs.local_video_url,
            "local_gcs_video_url": vs.local_gcs_video_url,
            "blogger_name": vs.blogger_name,
            "tiktok_blogger_id": str(vs.tiktok_blogger_id) if vs.tiktok_blogger_id else None,
            "has_local_video": bool(playable_url),
            "status": status,
            "category_key": cat_key,
            "category_label": CATEGORY_LABELS.get(cat_key) if cat_key else None,
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


_BATCH_SIZE = 5000  # asyncpg 单次 IN 参数上限保守值


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

        # 分批 UPDATE，避免 asyncpg 32767 参数上限
        for i in range(0, len(vs_ids), _BATCH_SIZE):
            batch = vs_ids[i:i + _BATCH_SIZE]
            await session.execute(
                VideoClassification.__table__.update()
                .where(VideoClassification.video_source_id.in_(batch))
                .values(status="pending", error_message=None)
            )

        # 查出涉及的 account_ids（blogger_ids 同样分批）
        blogger_ids = list({r.tiktok_blogger_id for r in rows if r.tiktok_blogger_id})
        account_ids: list[uuid.UUID] = []
        if blogger_ids:
            for i in range(0, len(blogger_ids), _BATCH_SIZE):
                batch = blogger_ids[i:i + _BATCH_SIZE]
                chunk = (await session.scalars(
                    select(AccountBloggerBinding.account_id)
                    .where(AccountBloggerBinding.tiktok_blogger_id.in_(batch))
                    .distinct()
                )).all()
                account_ids.extend(chunk)
            account_ids = list(set(account_ids))

        await session.commit()

    logger.info("Recovering %d stuck video classifications across %d accounts on startup",
                len(vs_ids), len(account_ids))

    _ensure_persist_worker()
    for vs_id in vs_ids:
        _set_state(str(vs_id), "pending")
    for account_id in account_ids:
        await _enqueue_account(account_id)
