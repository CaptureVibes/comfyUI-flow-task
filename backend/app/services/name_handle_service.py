"""
批量生成账号名称 / Handle / 签名服务

分支逻辑：
  - exclusive / persona：基于绑定的 TikTok 博主信息和头像生成
    占位符：{blogger_name}, {blogger_handle}, {blogger_signature}, {avatar_url}, {photo_url}
  - shared：基于绑定的标签关键词生成
    占位符：{keyword}, {avatar_url}, {photo_url}

返回 JSON：{"name": "...", "handle": "...", "signature": "...", "gender": "..."}
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal

logger = logging.getLogger("app.name_handle_service")

_CONCURRENCY = 5
_MAX_ATTEMPTS = 3

# 所有自动生成的 AI 博主签名末尾统一拼接此引流 suffix
_SIGNATURE_BIO_SUFFIX = "Outfits from my videos are available through the link below 💗"


def _ensure_signature_suffix(signature: str) -> str:
    """确保签名末尾带有引流 suffix；已包含则原样返回（幂等）。"""
    s = (signature or "").rstrip()
    if _SIGNATURE_BIO_SUFFIX in s:
        return s
    if s:
        return f"{s}\n\n{_SIGNATURE_BIO_SUFFIX}"
    return _SIGNATURE_BIO_SUFFIX

_queue: asyncio.Queue[str] = asyncio.Queue()
_worker_task: asyncio.Task | None = None

_JSON_FORMAT_INSTRUCTION = (
    '\n\n请严格以 JSON 格式返回，不要包含任何其他文字：\n'
    '{"name": "博主名称", "handle": "博主handle（不含@，字母数字下划线）", '
    '"signature": "个人签名", "gender": "male/female/unisex"}'
    '\n其中 gender 只能是 male、female、unisex 三者之一。'
)

_DEFAULT_EXCLUSIVE_PROMPT = (
    "请根据参考头像图和关联 TikTok 博主资料，为新的 AI 博主生成账号名称、handle、个人签名，"
    "并判断账号性别定位。名称和签名要适合社交平台账号，handle 不要包含 @，只能使用英文字母、数字和下划线。"
)

_DEFAULT_SHARED_PROMPT = (
    "请根据参考头像图和账号关键词，为新的共享 AI 博主生成账号名称、handle、个人签名，"
    "并判断账号性别定位。名称和签名要适合社交平台账号，handle 不要包含 @，只能使用英文字母、数字和下划线。"
)

_NAME_HANDLE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "handle": {"type": "string"},
        "signature": {"type": "string"},
        "gender": {
            "type": "string",
            "enum": ["male", "female", "unisex"],
        },
    },
    "required": ["name", "handle", "signature", "gender"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fill_prompt(template: str, **kwargs: str) -> str:
    """将 {key} 占位符替换为对应值，缺失的 key 替换为空字符串。"""
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{key}}}", value or "")
    return result


def _extract_json(text: str) -> dict | None:
    """从文本中提取第一个 JSON 对象。"""
    # 去掉 markdown 代码块
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _normalize_gender(value: object) -> str:
    gender = str(value or "").strip().lower()
    return gender if gender in {"male", "female", "unisex"} else ""


def _normalize_handle(value: object) -> str:
    handle = str(value or "").strip().lstrip("@")
    handle = re.sub(r"\s+", "_", handle)
    handle = re.sub(r"[^A-Za-z0-9_]", "", handle)
    return handle[:200]


def _build_context(
    *,
    avatar_url: str,
    photo_url: str,
    blogger_name: str,
    blogger_handle: str,
    blogger_signature: str,
    keyword: str,
) -> str:
    lines = ["补充上下文："]
    if avatar_url:
        lines.append(f"- 已生成头像 URL：{avatar_url}")
        lines.append("- 请求中已附上头像参考图，请优先根据头像的外貌、气质和性别表达判断 gender。")
    if photo_url:
        lines.append(f"- 人工选择照片 URL：{photo_url}")
    if blogger_name or blogger_handle or blogger_signature:
        lines.append(f"- 关联 TikTok 博主名称：{blogger_name}")
        lines.append(f"- 关联 TikTok 博主 handle：{blogger_handle}")
        lines.append(f"- 关联 TikTok 博主签名：{blogger_signature}")
    if keyword:
        lines.append(f"- 账号关键词：{keyword}")
    lines.append("- 生成结果必须是新 AI 博主账号的信息，不要直接照抄关联 TikTok 博主。")
    return "\n".join(lines)


async def enqueue_name_handle_generation(account_ids: list[str]) -> int:
    """将账号 ID 列表入队，确保 worker 在运行，返回实际入队数量。"""
    global _worker_task

    for aid in account_ids:
        await _queue.put(aid)

    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_queue_processor())

    return len(account_ids)


async def _queue_processor() -> None:
    """并发处理队列中的账号。"""
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _process(account_id: str) -> None:
        async with sem:
            try:
                await _generate_for_account(account_id)
            except Exception as exc:
                logger.error("[名称生成] 账号 %s 处理失败: %s", account_id, exc)

    tasks: list[asyncio.Task] = []
    while True:
        try:
            account_id = _queue.get_nowait()
        except asyncio.QueueEmpty:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
            break
        task = asyncio.create_task(_process(account_id))
        tasks.append(task)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def generate_name_handle_for_account(
    account_id: str,
    *,
    avatar_url: str | None = None,
    photo_url: str | None = None,
) -> dict[str, str] | None:
    """同步生成单个账号名称/handle/签名/性别，供 AI 博主管道串行调用。"""
    return await _generate_for_account(
        account_id,
        avatar_url=avatar_url,
        photo_url=photo_url,
        require_configured_prompt=False,
    )


async def _unique_name(session, base_name: str, owner_id, exclude_id) -> str:
    """返回同 owner 下不重复的账号名。若 base_name 已存在则追加 -1、-2 …"""
    from app.models.account import Account as _Account
    base_name = base_name[:200]
    candidate = base_name
    suffix = 1
    while True:
        stmt = select(_Account.id).where(_Account.account_name == candidate)
        if owner_id is not None:
            stmt = stmt.where(_Account.owner_id == owner_id)
        if exclude_id is not None:
            stmt = stmt.where(_Account.id != exclude_id)
        dup = await session.scalar(stmt.limit(1))
        if not dup:
            return candidate
        suffix_token = f"-{suffix}"
        candidate = f"{base_name[:200 - len(suffix_token)]}{suffix_token}"
        suffix += 1


async def _unique_handle(session, base_handle: str, owner_id, exclude_id) -> str:
    """返回同 owner 下不重复的 handle。若 base_handle 已存在则追加 _1、_2 …"""
    from app.models.account import Account as _Account
    base_handle = base_handle[:200]
    candidate = base_handle
    suffix = 1
    while True:
        stmt = select(_Account.id).where(_Account.account_handle == candidate)
        if owner_id is not None:
            stmt = stmt.where(_Account.owner_id == owner_id)
        if exclude_id is not None:
            stmt = stmt.where(_Account.id != exclude_id)
        dup = await session.scalar(stmt.limit(1))
        if not dup:
            return candidate
        suffix_token = f"_{suffix}"
        candidate = f"{base_handle[:200 - len(suffix_token)]}{suffix_token}"
        suffix += 1


async def _generate_for_account(
    account_id: str,
    *,
    avatar_url: str | None = None,
    photo_url: str | None = None,
    require_configured_prompt: bool = True,
) -> dict[str, str] | None:
    """为单个账号生成名称/handle/签名/性别并写回数据库。"""
    from app.models.account import Account
    from app.models.account_blogger_binding import AccountBloggerBinding
    from app.models.account_tag import AccountTag
    from app.models.tag import Tag
    from app.models.tiktok_blogger import TiktokBlogger
    from app.services.ai_api import call_gemini_api, call_gemini_api_with_images
    from app.services.pipeline_settings_service import get_or_create_pipeline_settings

    import uuid as _uuid

    async with SessionLocal() as session:
        try:
            account_uuid = _uuid.UUID(account_id)
        except ValueError:
            logger.warning("[名称生成] 账号 ID 非法: %s", account_id)
            return None

        acc = await session.get(Account, account_uuid)
        if not acc:
            logger.warning("[名称生成] 账号 %s 不存在，跳过", account_id)
            return None

        # 读取配置
        if acc.owner_id:
            cfg = await get_or_create_pipeline_settings(session, owner_id=acc.owner_id)
            model_name = cfg.ai_account_name_model or "gemini-3.1-pro-preview"
            exclusive_prompt = cfg.ai_account_exclusive_name_prompt or ""
            shared_prompt = cfg.ai_account_shared_name_prompt or ""
        else:
            model_name = "gemini-3.1-pro-preview"
            exclusive_prompt = ""
            shared_prompt = ""

        account_type = acc.account_type or "exclusive"
        avatar_url = (avatar_url or acc.avatar_url or "").strip()
        photo_url = (photo_url or acc.photo_url or "").strip()

        # 查询第一个绑定的 TikTok 博主，所有账号类型都可作为命名上下文。
        blogger_stmt = (
            select(TiktokBlogger)
            .join(AccountBloggerBinding, AccountBloggerBinding.tiktok_blogger_id == TiktokBlogger.id)
            .where(AccountBloggerBinding.account_id == acc.id)
            .limit(1)
        )
        blogger = (await session.execute(blogger_stmt)).scalars().first()
        blogger_name = (blogger.blogger_name or "") if blogger else ""
        blogger_handle = (blogger.blogger_handle or "") if blogger else ""
        blogger_signature = (blogger.signature or "") if blogger else ""

        if account_type in ("exclusive", "persona") and not blogger:
            logger.warning("[名称生成] 账号 %s 没有绑定 TikTok 博主，将以空占位符继续", account_id)

        # 根据账号类型构建 prompt
        if account_type in ("exclusive", "persona"):
            base_prompt = exclusive_prompt or ""
            if not base_prompt and require_configured_prompt:
                logger.warning("[名称生成] 账号 %s 类型=%s，但未配置独享号/人设号 Prompt，跳过", account_id, account_type)
                return None
            if not base_prompt:
                base_prompt = _DEFAULT_EXCLUSIVE_PROMPT

            prompt = _fill_prompt(
                base_prompt,
                blogger_name=blogger_name,
                blogger_handle=blogger_handle,
                blogger_signature=blogger_signature,
                avatar_url=avatar_url,
                photo_url=photo_url,
            )
            keyword = ""

        else:  # shared
            base_prompt = shared_prompt or ""
            if not base_prompt and require_configured_prompt:
                logger.warning("[名称生成] 账号 %s 类型=shared，但未配置共享号 Prompt，跳过", account_id)
                return None
            if not base_prompt:
                base_prompt = _DEFAULT_SHARED_PROMPT

            # 查询绑定的所有标签
            stmt = (
                select(Tag.name)
                .join(AccountTag, AccountTag.tag_id == Tag.id)
                .where(AccountTag.account_id == acc.id)
            )
            tag_names = list((await session.execute(stmt)).scalars().all())

            if not tag_names:
                logger.warning("[名称生成] 账号 %s (shared) 没有绑定标签，将以空 keyword 继续", account_id)

            keyword = ", ".join(tag_names)
            prompt = _fill_prompt(
                base_prompt,
                keyword=keyword,
                avatar_url=avatar_url,
                photo_url=photo_url,
                blogger_name=blogger_name,
                blogger_handle=blogger_handle,
                blogger_signature=blogger_signature,
            )

        full_prompt = "\n\n".join([
            prompt,
            _build_context(
                avatar_url=avatar_url,
                photo_url=photo_url,
                blogger_name=blogger_name,
                blogger_handle=blogger_handle,
                blogger_signature=blogger_signature,
                keyword=keyword,
            ),
            _JSON_FORMAT_INSTRUCTION,
        ])
        image_urls: list[str] = []
        for image_url in (avatar_url, photo_url):
            if image_url and image_url not in image_urls:
                image_urls.append(image_url)

        # 调用 AI，最多重试 _MAX_ATTEMPTS 次
        result: dict | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                if image_urls:
                    raw = await call_gemini_api_with_images(
                        model_name=model_name,
                        prompt=full_prompt,
                        image_urls=image_urls,
                        temperature=0.9,
                        response_schema=_NAME_HANDLE_RESPONSE_SCHEMA,
                    )
                else:
                    raw = await call_gemini_api(
                        model_name=model_name,
                        prompt=full_prompt,
                        temperature=0.9,
                        response_schema=_NAME_HANDLE_RESPONSE_SCHEMA,
                    )
                result = _extract_json(raw)
                if result and "name" in result:
                    break
                logger.warning("[名称生成] 账号 %s 第 %d 次尝试 JSON 解析失败，原始: %s", account_id, attempt, raw[:200])
            except Exception as exc:
                logger.warning("[名称生成] 账号 %s 第 %d 次 API 调用失败: %s", account_id, attempt, exc)

        if not result or "name" not in result:
            logger.error("[名称生成] 账号 %s 生成失败，放弃写入", account_id)
            return None

        new_name = str(result.get("name") or "").strip()
        new_handle = _normalize_handle(result.get("handle"))
        new_signature = _ensure_signature_suffix(str(result.get("signature") or "").strip())
        new_gender = _normalize_gender(result.get("gender"))

        # 重复检测：同 owner 下不允许相同 name 或 handle（排除自身），重复则自动追加后缀
        owner_id = acc.owner_id
        if new_name:
            new_name = await _unique_name(session, new_name, owner_id, acc.id)
        if new_handle:
            new_handle = await _unique_handle(session, new_handle, owner_id, acc.id)

        if new_name:
            acc.account_name = new_name
        acc.account_handle = new_handle or None
        acc.account_signature = new_signature or None
        if new_gender:
            acc.gender = new_gender
        acc.updated_at = _utcnow()
        await session.commit()

        logger.info(
            "[名称生成] 账号 %s 更新完成: name=%r handle=%r",
            account_id, new_name, new_handle,
        )
        return {
            "name": new_name,
            "handle": new_handle,
            "signature": new_signature,
            "gender": new_gender,
        }
