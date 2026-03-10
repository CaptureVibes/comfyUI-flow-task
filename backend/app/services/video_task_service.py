import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status
from google.cloud import storage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.video_ai_template import VideoAITemplate
from app.models.account import Account
from app.models.system_setting import SystemSetting
from app.models.video_task import VideoSubTask, VideoTask
from app.models.video_task_config import VideoTaskConfig
from app.services.video_scoring_service import score_video_with_ai

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "generating", "scoring", "pending_publish", "publishing", "published", "abandoned"}

SUB_TASK_TRANSITIONS: dict[str, set[str]] = {
    "pending":         {"generating"},
    "generating":      {"scoring"},
    "scoring":         {"pending_publish", "abandoned"},
    "pending_publish": {"publishing", "published"},
    "publishing":      {"published"},
    "published":       set(),
    "abandoned":       set(),
}

PREV_STATUS: dict[str, str] = {
    "generating":      "pending",
    "scoring":          "generating",
    "pending_publish": "scoring",
    "publishing":      "pending_publish",
    "published":       "publishing",
}


def _compute_parent_status(sub_tasks: list[VideoSubTask]) -> str:
    if any(st.selected and st.status == "published" for st in sub_tasks):
        return "published"
    statuses = {st.status for st in sub_tasks if st.status != "abandoned"}
    if not statuses:
        return "abandoned"
    if "publishing" in statuses:
        return "publishing"
    if "pending_publish" in statuses:
        return "pending_publish"
    if "scoring" in statuses:
        return "scoring"
    if "generating" in statuses:
        return "generating"
    return "pending"


def _extract_image_urls(shots: list | None) -> list[str]:
    if not shots:
        return []
    urls = []
    for shot in shots:
        if isinstance(shot, dict):
            url = shot.get("image_url") or shot.get("url") or ""
            if url:
                urls.append(url)
    return urls


class VideoTaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bucket_name = settings.gcs_bucket_name
        self._storage_client = None
        self._bucket = None

    @property
    def bucket(self):
        if self._bucket is None:
            try:
                self._storage_client = storage.Client(project=settings.gcs_project_id)
                self._bucket = self._storage_client.bucket(self.bucket_name)
            except Exception as e:
                logger.warning(f"Could not initialize GCS client: {e}")
        return self._bucket

    async def create_task(
        self,
        account_id: uuid.UUID,
        template_id: uuid.UUID,
        final_prompt: str,
        duration: str,
        shots: list | None,
        user_id: uuid.UUID,
        target_date: date | None = None,
    ) -> VideoTask:
        if target_date is None:
            target_date = date.today() + timedelta(days=1)

        task = VideoTask(
            owner_id=user_id,
            account_id=account_id,
            template_id=template_id,
            target_date=target_date,
            status="pending",
            prompt=final_prompt,
            duration=duration,
            shots=shots,
        )
        self.db.add(task)
        await self.db.flush()  # get task.id before creating sub-tasks

        for i in range(1, 4):
            sub = VideoSubTask(
                task_id=task.id,
                sub_index=i,
                status="pending",
            )
            self.db.add(sub)

        await self.db.commit()
        await self.db.refresh(task)

        # Reload with sub_tasks
        result = await self.db.execute(
            select(VideoTask)
            .where(VideoTask.id == task.id)
            .options(selectinload(VideoTask.sub_tasks))
        )
        return result.scalar_one()

    async def get_tasks(
        self,
        target_date: date | None,
        owner_id: uuid.UUID | None,
        account_id: uuid.UUID | None = None,
        status_filter: str | None = None,
    ) -> list[VideoTask]:
        q = (
            select(VideoTask)
            .options(selectinload(VideoTask.sub_tasks))
            .order_by(VideoTask.created_at.desc())
        )
        if target_date is not None:
            q = q.where(VideoTask.target_date == target_date)
        if owner_id is not None:
            q = q.where(VideoTask.owner_id == owner_id)
        if account_id is not None:
            q = q.where(VideoTask.account_id == account_id)
        if status_filter:
            q = q.where(VideoTask.status == status_filter)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_task_detail(self, task_id: uuid.UUID, owner_id: uuid.UUID | None) -> dict:
        q = (
            select(VideoTask)
            .where(VideoTask.id == task_id)
            .options(selectinload(VideoTask.sub_tasks))
        )
        if owner_id is not None:
            q = q.where(VideoTask.owner_id == owner_id)
        task = (await self.db.execute(q)).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

        account_name: str | None = None
        template_title: str | None = None

        if task.account_id:
            acc = await self.db.get(Account, task.account_id)
            account_name = acc.account_name if acc else None

        if task.template_id:
            tpl = await self.db.get(VideoAITemplate, task.template_id)
            template_title = tpl.title if tpl else None

        return {"task": task, "account_name": account_name, "template_title": template_title}

    async def delete_task(self, task_id: uuid.UUID, owner_id: uuid.UUID | None) -> bool:
        q = select(VideoTask).where(VideoTask.id == task_id)
        if owner_id is not None:
            q = q.where(VideoTask.owner_id == owner_id)
        task = (await self.db.execute(q)).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        if task.target_date != date.today():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能删除今日任务")
        if task.status not in ("pending", "generating"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="只能删除 pending 或 generating 状态的任务")
        await self.db.delete(task)
        await self.db.commit()
        return True

    async def upload_tasks(self, target_date: date, owner_id: uuid.UUID | None) -> tuple[str, int, int]:
        """
        Upload all pending tasks for the date to GCS.
        Each sub-task gets one entry in the payload using its UUID as video_id.
        Returns (gcs_url, task_count, subtask_count).
        """
        tasks = await self.get_tasks(target_date, owner_id, status_filter="pending")
        if not tasks:
            raise ValueError(f"No pending tasks found for {target_date}")

        if not self.bucket:
            raise RuntimeError("GCS bucket not initialized")

        payload = []
        for task in tasks:
            image_urls = _extract_image_urls(task.shots)
            display_image_urls = image_urls[:1]  # 目前只传第一个
            prompt_text = (task.prompt.replace("\n", " ").replace("\r", "").strip() if task.prompt else "")[:1990]
            for sub in task.sub_tasks:
                sub_prompt = f"video_id: {sub.id}\n{prompt_text}"
                payload.append({
                    "prompt": sub_prompt,
                    "image_urls": display_image_urls,
                    "duration": task.duration,
                    "video_id": str(sub.id),
                })
                sub.status = "generating"
            task.status = "generating"

        date_str = target_date.strftime("%Y-%m-%d")
        object_key = f"jimeng/jobs/{date_str}.json"
        json_data = json.dumps(payload, ensure_ascii=False, indent=2)

        blob = self.bucket.blob(object_key)
        blob.upload_from_string(json_data, content_type="application/json")
        logger.info(f"Uploaded {len(payload)} sub-task entries to gs://{self.bucket_name}/{object_key}")

        await self.db.commit()
        gcs_url = f"gs://{self.bucket_name}/{object_key}"
        return gcs_url, len(tasks), len(payload)

    async def _upload_gcs_video_to_cdn(self, blob: Any, filename: str) -> str:
        """Download a GCS blob to a temp file and upload to CDN. Returns CDN URL."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await asyncio.to_thread(blob.download_to_filename, tmp_path)
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

    async def fetch_results(self, target_date: date, owner_id: uuid.UUID | None) -> dict:
        """
        Read result videos from GCS for the given date using each sub-task's UUID as the path key.
        GCS path: jimeng/results/{YYYY-MM-DD}/{sub_task.id}/video.mp4
        Scans all tasks for the date and processes any sub-task with status=generating.
        Uploads are processed concurrently. Then AI scoring is processed concurrently.
        """
        # Fetch all tasks for the date (regardless of parent status) and filter by sub-task status
        tasks = await self.get_tasks(target_date, owner_id)
        valid_tasks = [t for t in tasks if any(s.status == "generating" for s in t.sub_tasks)]
        if not valid_tasks:
            return {"updated": 0, "skipped": 0, "errors": [], "message": f"当天没有 generating 状态的子任务"}

        if not self.bucket:
            raise RuntimeError("GCS bucket not initialized")

        date_str = target_date.strftime("%Y-%m-%d")
        updated = 0
        skipped = 0
        errors = []

        # 1. Gather all generating subtasks
        target_subs = []
        for task in valid_tasks:
            for sub in task.sub_tasks:
                if sub.status == "generating":
                    target_subs.append((task, sub))
                else:
                    skipped += 1

        # 2. Concurrently check GCS and upload to CDN
        async def _process_upload(task, sub):
            object_key = f"jimeng/results/{date_str}/{sub.id}/video.mp4"
            blob = self.bucket.blob(object_key)
            if not await asyncio.to_thread(blob.exists):
                return task, sub, None, f"{sub.id}/video.mp4 not found in GCS"
            try:
                filename = f"{date_str}_{sub.id}.mp4"
                cdn_url = await self._upload_gcs_video_to_cdn(blob, filename)
                return task, sub, cdn_url, None
            except Exception as exc:
                return task, sub, None, f"{sub.id}: upload failed - {exc}"

        logger.info("Starting concurrent uploads for %d subtasks", len(target_subs))
        upload_coros = [_process_upload(t, s) for t, s in target_subs]
        upload_results = await asyncio.gather(*upload_coros)

        # 3. Process upload results and save DB
        #    If video not found or upload failed → abandon the subtask immediately
        successfully_uploaded = []
        for task, sub, cdn_url, error_msg in upload_results:
            if error_msg:
                errors.append(error_msg)
                sub.status = "abandoned"
                logger.info("Sub-task %s abandoned: %s", sub.id, error_msg)
                updated += 1
            else:
                sub.result_video_url = cdn_url
                sub.status = "scoring"
                successfully_uploaded.append((task, sub, cdn_url))
                logger.info("Sub-task %s uploaded, starting AI scoring", sub.id)

        # Recompute parent statuses and commit so frontend can see abandoned / scoring statuses immediately
        for task in valid_tasks:
            task.status = _compute_parent_status(task.sub_tasks)
        await self.db.commit()

        if not successfully_uploaded:
            # All subtasks failed upload, update parent statuses and return
            for task in valid_tasks:
                task.status = _compute_parent_status(task.sub_tasks)
            await self.db.commit()
            return {"updated": updated, "skipped": skipped, "errors": errors}

        # 4. Concurrently run AI scoring for all uploaded videos
        # Fetch configurations sequentially to avoid concurrent DB queries on the same session
        owner_ids = {t.owner_id for t, _, _ in successfully_uploaded}
        configs = {}
        for uid in owner_ids:
            configs[uid] = await self.db.get(VideoTaskConfig, uid)
        sys_cfg = await self.db.get(SystemSetting, "default")

        async def _score_task(task, sub, cdn_url):
            logger.info("Calling _score_video for sub-task %s with CDN URL: %s", sub.id, cdn_url[:100])
            config = configs.get(task.owner_id)
            scoring_result = await self._score_video(sub, cdn_url, config=config, sys_cfg=sys_cfg)
            return task, sub, scoring_result

        # Use as_completed so each result is processed and committed immediately
        score_futures = [
            asyncio.ensure_future(_score_task(t, s, url))
            for t, s, url in successfully_uploaded
        ]

        # 5. Process each scoring result as it completes — commit after each one
        task_scored_subs: dict[uuid.UUID, list] = {}  # task.id → [(sub, score)]

        for coro in asyncio.as_completed(score_futures):
            task, sub, scoring_result = await coro
            logger.info("_score_video returned for sub-task %s: %s", sub.id, "success" if scoring_result else "None")
            if scoring_result:
                final_score, round1_score, round2_score, round1_reason, round2_reason = scoring_result
                sub.ai_score = int(final_score)
                sub.round1_score = int(round1_score) if round1_score else None
                sub.round2_score = int(round2_score) if round2_score else None
                sub.round1_reason = round1_reason
                sub.round2_reason = round2_reason
                logger.info("Sub-task %s AI scored: final=%.1f, r1=%.1f, r2=%.1f",
                            sub.id, final_score, round1_score or 0, round2_score or 0)
                task_scored_subs.setdefault(task.id, []).append((task, sub, final_score))
                updated += 1
            else:
                # AI scoring failed, abandon
                sub.status = "abandoned"
                updated += 1
                logger.warning("Sub-task %s AI scoring failed, abandoned", sub.id)

            # Immediately recompute parent status and commit
            task.status = _compute_parent_status(task.sub_tasks)
            await self.db.commit()

        # 6. For each parent task, auto-select the best subtask
        any_reviewed_template_ids = set()

        for task_id, scored_list in task_scored_subs.items():
            # Pick the subtask with the highest AI score
            scored_list.sort(key=lambda x: x[2], reverse=True)
            best_task, best_sub, best_score = scored_list[0]

            # Check threshold
            config = configs.get(best_task.owner_id)
            threshold = config.final_threshold if config else 65.0

            if best_score >= threshold:
                best_sub.status = "pending_publish"
                best_sub.selected = True
                any_reviewed_template_ids.add(best_task.template_id)
                logger.info("Sub-task %s auto-selected: highest score %.1f >= threshold %.1f",
                            best_sub.id, best_score, threshold)
            else:
                best_sub.status = "abandoned"
                logger.info("Sub-task %s best score %.1f < threshold %.1f, all abandoned",
                            best_sub.id, best_score, threshold)

            # Abandon the rest
            for _, other_sub, _ in scored_list[1:]:
                other_sub.status = "abandoned"
                logger.info("Sub-task %s abandoned (not the best)", other_sub.id)

        # 7. Update parent task statuses after auto-selection
        for task in valid_tasks:
            task.status = _compute_parent_status(task.sub_tasks)

        # Mark templates used sequentially
        for template_id in any_reviewed_template_ids:
            if template_id:
                tpl = await self.db.get(VideoAITemplate, template_id)
                if tpl and not tpl.is_used:
                    tpl.is_used = True

        await self.db.commit()
        return {"updated": updated, "skipped": skipped, "errors": errors}

    async def patch_sub_task_status(
        self,
        sub_task_id: uuid.UUID,
        owner_id: uuid.UUID | None,
        new_status: str,
        result_video_url: str | None = None,
        selected: bool | None = None,
    ) -> VideoSubTask:
        if new_status not in VALID_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效状态: {new_status}")

        # Load sub-task with its parent task (and all siblings)
        q = (
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
        )
        sub = (await self.db.execute(q)).scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")
        if owner_id is not None and sub.task.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")

        allowed = SUB_TASK_TRANSITIONS.get(sub.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"不允许从 {sub.status} 切换到 {new_status}",
            )

        sub.status = new_status
        if result_video_url is not None:
            sub.result_video_url = result_video_url

        # When moving to pending_publish with selected=True, abandon the other sub-tasks
        if new_status == "pending_publish" and selected:
            sub.selected = True
            for sibling in sub.task.sub_tasks:
                if sibling.id != sub.id and sibling.status not in ("published", "abandoned"):
                    sibling.status = "abandoned"

        sub.task.status = _compute_parent_status(sub.task.sub_tasks)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def rollback_sub_task_status(
        self,
        sub_task_id: uuid.UUID,
        owner_id: uuid.UUID | None,
    ) -> VideoSubTask:
        q = (
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
        )
        sub = (await self.db.execute(q)).scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")
        if owner_id is not None and sub.task.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")

        prev = PREV_STATUS.get(sub.status)
        if not prev:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"状态 {sub.status} 无法回退",
            )
        sub.status = prev
        if prev != "pending_publish":
            sub.selected = False

        sub.task.status = _compute_parent_status(sub.task.sub_tasks)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def get_tasks_with_names(
        self,
        target_date: date | None,
        owner_id: uuid.UUID | None,
        account_id: uuid.UUID | None = None,
        status_filter: str | None = None,
    ) -> list[dict]:
        """Returns tasks enriched with account_name, template_title, sub_tasks_done."""
        tasks = await self.get_tasks(target_date, owner_id, account_id, status_filter)

        # Batch-fetch account and template names
        account_ids = {t.account_id for t in tasks if t.account_id}
        template_ids = {t.template_id for t in tasks if t.template_id}

        account_map: dict[uuid.UUID, str] = {}
        template_map: dict[uuid.UUID, str] = {}

        if account_ids:
            rows = await self.db.execute(
                select(Account.id, Account.account_name).where(Account.id.in_(account_ids))
            )
            account_map = {r.id: r.account_name for r in rows}

        if template_ids:
            rows = await self.db.execute(
                select(VideoAITemplate.id, VideoAITemplate.title).where(VideoAITemplate.id.in_(template_ids))
            )
            template_map = {r.id: r.title for r in rows}

        result = []
        for task in tasks:
            item = {
                "task": task,
                "account_name": account_map.get(task.account_id) if task.account_id else None,
                "template_title": template_map.get(task.template_id) if task.template_id else None,
                "sub_tasks_done": sum(1 for st in task.sub_tasks if st.result_video_url),
            }
            result.append(item)
        return result

    async def _score_video(
        self, sub: VideoSubTask, video_url: str, config: VideoTaskConfig | None = None, sys_cfg: SystemSetting | None = None
    ) -> tuple[float, float, float, str, str] | tuple[None, None, str] | None:
        """
        Score a video using AI two-round scoring.

        Args:
            sub: VideoSubTask to score
            video_url: CDN URL of the video
            config: Optional pre-fetched VideoTaskConfig
            sys_cfg: Optional pre-fetched SystemSetting

        Returns:
            Tuple of (final_score, round1_score, round2_score, round1_reason, round2_reason) on success
            Tuple of (None, None, error_message) on scoring failure
            None if config or system settings not found
        """
        from app.services.video_scoring_service import score_video_with_ai

        # Get config and system settings if not provided
        if config is None:
            config = await self.db.get(VideoTaskConfig, sub.task.owner_id)
        if not config:
            logger.warning("No AI scoring config found for owner %s, using defaults", sub.task.owner_id)
            return None

        logger.info("_score_video: Config found - round1_enabled=%s, round1_prompt_len=%d, round2_enabled=%s, round2_prompt_len=%d",
                    config.round1_enabled, len(config.round1_prompt), config.round2_enabled, len(config.round2_prompt))

        if sys_cfg is None:
            sys_cfg = await self.db.get(SystemSetting, "default")
        if not sys_cfg:
            logger.warning("No system settings found, cannot perform AI scoring")
            return None

        logger.info("_score_video: System settings found - has_api_key=%s", bool(sys_cfg.evolink_api_key))

        # Perform AI scoring
        logger.info("_score_video: Calling score_video_with_ai...")
        result = await score_video_with_ai(
            video_url=video_url,
            config=config,
            system_settings=sys_cfg,
        )
        logger.info("_score_video: score_video_with_ai returned %s", result)
        return result
