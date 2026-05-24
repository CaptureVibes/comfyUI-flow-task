"""GCS 视频链接的 V4 签名 + 自动续签。

video_sub_tasks.result_video_url 字段直接存"对外可用"的链接：
- 旧 CDN 后端：公开 CDN URL，无需处理
- GCS 后端：V4 签名 URL（7 天），快过期前自动续签并覆写同一列

读取路径：调用方拿到 video_sub_task → 用 ``ensure_sub_task_signed_url`` 检查/续签。
该函数会：

1. 若 ``result_video_url`` 不是 GCS（旧 CDN）→ 直接返回；
2. 若已是 V4 签名 URL 且 ``X-Goog-Expires`` 剩余 > REFRESH_THRESHOLD → 直接返回；
3. 否则（未签 / 即将过期）→ 现签一个 7 天有效的 V4 URL，覆写
   ``sub_task.result_video_url`` 并 commit，返回新链接。

失效时间从 URL 自身的 ``X-Goog-Date`` + ``X-Goog-Expires`` 解析，不另存字段。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app.gcs_signing")

# V4 签名 URL 最大 7 天有效（GCS 硬性限制）
SIGNED_URL_TTL = timedelta(days=7)
# 剩余 < 1 天时认为"即将过期"，触发续签
SIGNED_URL_REFRESH_THRESHOLD = timedelta(days=1)


def _parse_signed_url_expiration(url: str) -> datetime | None:
    """从 V4 签名 URL 的 query 里解析 (X-Goog-Date + X-Goog-Expires) → UTC datetime。

    URL 不是签名链或解析失败 → None。
    """
    try:
        params = parse_qs(urlparse(url).query)
        date_str = (params.get("X-Goog-Date") or [None])[0]
        expires_str = (params.get("X-Goog-Expires") or [None])[0]
        if not date_str or not expires_str:
            return None
        # X-Goog-Date 形如 20260524T120000Z
        signed_at = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return signed_at + timedelta(seconds=int(expires_str))
    except Exception as exc:
        logger.warning("无法解析 V4 签名 URL 失效时间: %s (url=%s...)", exc, url[:120])
        return None


def _is_signed_url_fresh(url: str | None) -> bool:
    """已是 V4 签名 URL，且剩余有效期 > REFRESH_THRESHOLD。"""
    if not url:
        return False
    expires_at = _parse_signed_url_expiration(url)
    if expires_at is None:
        return False
    return expires_at > datetime.now(timezone.utc) + SIGNED_URL_REFRESH_THRESHOLD


def _sign_gcs_url(raw_url: str) -> str:
    """对一条 GCS URL（无论原本签没签）签一个 7 天 V4 URL。

    bucket/key 从 URL path 解析，与是否带签名 query 参数无关；
    要求服务账号凭证可用（GOOGLE_APPLICATION_CREDENTIALS / 默认服务账号）。
    """
    from app.utils.gcs_download import parse_gcs_url
    from app.utils.gcs_utils import generate_gcs_signed_url

    bucket, key = parse_gcs_url(raw_url)
    return generate_gcs_signed_url(
        bucket_name=bucket,
        object_key=key,
        expiration_minutes=int(SIGNED_URL_TTL.total_seconds() // 60),
    )


async def ensure_sub_task_signed_url(
    session: AsyncSession,
    sub_task,
) -> str | None:
    """返回对外可播的 result_video_url。

    - 空 → None
    - 非 GCS（旧 CDN）→ 原样返回
    - GCS 且当前已是签名链且剩余 > 1 天 → 原样返回
    - 否则（未签 / 即将过期）→ 现签覆写 result_video_url 并 commit
    """
    from app.utils.gcs_download import is_gcs_url

    url = sub_task.result_video_url
    if not url:
        return None
    if not is_gcs_url(url):
        return url
    if _is_signed_url_fresh(url):
        return url

    # 续签 / 首次签名
    try:
        new_signed = _sign_gcs_url(url)
    except Exception as exc:
        logger.error("签名 GCS URL 失败 sub_task=%s url=%s: %s", sub_task.id, url[:120], exc)
        # 退化：直接返回原 URL（外部播放会 403，但至少不阻塞接口）
        return url

    sub_task.result_video_url = new_signed
    try:
        await session.commit()
    except Exception as exc:
        logger.warning("回写 result_video_url 签名 URL 失败 sub_task=%s: %s", sub_task.id, exc)
        await session.rollback()
    return new_signed


async def ensure_sub_tasks_signed_urls(
    session: AsyncSession,
    sub_tasks: list,
) -> dict:
    """批量版：返回 {sub_task.id: 外部可播 URL}。一次性 commit。"""
    from app.utils.gcs_download import is_gcs_url

    out: dict = {}
    dirty = False
    for st in sub_tasks:
        url = st.result_video_url
        if not url:
            out[st.id] = None
            continue
        if not is_gcs_url(url):
            out[st.id] = url
            continue
        if _is_signed_url_fresh(url):
            out[st.id] = url
            continue
        try:
            new_signed = _sign_gcs_url(url)
        except Exception as exc:
            logger.error("签名 GCS URL 失败 sub_task=%s url=%s: %s", st.id, url[:120], exc)
            out[st.id] = url
            continue
        st.result_video_url = new_signed
        out[st.id] = new_signed
        dirty = True
    if dirty:
        try:
            await session.commit()
        except Exception as exc:
            logger.warning("批量回写 result_video_url 签名 URL 失败: %s", exc)
            await session.rollback()
    return out


async def serialize_sub_task(session: AsyncSession, sub_task) -> "VideoSubTaskRead":
    """构造 VideoSubTaskRead，确保 result_video_url 是对外可播的（GCS → 签名链）。"""
    from app.schemas.video_task import VideoSubTaskRead

    external_url = await ensure_sub_task_signed_url(session, sub_task)
    read = VideoSubTaskRead.model_validate(sub_task)
    read.result_video_url = external_url
    return read


async def serialize_sub_tasks(session: AsyncSession, sub_tasks: list) -> list:
    """批量版：返回 [VideoSubTaskRead]，URL 已替换为外部可播链。"""
    from app.schemas.video_task import VideoSubTaskRead

    url_map = await ensure_sub_tasks_signed_urls(session, sub_tasks)
    out = []
    for st in sub_tasks:
        read = VideoSubTaskRead.model_validate(st)
        read.result_video_url = url_map.get(st.id, read.result_video_url)
        out.append(read)
    return out
