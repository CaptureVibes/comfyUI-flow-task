"""候选库搜索服务

核心流程：
1. 用关键词调 RapidAPI 搜索，翻页收集博主，直到 max_bloggers 个唯一博主
2. 并发获取博主粉丝数，按粉丝量从高到低排序
3. 依次对每个博主做 [关键词 + 博主名] 精搜，取前 max_videos_per_blogger 条，过滤 > max_duration_seconds 的视频
4. 过滤后该博主视频数 >= exclusive_threshold → 独享模板（删除已存的共享记录，停止搜索）
   过滤后该博主视频数 < exclusive_threshold → 共享模板（写入并继续下一个博主）
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.models.candidate_video import CandidateVideo
from app.services import rapid_api
from app.services.image_upload_service import image_upload_service
from app.services.pipeline_settings_service import get_or_create_pipeline_settings
from app.services.system_settings_service import get_or_create_system_settings

logger = logging.getLogger(__name__)

# 并发控制
_CONCURRENCY_AI_REVIEW = 3    # AI 审核并发数
_CONCURRENCY_COVER_UPLOAD = 5 # 封面上传并发数


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 搜索配置（从 pipeline_settings 按用户读取）
# ---------------------------------------------------------------------------

class _SearchConfig:
    def __init__(self, row: Any | None) -> None:
        self.max_bloggers: int = row.candidate_max_bloggers if row else 20
        self.exclusive_threshold: int = row.candidate_exclusive_threshold if row else 10
        self.max_videos_per_blogger: int = row.candidate_max_videos_per_blogger if row else 100
        self.max_duration_seconds: int = row.candidate_max_duration_seconds if row else 30
        self.retry_delay: float = float(row.candidate_retry_delay_seconds) if row else 5.0
        self.min_play_count: int = row.candidate_min_play_count if row else 0
        self.publish_after_date: str | None = row.candidate_publish_after_date if row else None
        self.shared_top_n: int = row.candidate_shared_top_n if row else 50
        self.ai_review_enabled: bool = row.candidate_ai_review_enabled if row else False
        self.ai_review_model: str = row.candidate_ai_review_model if row else "gemini-3.1-pro-preview"
        self.ai_review_prompt: str = row.candidate_ai_review_prompt if row else ""


# ---------------------------------------------------------------------------
# 第一阶段：收集唯一博主
# ---------------------------------------------------------------------------

async def _collect_bloggers(
    keyword: str,
    max_bloggers: int,
    retry_delay: float,
    exclude_bloggers: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    翻页搜索关键词，收集 max_bloggers 个唯一博主（按出现顺序）。
    exclude_bloggers: 已在库中的博主 unique_id 集合，搜索时跳过。
    返回 list[{"unique_id", "nickname", "follower_count"}]，follower_count 可能为 None（待补全）。
    """
    seen: dict[str, dict[str, Any]] = {}  # unique_id -> blogger info
    excluded = exclude_bloggers or set()
    cursor = 0

    logger.info("【候选库】开始收集博主，keyword=%s，目标博主数=%d，排除已有博主数=%d",
                keyword, max_bloggers, len(excluded))

    while len(seen) < max_bloggers:
        result = await rapid_api.search_videos(keyword, cursor=cursor, retry_delay=retry_delay)
        items = result["items"]

        for item in items:
            uid = item["unique_id"]
            if uid in excluded:
                continue  # 跳过已入库的博主
            if uid not in seen:
                seen[uid] = {
                    "unique_id": uid,
                    "nickname": item["nickname"],
                    "follower_count": item.get("follower_count"),
                }
                if len(seen) >= max_bloggers:
                    break

        logger.info("【候选库】已收集 %d/%d 个博主，cursor=%d", len(seen), max_bloggers, cursor)

        if len(seen) >= max_bloggers:
            break
        if not result["has_more"]:
            logger.info("【候选库】搜索结果已无更多，停止翻页，共收集 %d 个博主", len(seen))
            break
        cursor = result["next_cursor"]

    return list(seen.values())


