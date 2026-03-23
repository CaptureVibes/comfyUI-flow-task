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
from app.db.session import SessionLocal
from app.models.video_ai_template import VideoAITemplate
from app.models.account import Account
from app.models.system_setting import SystemSetting
from app.models.video_task import VideoSubTask, VideoTask
from app.models.video_task_config import VideoTaskConfig
from app.services.video_scoring_service import score_video_with_ai

logger = logging.getLogger(__name__)

video_scoring_queue: asyncio.Queue[str] = asyncio.Queue()
video_scoring_worker_tasks: list[asyncio.Task] = []
video_scoring_inflight_ids: set[str] = set()

_SCORING_CONCURRENCY = 30
_SCORING_RETRY_DELAY_SECONDS = 30

VALID_STATUSES = {"pending", "generating", "scoring", "reviewing", "pending_publish", "queued", "publishing", "published", "publish_failed", "abandoned"}

SUB_TASK_TRANSITIONS: dict[str, set[str]] = {
    "pending":         {"generating"},
    "generating":      {"scoring"},
    "scoring":         {"reviewing", "abandoned"},
    "reviewing":       {"pending_publish", "abandoned"},
    "pending_publish": {"queued", "publishing", "published"},
    "queued":          {"publishing", "pending_publish"},
    "publishing":      {"published", "publish_failed"},
    "publish_failed":  {"pending_publish"},
    "published":       set(),
    "abandoned":       set(),
}

