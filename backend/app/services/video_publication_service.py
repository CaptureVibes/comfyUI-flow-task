import asyncio
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.video_publication import VideoPublication
from app.schemas.video_publication import VideoPublicationCreate

logger = logging.getLogger("app.video_publication_service")

# ── 后台轮询器 ──────────────────────────────────────────────────────────────────

_POLL_INTERVAL_SECONDS = 20.0

_poller_task: asyncio.Task | None = None
_poller_stop_event: asyncio.Event | None = None


def start_video_publication_poller() -> None:
    global _poller_task, _poller_stop_event
    if _poller_task is not None and not _poller_task.done():
        return
    _poller_stop_event = asyncio.Event()
    _poller_task = asyncio.get_running_loop().create_task(
        _poller_loop(_poller_stop_event)
    )
    logger.info("Video publication poller started")


async def stop_video_publication_poller() -> None:
    global _poller_task, _poller_stop_event
    stop_event, worker = _poller_stop_event, _poller_task
    _poller_stop_event = None
    _poller_task = None
    if stop_event is not None:
        stop_event.set()
    if worker is None:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("Video publication poller stopped")


async def _poller_loop(stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            try:
                await _poll_once()
            except Exception:
                logger.exception("Publication poll run failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        pass


async def _poll_once() -> None:
    """查询所有进行中的 publication，逐一调用 Open API 同步状态。"""
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        result = await db.execute(
            select(VideoPublication).where(
                VideoPublication.status.in_(["pending", "processing", "uploading"])
            )
        )
        pub_ids: list[uuid.UUID] = [p.id for p in result.scalars().all()]

    if not pub_ids:
        return

    logger.debug("Polling %d in-progress publications", len(pub_ids))

    from app.db.session import SessionLocal

    for pub_id in pub_ids:
        try:
            async with SessionLocal() as db:
                service = VideoPublicationService(db)
                await service.sync_publication_status(pub_id)
        except ValueError as e:
            logger.warning("Skipping publication %s: %s", pub_id, e)
        except Exception:
            logger.exception("Failed to sync publication %s", pub_id)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OpenAPIClient:
    """Open API 客户端"""

    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.base_url = base_url or getattr(settings, "open_api_base_url", "http://192.168.199.28:8080")
        self.client_id = client_id or getattr(settings, "open_api_client_id", "default_client")
        self.client_secret = client_secret or getattr(
            settings, "open_api_client_secret", ""
        )
        self.timeout = 30.0

    def _generate_signature(self, params: dict, timestamp: int) -> str:
        """生成 HMAC-SHA256 签名"""
        # 过滤掉 signature 和 null/None 的值
        filtered = {k: v for k, v in params.items() if k != "signature" and v is not None}
        # 按字母排序
        sorted_keys = sorted(filtered.keys())
        # 拼接参数（值转为字符串）
        param_str = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)
        # 追加 timestamp
        sign_str = f"{param_str}&timestamp={timestamp}"
        # HMAC-SHA256
        signature = hmac.new(
            self.client_secret.encode(),
            sign_str.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _sign_params(self, params: dict) -> dict:
        """为请求参数添加签名"""
        timestamp = int(utcnow().timestamp())
        signature = self._generate_signature({**params, "client_id": self.client_id}, timestamp)
        return {
            **params,
            "client_id": self.client_id,
            "timestamp": timestamp,
            "signature": signature,
        }

    async def fetch_channels(
        self, platform: str, page: int = 1, page_size: int = 20, is_active: bool | None = None
    ) -> dict:
        """获取渠道列表"""
        params = {"platform": platform, "page": page, "page_size": page_size}
        if is_active is not None:
            params["is_active"] = is_active

        signed_params = self._sign_params(params)

        # trust_env=False 禁用系统代理
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/open-api/v1/channels",
                params=signed_params,
            )
            response.raise_for_status()
            return response.json()

    async def create_upload_task(self, payload: dict) -> dict:
        """创建视频上传任务"""
        signed_payload = self._sign_params(payload)

        # trust_env=False 禁用系统代理
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.post(
                f"{self.base_url}/open-api/v1/upload/task",
                json=signed_payload,
            )
            response.raise_for_status()
            return response.json()

    async def fetch_upload_status(self, task_id: str | None = None, external_id: str | None = None) -> dict:
        """查询上传任务状态"""
        params = {}
        if task_id:
            params["task_id"] = task_id
        if external_id:
            params["external_id"] = external_id

        signed_params = self._sign_params(params)

        # trust_env=False 禁用系统代理
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/open-api/v1/upload/status",
                params=signed_params,
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> dict:
        """健康检查"""
        # trust_env=False 禁用系统代理
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            response = await client.get(f"{self.base_url}/open-api/v1/health")
            response.raise_for_status()
            return response.json()


class VideoPublicationService:
    """视频发布服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.open_api = OpenAPIClient()

    async def create_publication(self, data: VideoPublicationCreate) -> VideoPublication:
        """创建发布任务"""
        # 构建请求 payload
        callback_url = data.callback_url or settings.open_api_callback_url or None
        request_payload = {
            "video_url": data.video_url,
            "title": data.title,
            "description": data.description,
            "tags": data.tags or [],
            "channels": data.channels,
            "external_id": str(data.sub_task_id),
        }
        if callback_url:
            request_payload["callback_url"] = callback_url

        # 调用 Open API 创建任务
        try:
            response = await self.open_api.create_upload_task(request_payload)

            if response.get("code") != 0:
                raise ValueError(response.get("message", "Open API 返回错误"))

            response_data = response.get("data", {})

            # 创建发布任务记录
            publication = VideoPublication(
                sub_task_id=data.sub_task_id,
                open_api_task_id=response_data.get("task_id"),
                external_id=str(data.sub_task_id),
                status=response_data.get("status", "pending"),
                request_payload=request_payload,
                response_data=response_data,
                total_channels=response_data.get("total_channels", len(data.channels)),
                completed_channels=response_data.get("completed_channels", 0),
                failed_channels=response_data.get("failed_channels", 0),
                channels_status=response_data.get("channels"),
            )

            self.db.add(publication)
            await self.db.commit()
            await self.db.refresh(publication)

            return publication

        except httpx.HTTPError as e:
            # 网络错误，创建失败记录
            publication = VideoPublication(
                sub_task_id=data.sub_task_id,
                external_id=str(data.sub_task_id),
                status="failed",
                request_payload=request_payload,
                total_channels=len(data.channels),
                error_message=f"Open API 请求失败: {str(e)}",
            )
            self.db.add(publication)
            await self.db.commit()
            await self.db.refresh(publication)
            raise

    async def get_publication(self, publication_id: uuid.UUID) -> VideoPublication | None:
        """获取发布任务"""
        from sqlalchemy import select

        result = await self.db.execute(
            select(VideoPublication).where(VideoPublication.id == publication_id)
        )
        return result.scalar_one_or_none()

    async def get_publications_by_sub_task(self, sub_task_id: uuid.UUID) -> list[VideoPublication]:
        """获取子任务的所有发布记录"""
        from sqlalchemy import select

        result = await self.db.execute(
            select(VideoPublication)
            .where(VideoPublication.sub_task_id == sub_task_id)
            .order_by(VideoPublication.created_at.desc())
        )
        return list(result.scalars().all())

    async def sync_publication_status(self, publication_id: uuid.UUID) -> VideoPublication:
        """从 Open API 同步发布任务状态，并同步更新 sub_task 状态"""
        publication = await self.get_publication(publication_id)
        if not publication:
            raise ValueError("发布任务不存在")

        if not publication.open_api_task_id:
            raise ValueError("Open API 任务 ID 不存在")

        # 调用 Open API 查询状态
        response = await self.open_api.fetch_upload_status(
            task_id=publication.open_api_task_id,
            external_id=publication.external_id,
        )

        if response.get("code") != 0:
            raise ValueError(response.get("message", "Open API 返回错误"))

        response_data = response.get("data", {})

        # 更新发布任务状态
        new_status = response_data.get("status", publication.status)
        publication.status = new_status
        publication.total_channels = response_data.get("total_channels", publication.total_channels)
        publication.completed_channels = response_data.get("completed_channels", publication.completed_channels)
        publication.failed_channels = response_data.get("failed_channels", publication.failed_channels)
        publication.channels_status = response_data.get("channels")
        publication.response_data = response_data

        if response_data.get("completed_at"):
            from datetime import datetime
            publication.completed_at = datetime.fromisoformat(response_data["completed_at"].replace("Z", "+00:00"))

        # 根据发布结果同步更新子任务状态
        if new_status in ("completed", "partial"):
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.video_task import VideoSubTask, VideoTask

            result = await self.db.execute(
                select(VideoSubTask)
                .where(VideoSubTask.id == publication.sub_task_id)
                .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
            )
            sub_task = result.scalar_one_or_none()
            if sub_task and sub_task.status == "publishing":
                sub_task.status = "published"
                from app.services.video_task_service import _compute_parent_status
                sub_task.task.status = _compute_parent_status(sub_task.task.sub_tasks)

        elif new_status == "failed":
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.video_task import VideoSubTask, VideoTask

            result = await self.db.execute(
                select(VideoSubTask)
                .where(VideoSubTask.id == publication.sub_task_id)
                .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
            )
            sub_task = result.scalar_one_or_none()
            if sub_task and sub_task.status == "publishing":
                sub_task.status = "pending_publish"
                from app.services.video_task_service import _compute_parent_status
                sub_task.task.status = _compute_parent_status(sub_task.task.sub_tasks)

        await self.db.commit()
        await self.db.refresh(publication)

        return publication

    async def handle_callback(self, callback_data: dict) -> VideoPublication | None:
        """处理 Open API 回调"""
        task_id = callback_data.get("task_id")
        external_id = callback_data.get("external_id")

        # 查找对应的发布任务
        from sqlalchemy import select

        result = await self.db.execute(
            select(VideoPublication).where(
                (VideoPublication.open_api_task_id == task_id) |
                (VideoPublication.external_id == external_id)
            )
        )
        publication = result.scalar_one_or_none()

        if not publication:
            return None

        # 更新状态
        publication.status = callback_data.get("status", publication.status)
        publication.total_channels = callback_data.get("total_channels", publication.total_channels)
        publication.completed_channels = callback_data.get("completed_channels", publication.completed_channels)
        publication.failed_channels = callback_data.get("failed_channels", publication.failed_channels)
        publication.channels_status = callback_data.get("channels")
        publication.callback_received = True
        publication.callback_received_at = utcnow()

        if callback_data.get("completed_at"):
            from datetime import datetime
            publication.completed_at = datetime.fromisoformat(callback_data["completed_at"].replace("Z", "+00:00"))

        await self.db.commit()
        await self.db.refresh(publication)

        return publication

    async def fetch_channels(self, platform: str, is_active: bool | None = None) -> dict:
        """获取渠道列表（代理到 Open API）"""
        return await self.open_api.fetch_channels(platform, is_active=is_active)
