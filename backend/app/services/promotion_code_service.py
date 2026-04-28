from __future__ import annotations

import asyncio
import logging
import secrets
from collections import deque

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask

logger = logging.getLogger("app.promotion_code_service")

_CODE_SPACE = 100_000_000
_REFILL_THRESHOLD_RATIO = 0.3


class PromotionCodeDistributor:
    """Single-instance in-memory distributor for 8-digit promotion codes."""

    def __init__(self) -> None:
        self._pool: deque[str] = deque()
        self._pool_set: set[str] = set()
        self._leased_set: set[str] = set()
        self._used_set: set[str] = set()
        self._burned_set: set[str] = set()
        self._lock: asyncio.Lock | None = None
        self._refill_task: asyncio.Task | None = None
        self._started = False

    @property
    def target_size(self) -> int:
        return max(1, min(int(settings.promotion_code_pool_size), _CODE_SPACE))

    @property
    def refill_threshold(self) -> int:
        return max(1, int(self.target_size * _REFILL_THRESHOLD_RATIO))

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def start(self) -> None:
        self._started = True
        await self._refill()

    async def stop(self) -> None:
        self._started = False
        task = self._refill_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._refill_task = None

    async def acquire(self) -> str:
        """Return one promotion code and mark it leased until DB commit."""
        for _ in range(2):
            task_to_wait: asyncio.Task | None = None
            async with self._get_lock():
                if self._pool:
                    code = self._pool.popleft()
                    self._pool_set.remove(code)
                    self._leased_set.add(code)
                    self._schedule_refill_if_needed_locked()
                    return code

                task_to_wait = self._ensure_refill_locked()

            if task_to_wait is not None:
                await asyncio.shield(task_to_wait)

        raise RuntimeError("promotion code pool is empty")

    async def mark_committed(self, code: str | None) -> None:
        if not code:
            return
        async with self._get_lock():
            self._leased_set.discard(code)
            self._used_set.add(code)
            self._burned_set.discard(code)

    async def discard(self, code: str | None) -> None:
        """Do not return the code to this process' pool after an uncertain failure."""
        if not code:
            return
        async with self._get_lock():
            self._leased_set.discard(code)
            self._pool_set.discard(code)
            self._burned_set.add(code)

    def _schedule_refill_if_needed_locked(self) -> None:
        if not self._started:
            return
        if len(self._pool) > self.refill_threshold:
            return
        self._ensure_refill_locked()

    def _ensure_refill_locked(self) -> asyncio.Task:
        if self._refill_task is None or self._refill_task.done():
            self._refill_task = asyncio.create_task(self._refill())
        return self._refill_task

    async def _load_existing_codes(self) -> set[str]:
        async with SessionLocal() as session:
            rows = await session.execute(
                select(VideoPublication.promotion_code).where(VideoPublication.promotion_code.is_not(None))
            )
            publication_codes = {
                str(code)
                for code in rows.scalars().all()
                if isinstance(code, str) and len(code) == 8 and code.isdigit()
            }
            meta_rows = await session.execute(
                select(VideoSubTask.publish_meta).where(VideoSubTask.publish_meta.is_not(None))
            )
            publish_meta_codes = set()
            for meta in meta_rows.scalars().all():
                if not isinstance(meta, dict):
                    continue
                code = meta.get("promotion_code")
                if isinstance(code, str) and len(code) == 8 and code.isdigit():
                    publish_meta_codes.add(code)
            return publication_codes | publish_meta_codes

    def _memory_reserved_codes_locked(self) -> set[str]:
        """Codes already known by this process; caller must hold _lock."""
        reserved = set(self._pool_set)
        reserved.update(self._leased_set)
        reserved.update(self._used_set)
        reserved.update(self._burned_set)
        return reserved

    async def _refill(self) -> None:
        existing_codes = await self._load_existing_codes()

        async with self._get_lock():
            needed = self.target_size - len(self._pool)
            if needed <= 0:
                return

            memory_reserved_codes = self._memory_reserved_codes_locked()
            unavailable = set(existing_codes)
            unavailable.update(memory_reserved_codes)

            if len(unavailable) >= _CODE_SPACE:
                raise RuntimeError("all promotion codes have been exhausted")

            added = 0
            attempts = 0
            max_attempts = max(needed * 20, 1000)
            while added < needed:
                attempts += 1
                if attempts > max_attempts:
                    raise RuntimeError(
                        f"unable to generate {needed} unique promotion codes after {attempts} attempts"
                    )

                code = f"{secrets.randbelow(_CODE_SPACE):08d}"
                if code in unavailable:
                    continue

                unavailable.add(code)
                self._pool.append(code)
                self._pool_set.add(code)
                added += 1

            logger.info(
                "Promotion code pool refilled: added=%d pool_size=%d leased=%d db_existing=%d memory_reserved=%d",
                added,
                len(self._pool),
                len(self._leased_set),
                len(existing_codes),
                len(memory_reserved_codes),
            )


promotion_code_distributor = PromotionCodeDistributor()


async def start_promotion_code_distributor() -> None:
    await promotion_code_distributor.start()


async def stop_promotion_code_distributor() -> None:
    await promotion_code_distributor.stop()