# ---------------------------------------------------------------------------
# 第二阶段：补全粉丝数并排序
# ---------------------------------------------------------------------------

async def _enrich_and_sort_bloggers(
    bloggers: list[dict[str, Any]],
    retry_delay: float,
) -> list[dict[str, Any]]:
    """
    对粉丝数为 None 的博主调 get_user_info 补全，然后按粉丝数从高到低排序。
    get_user_info 内部已有无限重试，此处不做额外并发限制。
    """
    needs_enrich = [b for b in bloggers if b.get("follower_count") is None]

    logger.info("【候选库】需要补全粉丝数的博主数量=%d", len(needs_enrich))

    async def _fetch_one(blogger: dict[str, Any]) -> None:
        info = await rapid_api.get_user_info(blogger["unique_id"], retry_delay=retry_delay)
        blogger["follower_count"] = info["follower_count"]
        if not blogger["nickname"] or blogger["nickname"] == blogger["unique_id"]:
            blogger["nickname"] = info["nickname"]

    tasks = [asyncio.create_task(_fetch_one(b)) for b in needs_enrich]
    if tasks:
        await asyncio.gather(*tasks)

    # 按粉丝数从高到低排序
    bloggers.sort(key=lambda b: b.get("follower_count") or 0, reverse=True)
    logger.info("【候选库】博主排序完成，top3: %s", [f"{b['unique_id']}({b.get('follower_count',0)})" for b in bloggers[:3]])
    return bloggers


# ---------------------------------------------------------------------------
# 第三阶段：对单个博主精搜 + 过滤
# ---------------------------------------------------------------------------

async def _search_blogger_videos(
    keyword: str,
    blogger: dict[str, Any],
    cfg: _SearchConfig,
) -> list[dict[str, Any]]:
    """
    用 [keyword + blogger_unique_id] 搜索，收集最多 max_videos 条，
    过滤掉时长 > max_duration / 播放量 < min_play_count / 发布超过 max_publish_days 天的视频。
    返回属于该博主且满足条件的视频列表。
    """
    search_keyword = f"{keyword} {blogger['unique_id']}"
    unique_id = blogger["unique_id"]
    collected: list[dict[str, Any]] = []
    total_fetched = 0
    cursor = 0

    # 计算发布时间截止 Unix 时间戳（0 表示不限制）
    import calendar
    cutoff_ts = 0
    if cfg.publish_after_date:
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(cfg.publish_after_date, "%Y-%m-%d")
            cutoff_ts = int(calendar.timegm(d.timetuple()))
        except ValueError:
            cutoff_ts = 0

    logger.info("【候选库】开始精搜博主 %s，搜索词=%s，max_videos=%d，max_dur=%ds，min_play=%d，publish_after=%s",
                unique_id, search_keyword, cfg.max_videos_per_blogger, cfg.max_duration_seconds,
                cfg.min_play_count, cfg.publish_after_date or "不限")

    while total_fetched < cfg.max_videos_per_blogger:
        result = await rapid_api.search_videos(search_keyword, cursor=cursor, retry_delay=cfg.retry_delay)
        items = result["items"]

        for item in items:
            if total_fetched >= cfg.max_videos_per_blogger:
                break
            total_fetched += 1

            # 只保留属于当前博主的视频
            if item["unique_id"] != unique_id:
                continue
            # 时长过滤
            if item["duration"] > cfg.max_duration_seconds:
                continue
            # 播放量过滤
            if cfg.min_play_count > 0 and (item.get("play_count") or 0) < cfg.min_play_count:
                continue
            # 发布日期过滤
            if cutoff_ts > 0 and (item.get("create_time") or 0) < cutoff_ts:
                continue

            collected.append(item)

        if not result["has_more"] or not items:
            break
        cursor = result["next_cursor"]

    logger.info("【候选库】博主 %s 精搜完成，搜索总量=%d，合规视频数=%d",
                unique_id, total_fetched, len(collected))
    return collected


