"""KOL 创建（仅创建，不生成长/短链）。

Account 创建成功（手动）或 AI 生成完成（自动）后同步调用
``provision_kol_for_account``，只做一件事：调站内平台
POST /open-api/v1/internal-platform/kol 拿到 kol_user_id（接口 data.user_id）
写回 accounts。

长链 / 短链由其它流程在需要时按 ``kol_user_id`` 现算 —— 这里以独立函数
``build_long_link`` / ``encode_short_link`` 暴露，给其他模块复用。

任何失败都只把 ``kol_provision_status='failed'`` + ``kol_provision_error`` 写库，
不抛回外层；外层账号创建本身永远不被这一步阻塞。
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.account import Account
from app.services.open_api_signing import sign_params

logger = logging.getLogger("app.kol_service")

SOURCE_PLATFORM = "echo-matrix"  # 站内项目代号，下游已纳入白名单
SUPPORTED_LINK_PLATFORMS: tuple[str, ...] = ("tiktok", "youtube", "instagram")
_HTTP_TIMEOUT_SEC = 30.0


def build_long_link(kol_user_id: str, platform: str) -> str:
    """按平台规则拼长链。YouTube 多一个 sf=youtube_short_us。"""
    base = settings.kol_long_link_base_url
    if platform == "youtube":
        return f"{base}?kolUserId={kol_user_id}&sf=youtube_short_us"
    return f"{base}?kolUserId={kol_user_id}"


async def create_kol_via_open_api(account: Account) -> dict[str, Any]:
    """调用站内平台 KOL 创建接口，返回 data dict（含 id / user_id / nickname 等）。"""
    body: dict[str, Any] = {
        "nickname": account.account_name,
        "source_platform": SOURCE_PLATFORM,
        "source_user_id": str(account.id),
    }
    if account.account_signature:
        body["description"] = account.account_signature
    if account.avatar_url:
        body["avatar"] = {"url": account.avatar_url}
    if account.hashtags:
        # 兜底兼容历史数据可能存的不是 list
        if isinstance(account.hashtags, list):
            body["tags"] = [str(t) for t in account.hashtags if t]
        else:
            body["tags"] = [str(account.hashtags)]

    client_id = settings.open_api_client_id
    client_secret = settings.open_api_client_secret
    if not client_secret:
        raise RuntimeError("OPEN_API_CLIENT_SECRET 未配置，无法调用 KOL 创建接口")

    signed_body = sign_params(body, client_id, client_secret)
    url = f"{settings.open_api_base_url.rstrip('/')}/open-api/v1/internal-platform/kol"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SEC, trust_env=False) as client:
        resp = await client.post(url, json=signed_body)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"KOL create failed: HTTP {resp.status_code} body={resp.text[:500]}"
        )
    payload = resp.json()
    if payload.get("code") not in (0, "0", None):
        raise RuntimeError(f"KOL create biz error: {payload}")
    data = payload.get("data") or {}
    if not data.get("user_id"):
        raise RuntimeError(f"KOL create response missing user_id: {payload}")
    return data


async def encode_short_link(long_link: str) -> dict[str, str]:
    """调用 alvinclub 长链转短链接口，返回 {long, short, short_code}。

    最终展示短链拼 ``{SHORT_LINK_DISPLAY_HOST}/{short_code}``，不直接用接口返回的
    shortLink（后者是 alvinclub.ca 域，我们要用 alvc.me）。
    """
    encoded = quote(long_link, safe="")
    url = f"{settings.short_link_encode_api}?link={encoded}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SEC, trust_env=False) as client:
        resp = await client.get(url)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Short link encode failed: HTTP {resp.status_code} body={resp.text[:500]}"
        )
    payload = resp.json()
    if payload.get("code") not in (0, "0", None) and not payload.get("success", False):
        raise RuntimeError(f"Short link encode biz error: {payload}")
    data = payload.get("data") or {}
    short_code = data.get("shortCode") or ""
    if not short_code:
        raise RuntimeError(f"Short link encode missing shortCode: {payload}")
    return {
        "long": long_link,
        "short": f"{settings.short_link_display_host.rstrip('/')}/{short_code}",
        "short_code": short_code,
    }


async def provision_kol_for_account(account_id: UUID) -> None:
    """调用站内平台创建 KOL，将 kol_user_id 写回 accounts。

    自带 session，自带 try/except，不抛出任何异常给调用方。
    幂等：若 kol_user_id 已存在则跳过整次调用。
    长链/短链不在此触发 —— 需要时由其它流程读取 ``kol_user_id`` 后现算。
    """
    async with SessionLocal() as session:
        account = await session.scalar(select(Account).where(Account.id == account_id))
        if account is None:
            logger.warning("KOL provision skipped: account %s not found", account_id)
            return
        if account.kol_user_id:
            logger.info("KOL provision skipped: account %s already has kol_user_id=%s", account_id, account.kol_user_id)
            return

        try:
            data = await create_kol_via_open_api(account)
            account.kol_user_id = str(data["user_id"])
            account.kol_provision_status = "success"
            account.kol_provision_error = None
            await session.commit()
            logger.info(
                "KOL provisioned for account=%s kol_user_id=%s",
                account_id, account.kol_user_id,
            )
        except Exception as exc:
            logger.exception("KOL provision failed for account=%s", account_id)
            account.kol_provision_status = "failed"
            account.kol_provision_error = (str(exc) or repr(exc))[:1000]
            try:
                await session.commit()
            except Exception:
                logger.exception("Failed to persist KOL provision_error for account=%s", account_id)
