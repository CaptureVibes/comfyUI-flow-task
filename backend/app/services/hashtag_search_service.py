"""
标签搜索服务（Hashtag Search Service）

流程：
1. 根据传入的 account_ids，找到各账号绑定的 TikTok 博主
2. 用 Apify 抓取每个博主最热门的前 top_n 个视频（按播放量排序）
3. 提取所有视频的 hashtag，去重
4. 调用 AI（Gemini）根据 hashtag_filter_prompt 进行过滤，返回 JSON 列表
5. 返回结果

AI 返回格式（在提示词末尾强制拼接）：
{"hashtags": ["tag1", "tag2", ...]}
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal

logger = logging.getLogger("app.hashtag_search_service")

_JSON_FORMAT_INSTRUCTION = (
    "\n\n请严格以 JSON 格式返回，不要包含任何其他文字：\n"
    '{"hashtags": ["hashtag1", "hashtag2", ...]}'
)

_MAX_ATTEMPTS = 3


def _extract_json_hashtags(text: str) -> list[str] | None:
    """从 AI 返回文本中提取 hashtags 列表。"""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        tags = data.get("hashtags")
        if isinstance(tags, list):
            return [str(t).strip().lstrip("#") for t in tags if t]
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


async def search_hashtags_for_accounts(
    account_ids: list[str],
    owner_id: str,
) -> dict[str, Any]:
    """
    为指定账号列表执行标签搜索。

    Returns:
        {
            "raw_hashtags": [...],         # 去重后全量 hashtag
            "filtered_hashtags": [...],    # AI 过滤后的 hashtag
            "blogger_handles": [...],      # 被搜索的博主 handle 列表
            "video_count": int,            # 抓取的总视频数
        }
    """
    import uuid as _uuid
    from app.models.account import Account
    from app.models.account_blogger_binding import AccountBloggerBinding
    from app.models.tiktok_blogger import TiktokBlogger
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings

    async with SessionLocal() as session:
        # 读取配置
        cfg = await get_or_create_pipeline_settings(session, owner_id=_uuid.UUID(owner_id))
        top_n: int = cfg.hashtag_search_top_n or 100
        filter_model: str = cfg.hashtag_filter_model or "gemini-3.1-pro-preview"
        filter_prompt: str = cfg.hashtag_filter_prompt or ""

        # 收集所有绑定的 TikTok 博主
        acc_uuids = [_uuid.UUID(aid) for aid in account_ids]
        blogger_stmt = (
            select(TiktokBlogger)
            .join(AccountBloggerBinding, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
            .where(AccountBloggerBinding.account_id.in_(acc_uuids))
        )
        bloggers = (await session.execute(blogger_stmt)).scalars().all()

    if not bloggers:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": [],
            "video_count": 0,
            "error": "所选账号没有绑定任何 TikTok 博主",
        }

    # 去重博主（按 blogger_handle）
    seen_handles: set[str] = set()
    unique_bloggers = []
    for b in bloggers:
        handle = (b.blogger_handle or "").strip()
        if handle and handle not in seen_handles:
            seen_handles.add(handle)
            unique_bloggers.append(b)

    if not unique_bloggers:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": [],
            "video_count": 0,
            "error": "所选账号的博主缺少 TikTok handle，无法搜索",
        }

    handles = [b.blogger_handle for b in unique_bloggers]
    logger.info("[hashtag_search] 开始搜索，博主 handles=%s top_n=%d", handles, top_n)

    # 用 asyncio.to_thread 调用同步的 Apify SDK
    from app.utils.apify import TikTokApifyClient, TikTokFilter, SortOrder, DateRange

    def _apify_search() -> list:
        client = TikTokApifyClient()
        videos = client.search(
            profiles=handles,
            results_per_page=top_n,
            date_range=DateRange.all_time,
            filter_params=TikTokFilter(
                sort_by=SortOrder.play_count,
                sort_descending=True,
            ),
        )
        return videos

    try:
        videos = await asyncio.to_thread(_apify_search)
    except Exception as exc:
        logger.error("[hashtag_search] Apify 搜索失败: %s", exc)
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": handles,
            "video_count": 0,
            "error": f"Apify 搜索失败：{exc}",
        }

    logger.info("[hashtag_search] Apify 返回 %d 个视频", len(videos))

    # 过滤：只保留作者 handle 确实在目标集合内的视频
    target_handles_lower = {h.lower() for h in handles}
    filtered_videos = [
        v for v in videos
        if (v.author.name or "").lower() in target_handles_lower
    ]
    skipped = len(videos) - len(filtered_videos)
    if skipped:
        logger.info("[hashtag_search] 过滤掉非目标博主视频 %d 条（共 %d 条）", skipped, len(videos))

    # 提取 hashtag，去重（保留首次出现的大小写形式，用小写做去重 key）
    seen_lower: set[str] = set()
    raw_hashtags: list[str] = []
    for video in filtered_videos:
        for ht in video.hashtags:
            name = (ht.name or "").strip()
            if name and name.lower() not in seen_lower:
                seen_lower.add(name.lower())
                raw_hashtags.append(name)

    logger.info("[hashtag_search] 去重后 hashtag 数量: %d", len(raw_hashtags))

    if not raw_hashtags:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": handles,
            "video_count": len(filtered_videos),
        }

    # AI 过滤
    filtered_hashtags: list[str] = raw_hashtags  # 默认全量返回

    if filter_prompt.strip():
        from app.services.ai_api import call_gemini_api

        hashtag_list_str = ", ".join(f"#{t}" for t in raw_hashtags)
        full_prompt = (
            filter_prompt.strip()
            + f"\n\n待筛选的 Hashtag 列表（共 {len(raw_hashtags)} 个）：\n{hashtag_list_str}"
            + _JSON_FORMAT_INSTRUCTION
        )

        ai_result: list[str] | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                raw_text = await call_gemini_api(
                    model_name=filter_model,
                    prompt=full_prompt,
                    temperature=0.3,
                )
                ai_result = _extract_json_hashtags(raw_text)
                if ai_result is not None:
                    break
                logger.warning("[hashtag_search] 第 %d 次 AI 过滤 JSON 解析失败，原文: %s", attempt, raw_text[:200])
            except Exception as exc:
                logger.warning("[hashtag_search] 第 %d 次 AI 过滤调用失败: %s", attempt, exc)

        if ai_result is not None:
            filtered_hashtags = ai_result
            logger.info("[hashtag_search] AI 过滤后 hashtag 数量: %d", len(filtered_hashtags))
        else:
            logger.error("[hashtag_search] AI 过滤全部失败，回退到全量 hashtag")
    else:
        logger.info("[hashtag_search] 未配置过滤提示词，跳过 AI 过滤，返回全量 hashtag")

    return {
        "raw_hashtags": raw_hashtags,
        "filtered_hashtags": filtered_hashtags,
        "blogger_handles": handles,
        "video_count": len(filtered_videos),
    }


async def _search_hashtags_for_handles(
    *,
    handles: list[str],
    top_n: int,
    filter_model: str,
    filter_prompt: str,
    log_prefix: str,
) -> dict[str, Any]:
    """对一组 handle 执行一次 Apify 搜索 + AI 过滤。"""
    if not handles:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": [],
            "video_count": 0,
            "error": "缺少可搜索的 TikTok handle",
        }

    logger.info("%s 开始搜索，博主 handles=%s top_n=%d", log_prefix, handles, top_n)

    from app.utils.apify import DateRange, SortOrder, TikTokApifyClient, TikTokFilter

    def _apify_search() -> list:
        client = TikTokApifyClient()
        return client.search(
            profiles=handles,
            results_per_page=top_n,
            date_range=DateRange.all_time,
            filter_params=TikTokFilter(
                sort_by=SortOrder.play_count,
                sort_descending=True,
            ),
        )

    try:
        videos = await asyncio.to_thread(_apify_search)
    except Exception as exc:
        logger.error("%s Apify 搜索失败: %s", log_prefix, exc)
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": handles,
            "video_count": 0,
            "error": f"Apify 搜索失败：{exc}",
        }

    logger.info("%s Apify 返回 %d 个视频", log_prefix, len(videos))

    target_handles_lower = {h.lower() for h in handles}
    filtered_videos = [
        v for v in videos
        if (v.author.name or "").lower() in target_handles_lower
    ]
    skipped = len(videos) - len(filtered_videos)
    if skipped:
        logger.info("%s 过滤掉非目标博主视频 %d 条（共 %d 条）", log_prefix, skipped, len(videos))

    seen_lower: set[str] = set()
    raw_hashtags: list[str] = []
    for video in filtered_videos:
        for ht in video.hashtags:
            name = (ht.name or "").strip()
            if name and name.lower() not in seen_lower:
                seen_lower.add(name.lower())
                raw_hashtags.append(name)

    logger.info("%s 去重后 hashtag 数量: %d", log_prefix, len(raw_hashtags))

    if not raw_hashtags:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": handles,
            "video_count": len(filtered_videos),
        }

    filtered_hashtags: list[str] = raw_hashtags
    if filter_prompt.strip():
        from app.services.ai_api import call_gemini_api

        hashtag_list_str = ", ".join(f"#{t}" for t in raw_hashtags)
        full_prompt = (
            filter_prompt.strip()
            + f"\n\n待筛选的 Hashtag 列表（共 {len(raw_hashtags)} 个）：\n{hashtag_list_str}"
            + _JSON_FORMAT_INSTRUCTION
        )

        ai_result: list[str] | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                raw_text = await call_gemini_api(
                    model_name=filter_model,
                    prompt=full_prompt,
                    temperature=0.3,
                )
                ai_result = _extract_json_hashtags(raw_text)
                if ai_result is not None:
                    break
                logger.warning("%s 第 %d 次 AI 过滤 JSON 解析失败，原文: %s", log_prefix, attempt, raw_text[:200])
            except Exception as exc:
                logger.warning("%s 第 %d 次 AI 过滤调用失败: %s", log_prefix, attempt, exc)

        if ai_result is not None:
            filtered_hashtags = ai_result
            logger.info("%s AI 过滤后 hashtag 数量: %d", log_prefix, len(filtered_hashtags))
        else:
            logger.error("%s AI 过滤全部失败，回退到全量 hashtag", log_prefix)
    else:
        logger.info("%s 未配置过滤提示词，跳过 AI 过滤，返回全量 hashtag", log_prefix)

    return {
        "raw_hashtags": raw_hashtags,
        "filtered_hashtags": filtered_hashtags,
        "blogger_handles": handles,
        "video_count": len(filtered_videos),
    }


async def search_hashtags_for_account(
    account_id: str,
    owner_id: str,
    *,
    top_n: int,
    filter_model: str,
    filter_prompt: str,
) -> dict[str, Any]:
    """单个账号单独执行一次 hashtag 搜索。"""
    import uuid as _uuid
    from app.models.account import Account as _Account
    from app.models.account_blogger_binding import AccountBloggerBinding
    from app.models.tiktok_blogger import TiktokBlogger

    account_uuid = _uuid.UUID(account_id)
    owner_uuid = _uuid.UUID(owner_id)
    log_prefix = f"[hashtag_search][account={account_id}]"

    async with SessionLocal() as session:
        blogger_stmt = (
            select(TiktokBlogger)
            .join(AccountBloggerBinding, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
            .join(_Account, _Account.id == AccountBloggerBinding.account_id)
            .where(AccountBloggerBinding.account_id == account_uuid)
            .where(_Account.owner_id == owner_uuid)
        )
        bloggers = (await session.execute(blogger_stmt)).scalars().all()

    if not bloggers:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": [],
            "video_count": 0,
            "error": "账号没有绑定任何 TikTok 博主",
        }

    seen_handles: set[str] = set()
    handles: list[str] = []
    for blogger in bloggers:
        handle = (blogger.blogger_handle or "").strip()
        if handle and handle not in seen_handles:
            seen_handles.add(handle)
            handles.append(handle)

    if not handles:
        return {
            "raw_hashtags": [],
            "filtered_hashtags": [],
            "blogger_handles": [],
            "video_count": 0,
            "error": "账号绑定的博主缺少 TikTok handle，无法搜索",
        }

    return await _search_hashtags_for_handles(
        handles=handles,
        top_n=top_n,
        filter_model=filter_model,
        filter_prompt=filter_prompt,
        log_prefix=log_prefix,
    )


async def search_and_bind_hashtags_for_accounts(
    account_ids: list[str],
    owner_id: str,
    mode: str = "replace",
) -> None:
    """
    后台异步任务：搜索 hashtag 并写入各账号的 hashtags 字段。
    mode='replace'：覆盖；mode='merge'：追加合并去重。
    每个账号单独调用一次 Apify 搜索；并发受 Semaphore 控制，当前为 1。
    """
    import uuid as _uuid
    from sqlalchemy import select as _select
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.account import Account as _Account
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings

    logger.info("[hashtag_search] 异步任务开始: %d 个账号, mode=%s", len(account_ids), mode)

    async with SessionLocal() as session:
        cfg = await get_or_create_pipeline_settings(session, owner_id=_uuid.UUID(owner_id))
        top_n: int = cfg.hashtag_search_top_n or 100
        filter_model: str = cfg.hashtag_filter_model or "gemini-3.1-pro-preview"
        filter_prompt: str = cfg.hashtag_filter_prompt or ""

    semaphore = asyncio.Semaphore(3)
    updated_count = 0
    empty_count = 0
    failed_count = 0

    async def _process_one(account_id: str) -> None:
        nonlocal updated_count, empty_count, failed_count
        async with semaphore:
            result = await search_hashtags_for_account(
                account_id=account_id,
                owner_id=owner_id,
                top_n=top_n,
                filter_model=filter_model,
                filter_prompt=filter_prompt,
            )

            if result.get("error"):
                failed_count += 1
                logger.error("[hashtag_search][account=%s] 失败: %s", account_id, result["error"])
                return

            final_tags: list[str] = result.get("filtered_hashtags") or []
            if not final_tags:
                empty_count += 1
                logger.warning("[hashtag_search][account=%s] filtered_hashtags 为空，不写入", account_id)
                return

            async with SessionLocal() as session:
                acc = await session.scalar(
                    _select(_Account).where(_Account.id == _uuid.UUID(account_id))
                )
                if not acc:
                    failed_count += 1
                    logger.error("[hashtag_search][account=%s] 账号不存在", account_id)
                    return

                if mode == "merge":
                    if acc.hashtags:
                        existing_lower = {t.lower() for t in acc.hashtags}
                        merged = list(acc.hashtags) + [t for t in final_tags if t.lower() not in existing_lower]
                        acc.hashtags = merged
                    else:
                        acc.hashtags = list(final_tags)
                    flag_modified(acc, "hashtags")
                else:
                    acc.hashtags = list(final_tags)
                    flag_modified(acc, "hashtags")

                await session.commit()
                updated_count += 1
                logger.info(
                    "[hashtag_search][account=%s] 写入完成: hashtags=%d mode=%s handles=%s videos=%s",
                    account_id,
                    len(final_tags),
                    mode,
                    result.get("blogger_handles") or [],
                    result.get("video_count") or 0,
                )

    await asyncio.gather(*[_process_one(account_id) for account_id in account_ids])

    logger.info(
        "[hashtag_search] 异步任务完成: updated=%d empty=%d failed=%d mode=%s accounts=%d concurrency=%d",
        updated_count,
        empty_count,
        failed_count,
        mode,
        len(account_ids),
        3,
    )