# ---------------------------------------------------------------------------
# AI 审核（EvoLink / Gemini）
# ---------------------------------------------------------------------------

async def _ai_review_single(
    video_url: str,
    prompt: str,
    model: str,
    api_key: str,
    api_base_url: str,
    retry_delay: float = 5.0,
) -> bool:
    """
    调用 EvoLink Gemini API 审核单条视频。
    返回 True 表示通过，False 表示不通过。
    遇到限流或网络错误时无限重试。
    """
    import json as _json

    url = f"{api_base_url.rstrip('/')}/v1beta/models/{model}:generateContent"

    json_instructions = (
        "\n\n请必须以JSON格式输出审核结果，只需包含一个字段：\n"
        "- \"pass\": 布尔值（true 表示通过审核，false 表示不通过）\n"
        "示例输出：\n"
        "{\"pass\": true}"
    )
    final_prompt = prompt + json_instructions

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"fileData": {"mimeType": "video/mp4", "fileUri": video_url}},
                    {"text": final_prompt},
                ],
            }
        ]
    }

    while True:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 429:
                    logger.warning("【候选库AI审核】被限流(429)，%.0fs后重试", retry_delay)
                    await asyncio.sleep(retry_delay)
                    continue
                resp.raise_for_status()
                data = resp.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("【候选库AI审核】原始响应: %s", text[:200])

            # 解析 JSON
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = _json.loads(cleaned)
            passed = bool(result.get("pass", True))
            logger.info("【候选库AI审核】结果: pass=%s", passed)
            return passed

        except Exception as exc:
            logger.warning("【候选库AI审核】请求异常，%.0fs后重试: %s", retry_delay, exc)
            await asyncio.sleep(retry_delay)


async def _ai_review_candidates(
    session: AsyncSession,
    keyword_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    cfg: _SearchConfig,
) -> None:
    """对新入库的候选视频进行 AI 审核，不通过的从数据库删除。"""
    if not cfg.ai_review_enabled or not cfg.ai_review_prompt.strip():
        logger.info("【候选库AI审核】未启用或提示词为空，跳过")
        return

    sys_settings = await get_or_create_system_settings(session)
    api_key = sys_settings.evolink_api_key
    api_base_url = sys_settings.evolink_api_base_url
    if not api_key:
        logger.warning("【候选库AI审核】EvoLink API key 未配置，跳过")
        return

    # 查询待审核的视频（本次关键词入库的）
    q = select(CandidateVideo).where(CandidateVideo.video_url.isnot(None))
    if keyword_id is not None:
        q = q.where(CandidateVideo.keyword_id == keyword_id)
    if owner_id is not None:
        q = q.where(CandidateVideo.owner_id == owner_id)

    rows = (await session.scalars(q)).all()
    if not rows:
        return

    logger.info("【候选库AI审核】开始审核 %d 条视频", len(rows))
    sem = asyncio.Semaphore(_CONCURRENCY_AI_REVIEW)
    to_delete: list[CandidateVideo] = []

    async def _review_one(row: CandidateVideo) -> None:
        async with sem:
            passed = await _ai_review_single(
                video_url=row.video_url,
                prompt=cfg.ai_review_prompt,
                model=cfg.ai_review_model,
                api_key=api_key,
                api_base_url=api_base_url,
            )
            if not passed:
                to_delete.append(row)
                logger.info("【候选库AI审核】视频 %s 未通过审核，将删除", row.video_id)

    tasks = [asyncio.create_task(_review_one(r)) for r in rows]
    await asyncio.gather(*tasks)

    if to_delete:
        for row in to_delete:
            await session.delete(row)
        await session.commit()
        logger.info("【候选库AI审核】已删除 %d 条未通过视频", len(to_delete))
    else:
        logger.info("【候选库AI审核】全部通过")


