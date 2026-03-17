from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tiktok_blogger import TiktokBlogger
from app.models.video_source import VideoSource
from app.schemas.tiktok_blogger import TiktokBloggerPatch

logger = logging.getLogger("app.tiktok_blogger")


async def _download_and_upload_avatar(avatar_url: str) -> str | None:
    """Download avatar from original URL and upload to CDN. Returns CDN URL or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(avatar_url)
            if resp.status_code >= 400:
                logger.warning("Failed to download avatar %s: HTTP %s", avatar_url, resp.status_code)
                return None
            content = resp.content
            content_type = resp.headers.get("content-type", "image/jpeg")
            # Determine extension from content-type
            ext = "jpg"
            if "png" in content_type:
                ext = "png"
            elif "webp" in content_type:
                ext = "webp"
            elif "gif" in content_type:
                ext = "gif"

        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(tmp_path, "rb") as f:
                    upload_resp = await client.post(
                        settings.upload_api_url,
                        files={"file": (f"avatar.{ext}", f, content_type)},
                        headers={"Accept": "*/*"},
                    )
            if upload_resp.status_code >= 400:
                logger.warning("Avatar upload API returned %s: %s", upload_resp.status_code, upload_resp.text[:200])
                return None
            payload = upload_resp.json()
            cdn_url = payload.get("data", {}).get("url") if isinstance(payload.get("data"), dict) else None
            if not cdn_url:
                logger.warning("Avatar upload response missing data.url: %s", payload)
                return None
            return cdn_url
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Avatar download/upload failed for %s: %s", avatar_url, exc)
        return None


def _normalize_platform(raw: str) -> str:
    p = raw.lower()
    if "youtube" in p:
        return "youtube"
    if "tiktok" in p:
        return "tiktok"
    if "instagram" in p:
        return "instagram"
    return p or "unknown"


def _extract_blogger_fields(info: dict) -> dict | None:
    """Extract stable blogger fields from a yt-dlp info dict."""
    # extractor_key (single video) or ie_key (playlist entry) or webpage_url domain
    raw_platform = (
        info.get("extractor_key", "")
        or info.get("ie_key", "")
        or info.get("platform", "")
        or info.get("webpage_url", "")
    )
    platform = _normalize_platform(raw_platform)

    blogger_id = info.get("uploader_id")
    if not blogger_id:
        # Fallback to channel_id for platforms that use it
        blogger_id = info.get("channel_id")
    if not blogger_id:
        return None

    blogger_name = info.get("channel") or info.get("uploader") or str(blogger_id)
    blogger_handle = info.get("uploader")  # @handle
    blogger_url = info.get("uploader_url") or info.get("channel_url")

    # Try to extract avatar URL (injected by video_source_service as _avatar_url from thumbnails list,
    # or from platform-specific fields; do NOT use thumbnail which is the video cover)
    raw_avatar = (
        info.get("_avatar_url")          # highest-preference thumbnail from yt-dlp list (may be avatar)
        or info.get("uploader_thumbnail")
        or info.get("channel_thumbnail")
        or info.get("creator_thumbnail")
        # intentionally NOT falling back to info.get("thumbnail") — that's the video cover
    )

    return {
        "platform": platform,
        "blogger_id": str(blogger_id),
        "blogger_name": blogger_name,
        "blogger_handle": blogger_handle,
        "blogger_url": blogger_url,
        "avatar_url": None,
        "_raw_avatar": raw_avatar,  # temporary field, not saved to DB
    }


async def upsert_blogger_from_info(
    session: AsyncSession,
    info_dict: dict,
    owner_id: UUID | None,
) -> TiktokBlogger | None:
    """Upsert a TiktokBlogger from a yt-dlp info dict. Returns the blogger or None if insufficient data."""
    fields = _extract_blogger_fields(info_dict)
    if not fields:
        return None

    raw_avatar = fields.pop("_raw_avatar", None)
    # Remove internal key before passing to model
    db_fields = {k: v for k, v in fields.items()}

    # NULL-safe SELECT: PostgreSQL treats NULL != NULL in unique constraints
    if owner_id is None:
        stmt = select(TiktokBlogger).where(
            TiktokBlogger.owner_id.is_(None),
            TiktokBlogger.platform == fields["platform"],
            TiktokBlogger.blogger_id == fields["blogger_id"],
        )
    else:
        stmt = select(TiktokBlogger).where(
            TiktokBlogger.owner_id == owner_id,
            TiktokBlogger.platform == fields["platform"],
            TiktokBlogger.blogger_id == fields["blogger_id"],
        )

    async def _resolve_avatar_url() -> str | None:
        """Try profile-page avatar first (more accurate), fallback to raw_avatar (video cover)."""
        profile_url = db_fields.get("blogger_url")
        handle = db_fields.get("blogger_handle")
        if profile_url or handle:
            cdn = await _fetch_and_upload_avatar_from_profile(handle, profile_url)
            if cdn:
                return cdn
        # Fallback: use whatever yt-dlp gave us (may be video thumbnail)
        if raw_avatar:
            return await _download_and_upload_avatar(raw_avatar)
        return None

    blogger = await session.scalar(stmt)
    if blogger:
        # Only update mutable fields when they have changed
        for key in ("blogger_name", "blogger_handle", "blogger_url"):
            new_val = db_fields.get(key)
            if new_val and getattr(blogger, key) != new_val:
                setattr(blogger, key, new_val)
        # Update avatar if no CDN avatar yet
        if not blogger.avatar_url:
            cdn_url = await _resolve_avatar_url()
            if cdn_url:
                blogger.avatar_url = cdn_url
    else:
        cdn_avatar_url = await _resolve_avatar_url()
        db_fields["avatar_url"] = cdn_avatar_url

        blogger = TiktokBlogger(
            id=uuid.uuid4(),
            owner_id=owner_id,
            **db_fields,
        )
        session.add(blogger)

    return blogger


def _extract_tiktok_user_info_from_webpage(ydl: object, profile_url: str) -> tuple[dict | None, str | None]:
    """Fetch TikTok user page once and extract both blogger info dict and raw avatar URL.
    Returns (info_dict_for_upsert, raw_avatar_url). Must be called inside a yt-dlp thread."""
    import json as _json
    import re as _re

    try:
        ie = ydl.get_info_extractor("TikTokUser")
        if ie is None:
            return None, None

        handle_match = _re.search(r"tiktok\.com/@([\w.\-]+)", profile_url)
        if not handle_match:
            return None, None
        user_name = handle_match.group(1)
        user_url = f"https://www.tiktok.com/@{user_name}"

        webpage = ie._download_webpage(
            user_url, user_name,
            note="Fetching TikTok user page",
            errnote="Failed to fetch user page",
            fatal=False, impersonate=True,
        ) or ""

        user: dict = {}

        # __UNIVERSAL_DATA_FOR_REHYDRATION__ (current TikTok)
        m = _re.search(r'id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(\{.*?\})</script>', webpage, _re.DOTALL)
        if m:
            data = _json.loads(m.group(1))
            user = (
                data
                .get("__DEFAULT_SCOPE__", data)
                .get("webapp.user-detail", {})
                .get("userInfo", {})
                .get("user", {})
            )

        # Fallback: SIGI_STATE
        if not user:
            m = _re.search(r'id="SIGI_STATE"[^>]*>(\{.*?\})</script>', webpage, _re.DOTALL)
            if m:
                data = _json.loads(m.group(1))
                users = data.get("UserModule", {}).get("users", {})
                if users:
                    user = next(iter(users.values()), {})

        if not user:
            return None, None

        avatar = user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb")

        # Build a minimal info dict compatible with _extract_blogger_fields
        info_dict = {
            "extractor_key": "TikTok",
            "uploader_id": user.get("id") or user.get("uid"),
            "channel_id": user.get("secUid"),
            "uploader": user.get("uniqueId") or user_name,
            "channel": user.get("nickname"),
            "uploader_url": f"https://www.tiktok.com/@{user.get('uniqueId') or user_name}",
            "channel_url": f"https://www.tiktok.com/@{user.get('uniqueId') or user_name}",
        }
        return info_dict, avatar

    except Exception as exc:
        logger.debug("_extract_tiktok_user_info_from_webpage failed: %s", exc)
    return None, None


async def _fetch_and_upload_avatar_from_profile(handle: str | None, blogger_url: str | None) -> str | None:
    """Fetch avatar from blogger's profile page HTML (og:image) and upload to CDN. Returns CDN URL or None."""
    if not handle and not blogger_url:
        return None

    import re

    user_url = blogger_url or f"https://www.tiktok.com/@{handle}"
    raw_avatar: str | None = None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                user_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            if resp.status_code >= 400:
                return None
            html = resp.text
            # og:image on TikTok profile pages is the blogger avatar
            m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](https?://[^"\']+)["\']', html)
            if not m:
                m = re.search(r'<meta\s+(?:name|property)=["\']twitter:image["\']\s+content=["\'](https?://[^"\']+)["\']', html)
            if m:
                raw_avatar = m.group(1)
    except Exception as exc:
        logger.debug("Failed to fetch profile page for %s: %s", user_url, exc)
        return None

    if not raw_avatar:
        return None
    return await _download_and_upload_avatar(raw_avatar)


async def create_blogger_from_url(
    profile_url: str,
    session: AsyncSession,
    owner_id: UUID | None,
) -> TiktokBlogger:
    """Parse a creator profile URL via tikwm/RapidAPI (TikTok) or yt-dlp (others) and upsert the blogger."""
    if "tiktok.com" in profile_url or "vm.tiktok.com" in profile_url:
        from app.services import tiktok_api_client
        try:
            info = await tiktok_api_client.fetch_blogger_info(profile_url)
        except Exception as exc:
            logger.warning("tiktok_api_client.fetch_blogger_info failed for %s: %s", profile_url, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无法解析博主主页链接: {exc}",
            ) from exc

        raw_avatar_url = info.pop("_avatar_url", None)
        blogger = await upsert_blogger_from_info(session, info, owner_id)

        if blogger is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="无法从该链接提取博主信息（缺少 uploader_id）",
            )

        await session.flush()

        if not blogger.avatar_url and raw_avatar_url:
            cdn_url = await _download_and_upload_avatar(raw_avatar_url)
            if cdn_url:
                blogger.avatar_url = cdn_url
                logger.info("Avatar uploaded for blogger %s: %s", blogger.blogger_id, cdn_url)

        await session.commit()
        await session.refresh(blogger)
        return blogger

    def _run() -> tuple[dict | None, str | None]:
        try:
            import yt_dlp  # type: ignore
        except ImportError:
            raise RuntimeError("yt-dlp is not installed")
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False) or {}
            return info, None

    try:
        info, raw_avatar_url = await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("yt-dlp failed for profile_url=%s: %s", profile_url, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法解析博主主页链接: {exc}",
        ) from exc

    blogger = await upsert_blogger_from_info(session, info, owner_id)

    if blogger is None and info.get("entries"):
        first_entry = info["entries"][0] if info["entries"] else {}
        blogger = await upsert_blogger_from_info(session, first_entry, owner_id)

    if blogger is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="无法从该链接提取博主信息（缺少 uploader_id）",
        )

    await session.flush()

    if not blogger.avatar_url and raw_avatar_url:
        cdn_url = await _download_and_upload_avatar(raw_avatar_url)
        if cdn_url:
            blogger.avatar_url = cdn_url
            logger.info("Avatar uploaded for blogger %s: %s", blogger.blogger_id, cdn_url)

    await session.commit()
    await session.refresh(blogger)
    return blogger