PREV_STATUS: dict[str, str] = {
    "generating":      "pending",
    "scoring":         "generating",
    "reviewing":       "scoring",
    "pending_publish": "reviewing",
    "queued":          "pending_publish",
    "publishing":      "queued",
    "publish_failed":  "publishing",
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
    if "publish_failed" in statuses:
        return "publish_failed"
    if "queued" in statuses:
        return "queued"
    if "pending_publish" in statuses:
        return "pending_publish"
    if "reviewing" in statuses:
        return "reviewing"
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


async def enqueue_video_scoring_task(task_id: uuid.UUID | str) -> bool:
    task_id_str = str(task_id)
    if task_id_str in video_scoring_inflight_ids:
        return False
    video_scoring_inflight_ids.add(task_id_str)
    await video_scoring_queue.put(task_id_str)
    return True


def _is_retryable_scoring_error(error_message: str) -> bool:
    text = (error_message or "").lower()
    retry_markers = (
        "网络超时",
        "api 服务不可用",
        "api 调用重试",
        "timed out",
        "timeout",
        "connect",
        "connection",
        "temporarily unavailable",
        "server disconnected",
        "cancelled",
        "502",
        "503",
        "504",
    )
    return any(marker in text for marker in retry_markers)


def _schedule_scoring_retry(task_id: uuid.UUID | str, delay_seconds: int = _SCORING_RETRY_DELAY_SECONDS) -> None:
    task_id_str = str(task_id)

    async def _delayed_requeue() -> None:
        await asyncio.sleep(delay_seconds)
        queued = await enqueue_video_scoring_task(task_id_str)
        if queued:
            logger.info("Requeued scoring task %s after delay=%ss", task_id_str, delay_seconds)
        else:
            logger.info("Skipped delayed requeue for scoring task %s because it is already inflight", task_id_str)

    asyncio.get_running_loop().create_task(_delayed_requeue())


async def _video_scoring_worker_loop(worker_index: int) -> None:
    while True:
        task_id = await video_scoring_queue.get()
        try:
            async with SessionLocal() as session:
                svc = VideoTaskService(db=session)
                await svc.process_scoring_task(task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Video scoring worker %s failed for task=%s", worker_index, task_id)
        finally:
            video_scoring_inflight_ids.discard(str(task_id))
            video_scoring_queue.task_done()


def start_video_scoring_queue_processor() -> None:
    global video_scoring_worker_tasks
    alive_tasks = [task for task in video_scoring_worker_tasks if not task.done()]
    if alive_tasks:
        video_scoring_worker_tasks = alive_tasks
        return
    loop = asyncio.get_running_loop()
    video_scoring_worker_tasks = [
        loop.create_task(_video_scoring_worker_loop(index + 1))
        for index in range(_SCORING_CONCURRENCY)
    ]
    logger.info("Video scoring queue processor started with concurrency=%s", _SCORING_CONCURRENCY)


async def stop_video_scoring_queue_processor() -> None:
    global video_scoring_worker_tasks
    tasks = [task for task in video_scoring_worker_tasks if not task.done()]
    video_scoring_worker_tasks = []
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Video scoring queue processor stopped")


async def recover_stuck_video_scoring_on_startup() -> None:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(VideoTask.id)
                .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
                .where(VideoSubTask.status == "scoring")
                .where(VideoSubTask.result_video_url.is_not(None))
            )
        ).scalars().unique().all()
    recovered = 0
    for task_id in rows:
        if await enqueue_video_scoring_task(task_id):
            recovered += 1
    if recovered:
        logger.info("Recovered %s stuck video scoring tasks on startup", recovered)


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

        normalized_shots = list(shots) if isinstance(shots, list) else []
        account = await self.db.get(Account, account_id)
        account_photo_url = account.photo_url if account and account.photo_url else None
        if account_photo_url:
            photo_shot = {
                "image_url": account_photo_url,
                "description": "",
            }
            if not normalized_shots or normalized_shots[0].get("image_url") != account_photo_url:
                normalized_shots = [photo_shot, *normalized_shots]

        task = VideoTask(
            owner_id=user_id,
            account_id=account_id,
            template_id=template_id,
            target_date=target_date,
            status="pending",
            prompt=final_prompt,
            duration=duration,
            shots=normalized_shots,
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
        tiktok_blogger_id: uuid.UUID | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[VideoTask], int]:
        from sqlalchemy import func

        base_q = select(VideoTask).order_by(VideoTask.created_at.desc())
        if target_date is not None:
            base_q = base_q.where(VideoTask.target_date == target_date)
        if owner_id is not None:
            base_q = base_q.where(VideoTask.owner_id == owner_id)
        if account_id is not None:
            base_q = base_q.where(VideoTask.account_id == account_id)
        if status_filter:
            base_q = base_q.where(VideoTask.status == status_filter)
        if tiktok_blogger_id is not None:
            base_q = base_q.join(VideoAITemplate, VideoTask.template_id == VideoAITemplate.id)
            base_q = base_q.where(VideoAITemplate.tiktok_blogger_id == tiktok_blogger_id)

        # Count total
        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self.db.execute(count_q)).scalar_one()

        # Paginate
        q = base_q.options(selectinload(VideoTask.sub_tasks))
        if page is not None and page_size is not None:
            q = q.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

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

    async def get_task_navigation(self, task_id: uuid.UUID, owner_id: uuid.UUID | None) -> dict:
        from sqlalchemy import func

        task = await self.db.get(VideoTask, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        if owner_id is not None and task.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")

        account = await self.db.get(Account, task.account_id) if task.account_id else None

        # Navigation only shows tasks in 'reviewing' (待决策) status
        NAV_STATUS = "reviewing"

        def _base_task_q():
            q = select(VideoTask).where(VideoTask.status == NAV_STATUS)
            if owner_id is not None:
                q = q.where(VideoTask.owner_id == owner_id)
            return q

        # Position: count reviewing tasks for same account with created_at > current (DESC order)
        pos_q = select(func.count(VideoTask.id)).where(
            VideoTask.account_id == task.account_id,
            VideoTask.status == NAV_STATUS,
            VideoTask.created_at > task.created_at,
        )
        if owner_id is not None:
            pos_q = pos_q.where(VideoTask.owner_id == owner_id)
        position: int = (await self.db.execute(pos_q)).scalar() or 0

        # Total reviewing tasks for this account
        total_q = select(func.count(VideoTask.id)).where(
            VideoTask.account_id == task.account_id,
            VideoTask.status == NAV_STATUS,
        )
        if owner_id is not None:
            total_q = total_q.where(VideoTask.owner_id == owner_id)
        total: int = (await self.db.execute(total_q)).scalar() or 0

        # Selected count (pending_publish / queued / publishing / published)
        SELECTED_STATUSES = ("pending_publish", "queued", "publishing", "published")
        sel_q = select(func.count(VideoTask.id)).where(
            VideoTask.account_id == task.account_id,
            VideoTask.status.in_(SELECTED_STATUSES),
        )
        if owner_id is not None:
            sel_q = sel_q.where(VideoTask.owner_id == owner_id)
        selected_count: int = (await self.db.execute(sel_q)).scalar() or 0

        # Prev task (lower index = newer = created_at > current), only reviewing
        prev_q = (
            _base_task_q()
            .where(VideoTask.account_id == task.account_id, VideoTask.created_at > task.created_at)
            .order_by(VideoTask.created_at.asc())
            .limit(1)
        )
        prev_task = (await self.db.execute(prev_q)).scalar_one_or_none()

        # Next task (higher index = older = created_at < current), only reviewing
        next_q = (
            _base_task_q()
            .where(VideoTask.account_id == task.account_id, VideoTask.created_at < task.created_at)
            .order_by(VideoTask.created_at.desc())
            .limit(1)
        )
        next_task = (await self.db.execute(next_q)).scalar_one_or_none()

        # Prev/next blogger task: only reviewing status
        prev_blogger_row = None
        next_blogger_row = None
        if account:
            prev_blogger_q = (
                select(VideoTask, Account)
                .join(Account, Account.id == VideoTask.account_id)
                .where(Account.created_at > account.created_at)
                .where(VideoTask.status == NAV_STATUS)
                .order_by(Account.created_at.asc(), VideoTask.created_at.asc())
                .limit(1)
            )
            if owner_id is not None:
                prev_blogger_q = prev_blogger_q.where(VideoTask.owner_id == owner_id)
            prev_blogger_row = (await self.db.execute(prev_blogger_q)).first()

            next_blogger_q = (
                select(VideoTask, Account)
                .join(Account, Account.id == VideoTask.account_id)
                .where(Account.created_at < account.created_at)
                .where(VideoTask.status == NAV_STATUS)
                .order_by(Account.created_at.desc(), VideoTask.created_at.desc())
                .limit(1)
            )
            if owner_id is not None:
                next_blogger_q = next_blogger_q.where(VideoTask.owner_id == owner_id)
            next_blogger_row = (await self.db.execute(next_blogger_q)).first()

        return {
            "position": position,
            "total": total,
            "selected_count": selected_count,
            "prev_task": prev_task,
            "next_task": next_task,
            "prev_blogger_task": prev_blogger_row,
            "next_blogger_task": next_blogger_row,
            "account": account,
        }

    async def delete_task(self, task_id: uuid.UUID, owner_id: uuid.UUID | None) -> bool:
        q = select(VideoTask).where(VideoTask.id == task_id)
        if owner_id is not None:
            q = q.where(VideoTask.owner_id == owner_id)
        task = (await self.db.execute(q)).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        if task.target_date < date.today():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不允许删除今日之前的任务")
        if task.status not in ("pending", "generating"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="只能删除 pending 或 generating 状态的任务")
        await self.db.delete(task)
        await self.db.commit()
        return True

    async def delete_sub_task(self, sub_task_id: uuid.UUID, owner_id: uuid.UUID | None) -> dict:
        """删除待发布的 sub_task，若父 task 无剩余有效 sub_task 则一并删除 task"""
        q = (
            select(VideoSubTask)
            .where(VideoSubTask.id == sub_task_id)
            .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
        )
        sub_task = (await self.db.execute(q)).scalar_one_or_none()
        if not sub_task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")

        task = sub_task.task
        if owner_id is not None and task.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作")

        if sub_task.status != "pending_publish":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"只能删除待发布状态的子任务，当前状态: {sub_task.status}",
            )

        await self.db.delete(sub_task)

        # 若父任务除本 sub_task 外无其他非 abandoned sub_task，则删除父任务
        remaining = [st for st in task.sub_tasks if st.id != sub_task_id and st.status != "abandoned"]
        if not remaining:
            await self.db.delete(task)
            await self.db.commit()
            return {"deleted_task": True}

        # 否则重新计算父任务状态
        # 先 flush 使 sub_task 从 task.sub_tasks 中移除，再重算
        await self.db.flush()
        updated_subs = [st for st in task.sub_tasks if st.id != sub_task_id]
        task.status = _compute_parent_status(updated_subs) if updated_subs else "pending"
        await self.db.commit()
        return {"deleted_task": False}

    async def upload_tasks(self, target_date: date, owner_id: uuid.UUID | None) -> tuple[str, int, int]:
        """
        Upload all pending tasks for the date to GCS.
        Each sub-task gets one entry in the payload using its UUID as video_id.
        Returns (gcs_url, task_count, subtask_count).
        """
        tasks, _ = await self.get_tasks(target_date, owner_id, status_filter="pending")
        if not tasks:
            raise ValueError(f"No pending tasks found for {target_date}")

        if not self.bucket:
            raise RuntimeError("GCS bucket not initialized")

        payload = []
        for task in tasks:
            image_urls = _extract_image_urls(task.shots)
            prompt_text = (task.prompt.replace("\n", " ").replace("\r", "").strip() if task.prompt else "")[:1990]
            for sub in task.sub_tasks:
                sub_prompt = f"video_id: {sub.id}\n{prompt_text}"
                payload.append({
                    "prompt": sub_prompt,
                    "image_urls": image_urls,
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
        Uploads are processed concurrently. Successfully uploaded videos are then enqueued
        into the background AI scoring queue.
        """
        # Fetch all tasks for the date (regardless of parent status) and filter by sub-task status
        tasks, _ = await self.get_tasks(target_date, owner_id)
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

        enqueued_for_scoring = 0
        if not successfully_uploaded:
            # All subtasks failed upload, update parent statuses and return
            for task in valid_tasks:
                task.status = _compute_parent_status(task.sub_tasks)
            await self.db.commit()
            return {"updated": updated, "skipped": skipped, "errors": errors, "queued_for_scoring": enqueued_for_scoring}

        task_ids_to_queue = {task.id for task, _, _ in successfully_uploaded}
        for task_id in task_ids_to_queue:
            if await enqueue_video_scoring_task(task_id):
                enqueued_for_scoring += 1

        logger.info("Queued %s tasks for background AI scoring", enqueued_for_scoring)
        return {"updated": updated, "skipped": skipped, "errors": errors, "queued_for_scoring": enqueued_for_scoring}

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

    # Dimension weights for multi-dimension scoring
    DIMENSION_WEIGHTS = {
        "audio_visual": 20,        # 声画与听觉
        "character_realism": 30,   # 人物与全身拟真
        "performance_narrative": 15, # 表演与叙事
        "editing_transition": 12,  # 剪辑与转场
        "camera_composition": 12,  # 镜头与构图
        "visual_environment": 11,  # 画面与环境
    }

    async def update_sub_task_note(
        self,
        sub_task_id: uuid.UUID,
        owner_id: uuid.UUID | None,
        manual_note: str | None,
        manual_score: int | None = None,
        temporal_consistency: bool | None = None,
        character_integrity: bool | None = None,
        audio_sync: bool | None = None,
        dimension_scores: dict | None = None,
    ) -> VideoSubTask:
        q = select(VideoSubTask).where(VideoSubTask.id == sub_task_id).options(
            selectinload(VideoSubTask.task)
        )
        sub = (await self.db.execute(q)).scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")
        if owner_id is not None and sub.task.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子任务不存在")

        # Update critical checks if provided
        if temporal_consistency is not None:
            sub.temporal_consistency = temporal_consistency
        if character_integrity is not None:
            sub.character_integrity = character_integrity
        if audio_sync is not None:
            sub.audio_sync = audio_sync

        # Compute critical_fail: any False → fail
        checks = [sub.temporal_consistency, sub.character_integrity, sub.audio_sync]
        if any(v is False for v in checks):
            sub.critical_fail = True
        elif all(v is True for v in checks):
            sub.critical_fail = False
        else:
            sub.critical_fail = None  # Not fully evaluated yet

        # Update dimension scores if provided
        if dimension_scores is not None:
            sub.dimension_scores = dimension_scores

        # Compute weighted total score from dimension_scores
        if sub.dimension_scores and not sub.critical_fail:
            total = 0.0
            for dim, weight in self.DIMENSION_WEIGHTS.items():
                score = sub.dimension_scores.get(dim)
                if score is not None:
                    total += (score / 5) * weight
            sub.weighted_total_score = round(total, 1)
            sub.manual_score = round(total)
        elif sub.critical_fail:
            sub.weighted_total_score = 0
            sub.manual_score = 0

        if manual_note is not None:
            sub.manual_note = manual_note

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

        was_pending_publish = sub.status == "pending_publish"
        sub.status = prev
        sub.selected = False

        # 从 pending_publish 撤回时，将所有被废弃的兄弟子任务一并恢复到 reviewing
        if was_pending_publish:
            for sibling in sub.task.sub_tasks:
                if sibling.id != sub.id and sibling.status == "abandoned":
                    sibling.status = "reviewing"
                    sibling.selected = False

        sub.task.status = _compute_parent_status(sub.task.sub_tasks)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def enqueue_sub_task(
        self,
        sub_task_id: uuid.UUID,
        owner_id: uuid.UUID | None,
    ) -> VideoSubTask:
        """将子任务从 pending_publish 状态移到 queued 状态，进入发布队列"""
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

        if sub.status != "pending_publish":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"只有 pending_publish 状态的子任务才能进入队列",
            )

        sub.status = "queued"
        # 如果没有设置 queue_order，设置为当前时间戳，确保排在最后
        if sub.queue_order is None:
            # 获取当前最大的 queue_order
            from sqlalchemy import func
            max_order = await self.db.execute(
                select(func.max(VideoSubTask.queue_order)).where(VideoSubTask.status == "queued")
            )
            max_order_val = max_order.scalar()
            sub.queue_order = (max_order_val or 0) + 1

        sub.task.status = _compute_parent_status(sub.task.sub_tasks)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def dequeue_sub_task(
        self,
        sub_task_id: uuid.UUID,
        owner_id: uuid.UUID | None,
    ) -> VideoSubTask:
        """将子任务从 queued 状态移回 pending_publish 状态"""
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

        if sub.status != "queued":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"只有 queued 状态的子任务才能移出队列",
            )

        sub.status = "pending_publish"
        sub.queue_order = None  # 清除排序

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
        tiktok_blogger_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """Returns (enriched task list, total count). Supports pagination."""
        tasks, total = await self.get_tasks(
            target_date, owner_id, account_id, status_filter, tiktok_blogger_id,
            page=page, page_size=page_size,
        )

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
        return result, total

    async def resume_scoring_tasks(self, target_date: date, owner_id: uuid.UUID | None) -> dict[str, int]:
        tasks, _ = await self.get_tasks(target_date, owner_id)
        queued = 0
        skipped = 0
        for task in tasks:
            has_scoring = any(sub.status == "scoring" and sub.result_video_url for sub in task.sub_tasks)
            if not has_scoring:
                continue
            if await enqueue_video_scoring_task(task.id):
                queued += 1
            else:
                skipped += 1
        return {"queued": queued, "skipped": skipped}

    async def process_scoring_task(self, task_id: uuid.UUID | str) -> dict[str, Any]:
        q = (
            select(VideoTask)
            .where(VideoTask.id == task_id)
            .options(selectinload(VideoTask.sub_tasks))
        )
        task = (await self.db.execute(q)).scalar_one_or_none()
        if not task:
            logger.warning("Scoring queue skipped missing task %s", task_id)
            return {"status": "missing"}
        scoring_subs = [sub for sub in task.sub_tasks if sub.status == "scoring"]
        if not scoring_subs:
            logger.info("Scoring queue skipped task %s because no sub-task is in scoring", task.id)
            return {"status": "skipped", "reason": "no_scoring_subtasks"}

        config = await self.db.get(VideoTaskConfig, task.owner_id)
        sys_cfg = await self.db.get(SystemSetting, "default")

        task.status = _compute_parent_status(task.sub_tasks)
        await self.db.commit()

        has_retryable_failure = False
        processed = 0

        for sub in scoring_subs:
            if not sub.result_video_url:
                sub.scoring_error = "缺少 result_video_url，无法进行 AI 打分"
                continue

            sub.scoring_error = None
            await self.db.commit()

            try:
                result = await self._score_video(sub, sub.result_video_url, config=config, sys_cfg=sys_cfg)
            except Exception as exc:
                logger.exception("AI scoring crashed for sub-task %s", sub.id)
                sub.scoring_error = str(exc)[:1000]
                has_retryable_failure = True
                continue

            if not result:
                sub.scoring_error = "AI 打分未返回结果"
                continue

            if result[0] is None:
                error_message = ""
                if len(result) >= 3:
                    error_message = str(result[2] or "")
                sub.scoring_error = error_message or "AI 打分失败"
                if _is_retryable_scoring_error(sub.scoring_error):
                    has_retryable_failure = True
                continue

            final_score, round1_score, round2_score, round1_reason, round2_reason = result
            sub.ai_score = int(final_score) if final_score >= 0 else None
            sub.round1_score = int(round1_score) if round1_score is not None else None
            sub.round2_score = int(round2_score) if round2_score is not None else None
            sub.round1_reason = round1_reason
            sub.round2_reason = round2_reason
            sub.scoring_error = None
            processed += 1

            if final_score < 0:
                sub.status = "abandoned"
                logger.info("Sub-task %s abandoned due to low AI score", sub.id)
            else:
                sub.status = "reviewing"
                logger.info("Sub-task %s AI scored successfully: final=%.1f", sub.id, final_score)

        refreshed_task = (
            await self.db.execute(
                select(VideoTask)
                .where(VideoTask.id == task.id)
                .options(selectinload(VideoTask.sub_tasks))
            )
        ).scalar_one()
        finalized = await self._finalize_scored_task_if_ready(refreshed_task, config)
        if not finalized:
            refreshed_task.status = _compute_parent_status(refreshed_task.sub_tasks)
        await self.db.commit()

        if has_retryable_failure:
            _schedule_scoring_retry(refreshed_task.id)

        return {"status": "completed", "finalized": finalized, "processed": processed}

    async def _finalize_scored_task_if_ready(
        self,
        task: VideoTask,
        config: VideoTaskConfig | None,
    ) -> bool:
        retry_pending = [
            st for st in task.sub_tasks
            if st.status == "scoring" and st.scoring_error and st.ai_score is None and st.round1_score is None
        ]
        if retry_pending:
            logger.info("Task %s still has %s scoring subtasks waiting for retry", task.id, len(retry_pending))
            return False

        in_progress = [
            st for st in task.sub_tasks
            if st.status == "scoring" and not st.scoring_error and st.ai_score is None and st.round1_score is None
        ]
        if in_progress:
            return False

        # 打分完成后所有子任务停留在 reviewing 状态，由用户手动选择发布版本
        task.status = _compute_parent_status(task.sub_tasks)
        logger.info("Task %s all sub-tasks scored, waiting for manual selection", task.id)
        return True

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

    # ── Download videos ────────────────────────────────────────────────────────

    async def download_videos(
        self,
        target_date: date,
        owner_id: uuid.UUID | None,
    ) -> tuple["io.BytesIO", str] | tuple[None, None]:
        """
        下载指定日期当天发布成功的视频，按账号分文件夹打包成 ZIP 返回。
        文件夹名：account_name
        文件名：account_id_account_name_发布时间.mp4（VideoPublication.completed_at）
        """
        import io
        import re
        import zipfile
        from sqlalchemy import func, cast, Date
        from app.models.video_publication import VideoPublication

        stmt = (
            select(VideoTask, VideoSubTask, VideoPublication, Account)
            .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
            .join(VideoPublication, VideoPublication.sub_task_id == VideoSubTask.id)
            .join(Account, Account.id == VideoTask.account_id)
            .where(VideoPublication.status == "completed")
            .where(VideoSubTask.result_video_url.isnot(None))
            .where(cast(VideoPublication.completed_at, Date) == target_date)
        )
        if owner_id is not None:
            stmt = stmt.where(VideoTask.owner_id == owner_id)

        rows = (await self.db.execute(stmt)).all()
        if not rows:
            return None, None

        def sanitize(name: str) -> str:
            return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

        date_str = target_date.strftime("%Y%m%d")
        root = f"videos_{date_str}"
        zip_filename = f"videos_{date_str}.zip"

        buf = io.BytesIO()
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for task, sub_task, publication, account in rows:
                    folder = sanitize(account.account_name)
                    pub_time = publication.completed_at or publication.updated_at or task.created_at
                    pub_str = pub_time.strftime("%Y%m%d_%H%M%S")
                    filename = f"{account.id}_{sanitize(account.account_name)}_{pub_str}.mp4"
                    arc_path = f"{root}/{folder}/{filename}"
                    try:
                        resp = await client.get(sub_task.result_video_url)
                        resp.raise_for_status()
                        zf.writestr(arc_path, resp.content)
                        logger.info("Packed video %s → %s", sub_task.result_video_url, arc_path)
                    except Exception as exc:
                        logger.warning(
                            "Skip video for task %s (account %s): %s",
                            task.id, account.account_name, exc,
                        )

        buf.seek(0)
        return buf, zip_filename

    async def download_latest_published_videos(
        self,
        owner_id: uuid.UUID | None,
    ) -> tuple["io.BytesIO", str] | tuple[None, None]:
        """
        下载每个账号最新已发布的视频，同时打包对应的 caption/hashtag txt。
        文件夹名：account_name
        文件名：account_id_account_name_发布时间.mp4 / .txt
        txt 内容：标题 + 描述 + 标签（来自 VideoPublication.request_payload，若无则留空）
        以 VideoSubTask.status == 'published' 为主，LEFT JOIN VideoPublication 取 caption。
        """
        import io
        import re
        import zipfile
        from sqlalchemy import outerjoin
        from app.models.video_publication import VideoPublication

        # 以 VideoSubTask.status='published' 为准，LEFT JOIN VideoPublication 取 caption
        stmt = (
            select(VideoTask, VideoSubTask, VideoPublication, Account)
            .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
            .outerjoin(VideoPublication, VideoPublication.sub_task_id == VideoSubTask.id)
            .join(Account, Account.id == VideoTask.account_id)
            .where(VideoSubTask.status == "published")
            .where(VideoSubTask.result_video_url.isnot(None))
            .order_by(VideoSubTask.updated_at.desc())
        )
        if owner_id is not None:
            stmt = stmt.where(VideoTask.owner_id == owner_id)

        rows = (await self.db.execute(stmt)).all()
        if not rows:
            return None, None

        # 每个账号只保留最新一条（已按 updated_at DESC 排序）
        seen_accounts: set[uuid.UUID] = set()
        latest_rows = []
        for row in rows:
            task, sub_task, publication, account = row
            if account.id not in seen_accounts:
                seen_accounts.add(account.id)
                latest_rows.append(row)

        def sanitize(name: str) -> str:
            return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

        def build_caption_txt(payload: dict | None) -> str:
            if not payload:
                return ""
            lines = []
            if payload.get("title"):
                lines.append(f"标题：{payload['title']}")
            if payload.get("description"):
                lines.append(f"描述：{payload['description']}")
            tags = payload.get("tags") or []
            if tags:
                lines.append(f"标签：{' '.join(f'#{t}' if not t.startswith('#') else t for t in tags)}")
            return "\n".join(lines)

        root = "videos_latest"
        zip_filename = "videos_latest.zip"

        buf = io.BytesIO()
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for task, sub_task, publication, account in latest_rows:
                    folder = sanitize(account.account_name)
                    pub_time = sub_task.updated_at or task.created_at
                    pub_str = pub_time.strftime("%Y%m%d_%H%M%S")
                    base_name = f"{account.id}_{sanitize(account.account_name)}_{pub_str}"
                    video_path = f"{root}/{folder}/{base_name}.mp4"
                    txt_path = f"{root}/{folder}/{base_name}_caption.txt"
                    try:
                        resp = await client.get(sub_task.result_video_url)
                        resp.raise_for_status()
                        zf.writestr(video_path, resp.content)
                        caption_text = build_caption_txt(publication.request_payload)
                        zf.writestr(txt_path, caption_text.encode("utf-8"))
                        logger.info("Packed latest video for account %s → %s", account.account_name, video_path)
                    except Exception as exc:
                        logger.warning(
                            "Skip latest video for account %s: %s",
                            account.account_name, exc,
                        )

        buf.seek(0)
        return buf, zip_filename