# ---------------------------------------------------------------------------
# 封面图上传 CDN
# ---------------------------------------------------------------------------

async def _upload_covers_batch(videos: list[dict[str, Any]]) -> None:
    """批量上传封面到 CDN，直接在 video dict 中写入 cdn_cover_url 字段。入库前调用。"""
    to_upload = [v for v in videos if v.get("cover_url")]
    if not to_upload:
        return

    sem = asyncio.Semaphore(_CONCURRENCY_COVER_UPLOAD)

    async def _upload_one(v: dict[str, Any]) -> None:
        async with sem:
            for attempt in range(1, 4):
                try:
                    result = await image_upload_service.upload_from_url(
                        v["cover_url"],
                        filename=f"candidate_{v['video_id']}.jpg",
                    )
                    cdn_url = result.get("url")
                    if cdn_url:
                        v["cdn_cover_url"] = cdn_url
                        logger.debug("【候选库】封面上传成功 video_id=%s cdn_url=%s", v["video_id"], cdn_url)
                    break
                except Exception as exc:
                    if attempt < 3:
                        logger.warning("【候选库】封面上传失败 video_id=%s (第%d次，准备重试): %s", v["video_id"], attempt, exc)
                        await asyncio.sleep(2)
                    else:
                        logger.warning("【候选库】封面上传失败 video_id=%s (已重试3次，放弃): %s", v["video_id"], exc)

    tasks = [asyncio.create_task(_upload_one(v)) for v in to_upload]
    await asyncio.gather(*tasks)
    logger.info("【候选库】本批 %d 张封面上传完成", len(to_upload))


# ---------------------------------------------------------------------------
# 共享视频裁剪：按播放量保留前 N 条
# ---------------------------------------------------------------------------

async def _trim_shared_top_n(
    session: AsyncSession,
    keyword_id: uuid.UUID,
    owner_id: uuid.UUID | None,
    top_n: int,
) -> None:
    """保留该关键词下共享视频播放量最高的 top_n 条，删除其余记录。"""
    q = select(CandidateVideo).where(
        CandidateVideo.keyword_id == keyword_id,
        CandidateVideo.template_type == "shared",
    )
    if owner_id is not None:
        q = q.where(CandidateVideo.owner_id == owner_id)

    rows = list((await session.scalars(q)).all())
    if len(rows) <= top_n:
        return

    # 按 play_count 降序排序，NULL 视为 0
    rows.sort(key=lambda r: r.play_count or 0, reverse=True)
    to_delete = rows[top_n:]
    delete_ids = [r.id for r in to_delete]

    await session.execute(
        sa_delete(CandidateVideo).where(CandidateVideo.id.in_(delete_ids))
    )
    await session.commit()
    logger.info("【候选库】共享视频裁剪：保留前 %d 条，删除 %d 条", top_n, len(delete_ids))


# ---------------------------------------------------------------------------
# 导入视频库
# ---------------------------------------------------------------------------

async def _get_or_create_tag(session: AsyncSession, name: str, owner_id: uuid.UUID | None) -> uuid.UUID:
    """按名称查找标签，不存在则创建，返回 tag.id。"""
    from app.models.tag import Tag
    tag = await session.scalar(
        select(Tag).where(Tag.name == name, Tag.owner_id == owner_id)
    )
    if tag is None:
        tag = Tag(owner_id=owner_id, name=name)
        session.add(tag)
        await session.flush()  # 获取 id，不提交事务
    return tag.id