async def list_bloggers(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    owner_id: UUID | None = None,
    platform: str | None = None,
) -> tuple[list[tuple[TiktokBlogger, int]], int]:
    """Return list of (blogger, video_count) tuples and total count."""
    video_count_subq = (
        select(VideoSource.tiktok_blogger_id, func.count(VideoSource.id).label("vc"))
        .where(VideoSource.tiktok_blogger_id.is_not(None))
        .group_by(VideoSource.tiktok_blogger_id)
        .subquery()
    )

    stmt = (
        select(TiktokBlogger, func.coalesce(video_count_subq.c.vc, 0).label("video_count"))
        .outerjoin(video_count_subq, TiktokBlogger.id == video_count_subq.c.tiktok_blogger_id)
        .order_by(TiktokBlogger.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    total_stmt = select(func.count(TiktokBlogger.id))

    if owner_id is not None:
        stmt = stmt.where(TiktokBlogger.owner_id == owner_id)
        total_stmt = total_stmt.where(TiktokBlogger.owner_id == owner_id)
    if platform:
        stmt = stmt.where(TiktokBlogger.platform == platform)
        total_stmt = total_stmt.where(TiktokBlogger.platform == platform)

    rows = (await session.execute(stmt)).all()
    total = await session.scalar(total_stmt) or 0
    return [(row[0], row[1]) for row in rows], total


async def get_blogger_or_404(session: AsyncSession, blogger_id: UUID) -> TiktokBlogger:
    blogger = await session.get(TiktokBlogger, blogger_id)
    if not blogger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="博主不存在")
    return blogger


async def patch_blogger(
    session: AsyncSession,
    blogger: TiktokBlogger,
    payload: TiktokBloggerPatch,
) -> TiktokBlogger:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(blogger, field, value)
    await session.commit()
    await session.refresh(blogger)
    return blogger


async def delete_blogger(session: AsyncSession, blogger: TiktokBlogger) -> None:
    await session.delete(blogger)
    await session.commit()


async def list_blogger_videos(
    session: AsyncSession,
    blogger_id: UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[VideoSource], int]:
    stmt = (
        select(VideoSource)
        .where(VideoSource.tiktok_blogger_id == blogger_id)
        .order_by(VideoSource.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    total_stmt = select(func.count(VideoSource.id)).where(VideoSource.tiktok_blogger_id == blogger_id)

    items = list((await session.scalars(stmt)).all())
    total = await session.scalar(total_stmt) or 0
    return items, total
