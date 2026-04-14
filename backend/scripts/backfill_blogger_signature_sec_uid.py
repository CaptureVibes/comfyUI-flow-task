"""
Backfill signature and sec_uid for existing tiktok_bloggers.

Usage:
    cd backend
    uv run python scripts/backfill_blogger_signature_sec_uid.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx
from sqlalchemy import select

sys.path.insert(0, ".")
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.tiktok_blogger import TiktokBlogger

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("backfill_blogger")

_RAPIDAPI_BASE = "https://tiktok-api23.p.rapidapi.com"
_REQUEST_DELAY = 1.2   # seconds between successful requests
_RETRY_DELAY   = 3.0   # seconds to wait before retry on failure
_MAX_RETRIES   = 3


async def _fetch_user_info(client: httpx.AsyncClient, unique_id: str) -> dict | None:
    """Call RapidAPI /api/user/info with up to _MAX_RETRIES retries on 202/204/error."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = await client.get(
                f"{_RAPIDAPI_BASE}/api/user/info",
                params={"uniqueId": unique_id},
                headers={
                    "x-rapidapi-key": settings.rapidapi_key,
                    "x-rapidapi-host": "tiktok-api23.p.rapidapi.com",
                    "Content-Type": "application/json",
                },
            )
            # 202 / 204 = not ready, treat as retriable
            if resp.status_code in (202, 204):
                logger.warning("  attempt %d/%d: HTTP %d (not ready), retrying in %.0fs...",
                               attempt, _MAX_RETRIES, resp.status_code, _RETRY_DELAY)
                await asyncio.sleep(_RETRY_DELAY)
                continue

            resp.raise_for_status()
            body = resp.json()
            user_info = body.get("userInfo") or {}
            user = user_info.get("user") or None
            if not user:
                logger.warning("  attempt %d/%d: empty user in response, retrying in %.0fs...",
                               attempt, _MAX_RETRIES, _RETRY_DELAY)
                await asyncio.sleep(_RETRY_DELAY)
                continue
            return user

        except Exception as exc:
            logger.warning("  attempt %d/%d: error %s, retrying in %.0fs...",
                           attempt, _MAX_RETRIES, exc, _RETRY_DELAY)
            await asyncio.sleep(_RETRY_DELAY)

    logger.error("  all %d attempts failed for %s", _MAX_RETRIES, unique_id)
    return None


async def main(dry_run: bool, limit: int | None) -> None:
    if not settings.rapidapi_key:
        logger.error("RAPIDAPI_KEY not configured in .env, aborting.")
        sys.exit(1)

    async with SessionLocal() as session:
        stmt = select(TiktokBlogger).where(TiktokBlogger.platform == "tiktok")
        result = await session.execute(stmt)
        bloggers: list[TiktokBlogger] = list(result.scalars().all())

    if limit:
        bloggers = bloggers[:limit]

    logger.info("Found %d tiktok bloggers to process.", len(bloggers))

    updated = skipped = failed = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        for i, blogger in enumerate(bloggers):
            unique_id = blogger.blogger_handle or blogger.blogger_id
            logger.info("[%d/%d] blogger_id=%s unique_id=%s", i + 1, len(bloggers), blogger.blogger_id, unique_id)

            user = await _fetch_user_info(client, unique_id)
            if not user:
                failed += 1
                continue

            new_signature = user.get("signature") or None
            new_sec_uid = user.get("secUid") or None

            if not new_signature and not new_sec_uid:
                logger.info("  -> nothing to update")
                skipped += 1
                await asyncio.sleep(_REQUEST_DELAY)
                continue

            sig_preview = (new_signature or "")[:60] + ("..." if new_signature and len(new_signature) > 60 else "")
            logger.info("  -> signature=%r  sec_uid=%s...", sig_preview, (new_sec_uid or "")[:20])

            if not dry_run:
                async with SessionLocal() as session:
                    b = await session.get(TiktokBlogger, blogger.id)
                    if b:
                        if new_signature:
                            b.signature = new_signature
                        if new_sec_uid:
                            b.sec_uid = new_sec_uid
                        await session.commit()

            updated += 1
            await asyncio.sleep(_REQUEST_DELAY)

    logger.info("Done. updated=%d  skipped=%d  failed=%d  dry_run=%s", updated, skipped, failed, dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing to DB")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N bloggers")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