async def _download_then_enqueue_template(
    vs_id: uuid.UUID,
    tpl_id: uuid.UUID,
    owner_id: uuid.UUID | None,
    blogger_name: str | None,
    keyword_text: str | None,
) -> None:
    """后台协程：等待视频下载完成后打标签并将模板入队。"""
    from app.db.session import SessionLocal
    from app.models.video_ai_template import VideoAITemplate
    from app.models.video_source import VideoSource
    from app.models.tag import VideoSourceTag
    from app.services.video_ai_service import enqueue_template

    # 轮询下载状态，直到 done
    while True:
        try:
            async with SessionLocal() as session:
                vs = await session.scalar(select(VideoSource).where(VideoSource.id == vs_id))
                if vs is None:
                    logger.warning("【候选库→模板】video_source %s 已被删除，取消入队", vs_id)
                    return
                if vs.download_status == "done":
                    break
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    logger.info("【候选库→模板】video_source %s 下载完成，开始打标签并入队 tpl_id=%s", vs_id, tpl_id)

    try:
        async with SessionLocal() as session:
            # ---- 打标签（关键词+博主名称拼接，get-or-create） ----
            tag_name_parts = [p.strip() for p in [keyword_text, blogger_name] if p and p.strip()]
            if tag_name_parts:
                combined_tag_name = " ".join(tag_name_parts)
                tid = await _get_or_create_tag(session, combined_tag_name, owner_id)
                # 视频打标签
                existing_vs_tag = await session.scalar(
                    select(VideoSourceTag).where(
                        VideoSourceTag.video_source_id == vs_id,
                        VideoSourceTag.tag_id == tid,
                    )
                )
                if existing_vs_tag is None:
                    session.add(VideoSourceTag(owner_id=owner_id, video_source_id=vs_id, tag_id=tid))
                # 模板打标签
                existing_tpl_tag = await session.scalar(
                    select(VideoSourceTag).where(
                        VideoSourceTag.video_ai_template_id == tpl_id,
                        VideoSourceTag.tag_id == tid,
                    )
                )
                if existing_tpl_tag is None:
                    session.add(VideoSourceTag(owner_id=owner_id, video_ai_template_id=tpl_id, tag_id=tid))

            await session.commit()

        await enqueue_template(str(tpl_id))
        logger.info("【候选库→模板】tpl_id=%s 已入队", tpl_id)
    except Exception as exc:
        logger.exception("【候选库→模板】tpl_id=%s 入队失败: %s", tpl_id, exc)


