import asyncio
import logging
import os
import tempfile
import uuid
import json
from datetime import date
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from google.cloud import storage

import httpx

from app.core.config import settings
from app.models.daily_generation import DailyGeneration

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "generating", "reviewing", "pending_publish", "published"}

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending":         {"generating"},
    "generating":      {"reviewing"},
    "reviewing":       {"pending_publish"},
    "pending_publish": {"published"},
    "published":       set(),
}


def _apply_owner_filter(q, owner_id: uuid.UUID | None):
    if owner_id is not None:
        q = q.where(DailyGeneration.owner_id == owner_id)
    return q


class VideoGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        try:
            self.storage_client = storage.Client(project="ai-agent-461123")
            self.bucket_name = "decom-objects"
            self.bucket = self.storage_client.bucket(self.bucket_name)
        except Exception as e:
            logger.warning(f"Could not initialize GCS client: {e}")
            self.bucket = None

    async def start_generation(
        self,
        account_id: uuid.UUID,
        template_id: uuid.UUID,
        final_prompt: str,
        image: str,
        duration: str,
        shots: list | None,
        user_id: uuid.UUID,
    ) -> uuid.UUID:
        today = date.today()

        max_order = await self.db.scalar(
            select(func.max(DailyGeneration.sort_order)).where(DailyGeneration.target_date == today)
        )
        next_order = (max_order or 0) + 1

        record = DailyGeneration(
            owner_id=user_id,
            account_id=account_id,
            template_id=template_id,
            target_date=today,
            sort_order=next_order,
            status="pending",
            prompt=final_prompt,
            image=image,
            duration=duration,
            shots=shots,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        logger.info(f"Saved DailyGeneration job for {today}. ID: {record.id}, Order: {next_order}")
        return record.id

    async def get_daily_jobs(self, target_date: date, owner_id: uuid.UUID | None) -> list[DailyGeneration]:
        q = select(DailyGeneration).where(DailyGeneration.target_date == target_date)
        q = _apply_owner_filter(q, owner_id)
        q = q.order_by(DailyGeneration.sort_order.asc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_account_jobs(
        self,
        account_id: uuid.UUID,
        owner_id: uuid.UUID | None,
        status_filter: str | None = None,
    ) -> list[DailyGeneration]:
        q = select(DailyGeneration).where(DailyGeneration.account_id == account_id)
        q = _apply_owner_filter(q, owner_id)
        if status_filter:
            q = q.where(DailyGeneration.status == status_filter)
        q = q.order_by(DailyGeneration.target_date.desc(), DailyGeneration.sort_order.asc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def upload_daily_jobs(self, target_date: date, owner_id: uuid.UUID | None) -> str:
        jobs = await self.get_daily_jobs(target_date, owner_id)
        if not jobs:
            raise ValueError(f"No generation jobs found for {target_date}")

        def _first_shot_image(shots: list | None) -> str:
            if not shots:
                return ""
            first = shots[0]
            if isinstance(first, dict):
                return first.get("image_url") or first.get("url") or ""
            return str(first) if first else ""

        payload = [
            {
                "prompt": (job.prompt.replace("\n", " ").replace("\r", "").strip() if job.prompt else "")[:1990],
                "image": _first_shot_image(job.shots),
                "duration": job.duration,
            }
            for job in jobs
        ]

        json_data = json.dumps(payload, ensure_ascii=False, indent=2)
        object_key = f"jimeng/jobs/{target_date.strftime('%Y-%m-%d')}.json"

        if self.bucket:
            blob = self.bucket.blob(object_key)
            blob.upload_from_string(json_data, content_type="application/json")
            logger.info(f"Successfully uploaded daily jobs to gs://{self.bucket_name}/{object_key}")
        else:
            logger.error("GCS bucket not initialized. Cannot upload.")
            raise RuntimeError("GCS bucket not initialized")

        for job in jobs:
            if job.status == "pending":
                job.status = "generating"
        await self.db.commit()

        return f"gs://{self.bucket_name}/{object_key}"

    async def patch_status(
        self,
        job_id: uuid.UUID,
        owner_id: uuid.UUID | None,
        new_status: str,
        result_videos: list[dict[str, Any]] | None = None,
        selected_video_url: str | None = None,
    ) -> DailyGeneration:
        if new_status not in VALID_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效状态: {new_status}")

        q = select(DailyGeneration).where(DailyGeneration.id == job_id)
        q = _apply_owner_filter(q, owner_id)
        job = (await self.db.execute(q)).scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        allowed = STATUS_TRANSITIONS.get(job.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"不允许从 {job.status} 切换到 {new_status}",
            )

        # reviewing → pending_publish: must provide the chosen video
        if new_status == "pending_publish":
            if not selected_video_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="进入待发布阶段时必须提供 selected_video_url",
                )
            job.selected_video_url = selected_video_url

        # generating → reviewing: attach the 3 result candidates
        if new_status == "reviewing" and result_videos is not None:
            job.result_videos = result_videos

        job.status = new_status
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def _upload_gcs_video_to_cdn(self, blob, filename: str) -> str:
        """Download a GCS blob to a temp file and upload to CDN. Returns CDN URL."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Download from GCS in a thread (sync SDK)
            await asyncio.to_thread(blob.download_to_filename, tmp_path)

            # Upload to CDN
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(tmp_path, "rb") as f:
                    response = await client.post(
                        settings.video_upload_api_url,
                        files={"file": (filename, f, "video/mp4")},
                        headers={"Accept": "*/*"},
                    )
            if response.status_code >= 400:
                raise RuntimeError(f"Upload API returned {response.status_code}: {response.text[:300]}")
            payload = response.json()
            cdn_url = payload.get("data", {}).get("url") if isinstance(payload.get("data"), dict) else None
            if not cdn_url:
                raise RuntimeError(f"Upload API response missing data.url: {payload}")
            return cdn_url
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def fetch_daily_results(self, target_date: date, owner_id: uuid.UUID | None) -> dict:
        """
        Read result videos from GCS for the given date, upload to CDN, and update jobs.
        GCS path pattern: jimeng/results/{YYYY-MM-DD}/{NNN}/video.mp4
        Jobs are matched by sort_order (1-based → 001, 002, …).
        Only jobs in 'generating' status are updated.
        Returns a summary dict with updated/skipped counts.
        """
        jobs = await self.get_daily_jobs(target_date, owner_id)
        if not jobs:
            raise ValueError(f"No generation jobs found for {target_date}")

        date_str = target_date.strftime("%Y-%m-%d")
        updated = 0
        skipped = 0
        errors = []

        for job in jobs:
            if job.status != "generating":
                skipped += 1
                continue

            folder = str(job.sort_order).zfill(3)
            object_key = f"jimeng/results/{date_str}/{folder}/video.mp4"

            if not self.bucket:
                raise RuntimeError("GCS bucket not initialized")

            blob = self.bucket.blob(object_key)
            if not await asyncio.to_thread(blob.exists):
                errors.append(f"{folder}/video.mp4 not found in GCS")
                skipped += 1
                continue

            try:
                filename = f"{date_str}_{folder}.mp4"
                cdn_url = await self._upload_gcs_video_to_cdn(blob, filename)
                job.result_videos = [{"video_url": cdn_url, "thumbnail_url": ""}]
                job.status = "reviewing"
                updated += 1
            except Exception as exc:
                logger.warning("Failed to upload GCS video %s to CDN: %s", object_key, exc)
                errors.append(f"{folder}: upload failed - {exc}")
                skipped += 1

        await self.db.commit()
        return {"updated": updated, "skipped": skipped, "errors": errors}

    async def delete_daily_job(self, job_id: uuid.UUID, owner_id: uuid.UUID | None) -> bool:
        q = select(DailyGeneration).where(DailyGeneration.id == job_id)
        q = _apply_owner_filter(q, owner_id)
        job = (await self.db.execute(q)).scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生成任务不存在或无权限删除")

        if job.target_date != date.today():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能删除今日生成的任务")

        await self.db.delete(job)
        await self.db.commit()
        return True
