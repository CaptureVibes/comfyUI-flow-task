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


async def search_and_bind_hashtags_for_accounts(
    account_ids: list[str],
    owner_id: str,
    mode: str = "replace",
) -> None:
    """
    后台异步任务：搜索 hashtag 并写入各账号的 hashtags 字段。
    mode='replace'：覆盖；mode='merge'：追加合并去重。
    """
    import uuid as _uuid

    logger.info("[hashtag_search] 异步任务开始: %d 个账号, mode=%s", len(account_ids), mode)

    result = await search_hashtags_for_accounts(account_ids=account_ids, owner_id=owner_id)

    if result.get("error"):
        logger.error("[hashtag_search] 异步任务失败: %s", result["error"])
        return

    final_tags: list[str] = result.get("filtered_hashtags") or []
    if not final_tags:
        logger.warning("[hashtag_search] 异步任务完成，但 filtered_hashtags 为空，不写入")
        return

    async with SessionLocal() as session:
        from app.models.account import Account as _Account
        from sqlalchemy import select as _select, update as _update
        from sqlalchemy.orm.attributes import flag_modified

        if mode == "merge":
            # merge 模式需要逐个读取现有值再合并
            accs = (
                await session.execute(
                    _select(_Account).where(_Account.id.in_([_uuid.UUID(aid) for aid in account_ids]))
                )
            ).scalars().all()
            for acc in accs:
                if acc.hashtags:
                    existing_lower = {t.lower() for t in acc.hashtags}
                    merged = list(acc.hashtags) + [t for t in final_tags if t.lower() not in existing_lower]
                    acc.hashtags = merged
                else:
                    acc.hashtags = list(final_tags)
                flag_modified(acc, "hashtags")
            updated_count = len(accs)
        else:
            # replace 模式直接批量 UPDATE，无需逐行加载
            result = await session.execute(
                _update(_Account)
                .where(_Account.id.in_([_uuid.UUID(aid) for aid in account_ids]))
                .values(hashtags=final_tags)
            )
            updated_count = result.rowcount

        await session.commit()

    logger.info(
        "[hashtag_search] 异步任务完成: 已为 %d 个账号写入 %d 个 hashtag (mode=%s)",
        updated_count, len(final_tags), mode,
    )