async def _import_to_video_library(
    session: AsyncSession,
    keyword_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> None:
    """将候选视频导入视频库（video_sources），完全复用 parse → create → download → 生成模板 四步流程。"""
    from app.schemas.video_source import VideoSourceCreate
    from app.services.video_source_service import (
        create_video_source,
        parse_video_url,
        trigger_download_and_upload,
    )

    _MAX_IMPORT_ATTEMPTS = 3

    q = select(CandidateVideo).where(
        CandidateVideo.video_url.isnot(None),
        CandidateVideo.video_source_id.is_(None),
        CandidateVideo.import_attempts < _MAX_IMPORT_ATTEMPTS,
    )
    if keyword_id is not None:
        q = q.where(CandidateVideo.keyword_id == keyword_id)
    if owner_id is not None:
        q = q.where(CandidateVideo.owner_id == owner_id)

    rows = list((await session.scalars(q)).all())
    if not rows:
        return

    total = len(rows)
    imported = 0
    skipped = 0

    logger.info("【候选库→视频库】开始导入 %d 条候选视频", total)

    for idx, cv in enumerate(rows, 1):
        try:
            # Step 1: Parse — 调 tikwm/RapidAPI 获取完整信息
            result = await parse_video_url(cv.video_url, session=session, owner_id=owner_id)

            if result.existing_id is not None:
                # 已存在，关联并跳过
                cv.video_source_id = result.existing_id
                await session.commit()
                skipped += 1
                logger.debug("【候选库→视频库】[%d/%d] 已存在，跳过 video_url=%s", idx, total, cv.video_url)
                continue

            # Step 2: Create — 用 parse 结果预填创建
            payload = VideoSourceCreate(
                source_url=result.source_url,
                platform=result.platform,
                blogger_name=result.blogger_name,
                video_title=result.video_title,
                video_desc=result.video_desc,
                video_url=result.video_url,
                thumbnail_url=result.thumbnail_url,
                view_count=result.view_count,
                like_count=result.like_count,
                favorite_count=result.favorite_count,
                comment_count=result.comment_count,
                share_count=result.share_count,
                publish_date=result.publish_date,
                duration=result.duration,
                width=result.width,
                height=result.height,
                aspect_ratio=result.aspect_ratio,
                extra=result.extra,
            )
            is_new, vs = await create_video_source(session, payload, owner_id)

            # 关联 video_source_id
            cv.video_source_id = vs.id
            await session.commit()

            if is_new:
                # Step 3: Download — 后台下载+上传
                await trigger_download_and_upload(session, vs.id, owner_id)

                # Step 4: 预先创建模板记录（pending，不入队），持久化后重启可恢复
                from app.models.enums import VideoAIProcessStatus
                from app.models.video_ai_template import VideoAITemplate
                tpl = VideoAITemplate(
                    owner_id=owner_id,
                    title=vs.video_title or vs.blogger_name or "新模板",
                    description="",
                    video_source_id=vs.id,
                    process_status=VideoAIProcessStatus.pending,
                )
                if getattr(vs, "tiktok_blogger_id", None) is not None:
                    tpl.tiktok_blogger_id = vs.tiktok_blogger_id
                session.add(tpl)
                await session.commit()
                await session.refresh(tpl)

                # 后台协程：等下载完成后打标签并入队
                asyncio.create_task(
                    _download_then_enqueue_template(
                        vs_id=vs.id,
                        tpl_id=tpl.id,
                        owner_id=owner_id,
                        blogger_name=vs.blogger_name,
                        keyword_text=cv.keyword_text,
                    )
                )
                imported += 1
                logger.info("【候选库→视频库】[%d/%d] 导入成功 video_url=%s vs_id=%s tpl_id=%s（等待下载后入队）", idx, total, cv.video_url, vs.id, tpl.id)
            else:
                skipped += 1
                logger.debug("【候选库→视频库】[%d/%d] 已存在（create去重），跳过 video_url=%s", idx, total, cv.video_url)

        except Exception as exc:
            cv.import_attempts = (cv.import_attempts or 0) + 1
            await session.commit()
            if cv.import_attempts >= _MAX_IMPORT_ATTEMPTS:
                logger.warning("【候选库→视频库】[%d/%d] 导入失败已达 %d 次上限，放弃 video_url=%s: %s", idx, total, _MAX_IMPORT_ATTEMPTS, cv.video_url, exc)
            else:
                logger.warning("【候选库→视频库】[%d/%d] 导入失败（第%d次） video_url=%s: %s", idx, total, cv.import_attempts, cv.video_url, exc)

    logger.info("【候选库→视频库】导入完成：共 %d 条，新导入 %d，跳过 %d", total, imported, skipped)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

async def run_candidate_search(
    session: AsyncSession,
    keyword_text: str,
    keyword_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    触发候选库搜索（后台异步任务，由 API 路由通过 asyncio.create_task 调用）。

    返回搜索摘要 {"template_type": "shared"|"exclusive", "video_count": int}。
    """
    # 读取配置（按用户；admin owner_id=None 时使用默认值）
    if owner_id is not None:
        cfg_row = await get_or_create_pipeline_settings(session, owner_id=owner_id)
        cfg = _SearchConfig(cfg_row)
    else:
        cfg = _SearchConfig(None)

    logger.info("【候选库】启动搜索 keyword=%s keyword_id=%s owner_id=%s 配置=%s",
                keyword_text, keyword_id, owner_id,
                f"max_bloggers={cfg.max_bloggers} threshold={cfg.exclusive_threshold} max_videos={cfg.max_videos_per_blogger} max_dur={cfg.max_duration_seconds}s")

    # 查询该关键词下已存在的博主（去重用）
    existing_bloggers: set[str] = set()
    if keyword_id is not None:
        rows = await session.scalars(
            select(CandidateVideo.blogger_unique_id).where(
                CandidateVideo.keyword_id == keyword_id,
                CandidateVideo.owner_id == owner_id,
            ).distinct()
        )
        existing_bloggers = set(rows.all())
        if existing_bloggers:
            logger.info("【候选库】该关键词已有 %d 个博主记录，将跳过这些博主", len(existing_bloggers))

    # 第一阶段：收集博主（排除已处理过的）
    bloggers = await _collect_bloggers(
        keyword_text, cfg.max_bloggers, cfg.retry_delay,
        exclude_bloggers=existing_bloggers,
    )

    # 第二阶段：补全粉丝数并排序
    bloggers = await _enrich_and_sort_bloggers(bloggers, cfg.retry_delay)

    # 第三阶段：依次精搜，判断共享/独享
    shared_videos: list[dict[str, Any]] = []  # 暂存已分类为 shared 的视频（可能被清除）
    final_type: str = "shared"

    for blogger in bloggers:
        videos = await _search_blogger_videos(keyword_text, blogger, cfg)

        if len(videos) >= cfg.exclusive_threshold:
            # 独享：清除已存共享，写入独享，停止
            logger.info("【候选库】博主 %s 命中独享阈值（%d >= %d），清除共享记录，写入独享",
                        blogger["unique_id"], len(videos), cfg.exclusive_threshold)

            # 删除本轮已写入数据库的共享记录
            if shared_videos:
                await session.execute(
                    sa_delete(CandidateVideo).where(
                        CandidateVideo.keyword_id == keyword_id,
                        CandidateVideo.owner_id == owner_id,
                        CandidateVideo.template_type == "shared",
                    )
                )
                await session.flush()

            # 写入独享视频（跳过已存在的重复记录）
            now = _utcnow()
            rows_to_insert = [
                dict(
                    id=uuid.uuid4(),
                    owner_id=owner_id,
                    keyword_id=keyword_id,
                    keyword_text=keyword_text,
                    template_type="exclusive",
                    blogger_unique_id=blogger["unique_id"],
                    blogger_nickname=blogger.get("nickname"),
                    blogger_follower_count=blogger.get("follower_count"),
                    video_id=v["video_id"],
                    video_url=v["video_url"],
                    video_title=v.get("video_title"),
                    duration=v["duration"],
                    cover_url=v.get("cover_url"),
                    play_count=v.get("play_count"),
                    like_count=v.get("like_count"),
                    created_at=now,
                )
                for v in videos
            ]
            await _upload_covers_batch(rows_to_insert)
            if rows_to_insert:
                stmt = pg_insert(CandidateVideo).values(rows_to_insert).on_conflict_do_nothing(
                    index_elements=["keyword_id", "blogger_unique_id", "video_id"]
                )
                await session.execute(stmt)

            await session.commit()
            await _ai_review_candidates(session, keyword_id, owner_id, cfg)
            await _import_to_video_library(session, keyword_id, owner_id)
            final_type = "exclusive"
            logger.info("【候选库】搜索完成，结果=独享，视频数=%d", len(videos))
            return {"template_type": "exclusive", "video_count": len(videos)}

        else:
            # 共享：写入，继续
            logger.info("【候选库】博主 %s 进入共享（%d < %d），继续下一个博主",
                        blogger["unique_id"], len(videos), cfg.exclusive_threshold)
            now = _utcnow()
            rows_to_insert = [
                dict(
                    id=uuid.uuid4(),
                    owner_id=owner_id,
                    keyword_id=keyword_id,
                    keyword_text=keyword_text,
                    template_type="shared",
                    blogger_unique_id=blogger["unique_id"],
                    blogger_nickname=blogger.get("nickname"),
                    blogger_follower_count=blogger.get("follower_count"),
                    video_id=v["video_id"],
                    video_url=v["video_url"],
                    video_title=v.get("video_title"),
                    duration=v["duration"],
                    cover_url=v.get("cover_url"),
                    play_count=v.get("play_count"),
                    like_count=v.get("like_count"),
                    created_at=now,
                )
                for v in videos
            ]
            await _upload_covers_batch(rows_to_insert)
            if rows_to_insert:
                stmt = pg_insert(CandidateVideo).values(rows_to_insert).on_conflict_do_nothing(
                    index_elements=["keyword_id", "blogger_unique_id", "video_id"]
                )
                await session.execute(stmt)
            shared_videos.extend(videos)

            await session.commit()

    total_shared = len(shared_videos)

    # 共享结果按播放量保留前 N 条，删除多余记录
    if cfg.shared_top_n > 0 and keyword_id is not None:
        await _trim_shared_top_n(session, keyword_id, owner_id, cfg.shared_top_n)

    await _ai_review_candidates(session, keyword_id, owner_id, cfg)
    await _import_to_video_library(session, keyword_id, owner_id)
    logger.info("【候选库】搜索完成，结果=共享，视频数=%d", total_shared)
    return {"template_type": "shared", "video_count": total_shared}


# ---------------------------------------------------------------------------
# 查询 / 删除
# ---------------------------------------------------------------------------

async def list_candidate_videos(
    session: AsyncSession,
    owner_id: uuid.UUID | None,
    *,
    keyword_id: uuid.UUID | None = None,
    template_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询候选视频"""
    q = select(CandidateVideo)

    if owner_id is not None:
        q = q.where(CandidateVideo.owner_id == owner_id)
    if keyword_id is not None:
        q = q.where(CandidateVideo.keyword_id == keyword_id)
    if template_type is not None:
        q = q.where(CandidateVideo.template_type == template_type)

    # 总数
    from sqlalchemy import func
    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.scalar(count_q)) or 0

    # 分页
    offset = (page - 1) * page_size
    rows = (await session.scalars(q.order_by(CandidateVideo.created_at.desc()).offset(offset).limit(page_size))).all()

    return {"total": total, "items": rows, "page": page, "page_size": page_size}


async def delete_candidate_video(
    session: AsyncSession,
    video_id: uuid.UUID,
    owner_id: uuid.UUID | None,
) -> bool:
    """删除单条候选视频，非 admin 需校验 owner"""
    row = await session.get(CandidateVideo, video_id)
    if row is None:
        return False
    if owner_id is not None and row.owner_id != owner_id:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def recover_candidate_imports_on_startup() -> None:
    """启动时恢复中断的候选视频导入：将 video_source_id IS NULL 的候选视频重新走导入流程。"""
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        q = select(CandidateVideo).where(
            CandidateVideo.video_url.isnot(None),
            CandidateVideo.video_source_id.is_(None),
            CandidateVideo.import_attempts < 3,
        )
        rows = list((await session.scalars(q)).all())

    if not rows:
        logger.info("No stuck candidate imports found on startup")
        return

    # 按 (owner_id, keyword_id) 分组，逐组调用 _import_to_video_library
    groups: dict[tuple, list] = {}
    for cv in rows:
        key = (str(cv.owner_id) if cv.owner_id else None, str(cv.keyword_id) if cv.keyword_id else None)
        groups.setdefault(key, []).append(cv)

    logger.info("Recovering %d stuck candidate imports (%d groups) on startup", len(rows), len(groups))

    for (oid_str, kid_str), _ in groups.items():
        owner_id = uuid.UUID(oid_str) if oid_str else None
        keyword_id = uuid.UUID(kid_str) if kid_str else None
        try:
            async with SessionLocal() as session:
                await _import_to_video_library(session, keyword_id, owner_id)
        except Exception:
            logger.exception("Failed to recover candidate imports for owner=%s keyword=%s", oid_str, kid_str)

    logger.info("Candidate import recovery finished")
