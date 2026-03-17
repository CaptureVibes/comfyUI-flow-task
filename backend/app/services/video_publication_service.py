import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, date, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.account import Account
from app.models.video_publication import VideoPublication
from app.schemas.video_publication import VideoPublicationCreate

logger = logging.getLogger("app.video_publication_service")

# ── 后台轮询器 ──────────────────────────────────────────────────────────────────

_POLL_INTERVAL_SECONDS = 60.0

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

    @staticmethod
    def _value_to_sign_str(v) -> str:
        """将参数值规范序列化为签名字符串"""
        if v is None:
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, (list, dict)):
            return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return str(v)

    def _generate_signature(self, params: dict, timestamp: int) -> str:
        """生成 HMAC-SHA256 签名"""
        # 过滤掉 signature 和 None/空字符串
        filtered = {k: v for k, v in params.items() if k != "signature" and v is not None and v != ""}
        # 按字母排序，值规范序列化后拼接
        param_str = "&".join(
            f"{k}={self._value_to_sign_str(v)}" for k, v in sorted(filtered.items())
        )
        # 追加 timestamp
        sign_str = f"{param_str}&timestamp={timestamp}"
        return hmac.new(
            self.client_secret.encode(),
            sign_str.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _sign_params(self, params: dict) -> dict:
        """为请求参数添加签名"""
        timestamp = int(utcnow().timestamp())
        # 传入 timestamp 使其参与排序拼接，_generate_signature 末尾再追加一次（服务端规则）
        signature = self._generate_signature({**params, "client_id": self.client_id, "timestamp": timestamp}, timestamp)
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
        logged_params = dict(signed_params)
        if "signature" in logged_params:
            sig = str(logged_params["signature"])
            logged_params["signature"] = f"{sig[:8]}...{sig[-6:]}" if len(sig) > 14 else "***"
        logger.info(
            "Open API fetch_channels outbound request: base_url=%s params=%s",
            self.base_url,
            logged_params,
        )

        # trust_env=False 禁用系统代理；渠道列表是 UI 辅助接口，超时缩短到 5s
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/open-api/v1/channels",
                params=signed_params,
            )
            response.raise_for_status()
            result = response.json()
            data = result.get("data", {}) if isinstance(result, dict) else {}
            logger.info(
                "Open API fetch_channels outbound response: status=%s code=%s total=%s items=%s message=%s",
                response.status_code,
                result.get("code") if isinstance(result, dict) else None,
                data.get("total"),
                len(data.get("items") or []),
                result.get("message") if isinstance(result, dict) else None,
            )
            return result

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

    async def fetch_upload_metrics(self, task_id: str | None = None, external_id: str | None = None) -> dict:
        """查询上传任务各渠道视频指标"""
        params = {}
        if task_id:
            params["task_id"] = task_id
        if external_id:
            params["external_id"] = external_id

        signed_params = self._sign_params(params)

        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/open-api/v1/upload/metrics",
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
                sub_task.status = "publish_failed"

                from app.services.video_task_service import _compute_parent_status
                sub_task.task.status = _compute_parent_status(sub_task.task.sub_tasks)

        await self.db.commit()
        await self.db.refresh(publication)

        return publication

    async def handle_callback(self, callback_data: dict) -> VideoPublication | None:
        """处理 Open API 回调"""
        task_id = callback_data.get("task_id")
        external_id = callback_data.get("external_id")

        logger.info(
            "handle_callback: looking up publication by task_id=%s OR external_id=%s",
            task_id, external_id,
        )

        # 查找对应的发布任务：优先同时匹配 open_api_task_id 和 external_id（AND），
        # 若未找到则单独用 open_api_task_id 回退（external_id 可能重复，不单独作为回退）
        from sqlalchemy import select

        publication = None
        if task_id and external_id:
            result = await self.db.execute(
                select(VideoPublication).where(
                    (VideoPublication.open_api_task_id == task_id) &
                    (VideoPublication.external_id == external_id)
                )
            )
            publication = result.scalar_one_or_none()

        if publication is None and task_id:
            result = await self.db.execute(
                select(VideoPublication).where(VideoPublication.open_api_task_id == task_id)
            )
            publication = result.scalar_one_or_none()

        if not publication:
            # 打印所有 publication 记录帮助排查
            all_pubs = (await self.db.execute(select(VideoPublication))).scalars().all()
            logger.warning(
                "handle_callback: no publication found. Total publications in DB: %d. "
                "task_ids=%s, external_ids=%s",
                len(all_pubs),
                [p.open_api_task_id for p in all_pubs],
                [p.external_id for p in all_pubs],
            )
            return None

        # 更新 publication 状态
        new_status = callback_data.get("status", publication.status)
        publication.status = new_status
        publication.total_channels = callback_data.get("total_channels", publication.total_channels)
        publication.completed_channels = callback_data.get("completed_channels", publication.completed_channels)
        publication.failed_channels = callback_data.get("failed_channels", publication.failed_channels)
        publication.channels_status = callback_data.get("channels")
        publication.callback_received = True
        publication.callback_received_at = utcnow()

        if callback_data.get("completed_at"):
            from datetime import datetime
            completed_at = callback_data["completed_at"]
            if isinstance(completed_at, datetime):
                publication.completed_at = completed_at
            else:
                publication.completed_at = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))

        logger.info(
            "handle_callback: updating publication %s to status=%s",
            publication.id, new_status,
        )

        # 同步更新 sub_task 状态（与 sync_publication_status 保持一致）
        if new_status in ("completed", "partial"):
            from sqlalchemy.orm import selectinload
            from app.models.video_task import VideoSubTask, VideoTask
            from app.services.video_task_service import _compute_parent_status

            result = await self.db.execute(
                select(VideoSubTask)
                .where(VideoSubTask.id == publication.sub_task_id)
                .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
            )
            sub_task = result.scalar_one_or_none()
            if sub_task and sub_task.status == "publishing":
                sub_task.status = "published"
                sub_task.task.status = _compute_parent_status(sub_task.task.sub_tasks)
                logger.info("handle_callback: sub_task %s → published", sub_task.id)

        elif new_status == "failed":
            from sqlalchemy.orm import selectinload
            from app.models.video_task import VideoSubTask, VideoTask
            from app.services.video_task_service import _compute_parent_status

            result = await self.db.execute(
                select(VideoSubTask)
                .where(VideoSubTask.id == publication.sub_task_id)
                .options(selectinload(VideoSubTask.task).selectinload(VideoTask.sub_tasks))
            )
            sub_task = result.scalar_one_or_none()
            if sub_task and sub_task.status == "publishing":
                sub_task.status = "publish_failed"

                sub_task.task.status = _compute_parent_status(sub_task.task.sub_tasks)
                logger.info("handle_callback: sub_task %s → publish_failed", sub_task.id)

        await self.db.commit()
        await self.db.refresh(publication)

        return publication

    async def fetch_channels(
        self,
        platform: str,
        page: int = 1,
        page_size: int = 20,
        is_active: bool | None = None,
    ) -> dict:
        """获取渠道列表（代理到 Open API）"""
        return await self.open_api.fetch_channels(platform, page=page, page_size=page_size, is_active=is_active)

    async def fetch_channels_filtered(
        self,
        platform: str,
        owner_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        is_active: bool | None = None,
        current_account_id: uuid.UUID | None = None,
    ) -> dict:
        """过滤掉当前用户下已被其他账号绑定过的渠道，并对过滤后的结果重新分页。"""
        excluded_channel_ids = await self._load_excluded_channel_ids(
            owner_id=owner_id,
            platform=platform,
            current_account_id=current_account_id,
        )
        logger.info(
            "Open API fetch_channels filtered request: platform=%s owner_id=%s page=%s page_size=%s current_account_id=%s excluded=%s",
            platform,
            owner_id,
            page,
            page_size,
            current_account_id,
            len(excluded_channel_ids),
        )
        if not excluded_channel_ids:
            return await self.fetch_channels(platform, page=page, page_size=page_size, is_active=is_active)

        upstream_page = 1
        upstream_page_size = max(page_size, 100)
        upstream_total = 0
        filtered_items: list[dict[str, Any]] = []

        while True:
            response = await self.open_api.fetch_channels(
                platform,
                page=upstream_page,
                page_size=upstream_page_size,
                is_active=is_active,
            )
            data = response.get("data", {}) if isinstance(response, dict) else {}
            raw_items = data.get("items") or []
            upstream_total = max(upstream_total, int(data.get("total") or 0))
            filtered_items.extend(
                item
                for item in raw_items
                if str(item.get("channel_id") or "").strip() not in excluded_channel_ids
            )
            if len(raw_items) < upstream_page_size:
                break
            if upstream_total and upstream_page * upstream_page_size >= upstream_total:
                break
            upstream_page += 1

        start = max(page - 1, 0) * page_size
        end = start + page_size
        page_items = filtered_items[start:end]
        logger.info(
            "Open API fetch_channels filtered response: platform=%s owner_id=%s upstream_total=%s filtered_total=%s page=%s page_size=%s returned=%s",
            platform,
            owner_id,
            upstream_total,
            len(filtered_items),
            page,
            page_size,
            len(page_items),
        )
        return {
            "code": 0,
            "message": "success",
            "data": {
                "items": page_items,
                "total": len(filtered_items),
                "page": page,
                "page_size": page_size,
            },
        }

    async def _load_excluded_channel_ids(
        self,
        owner_id: uuid.UUID,
        platform: str,
        current_account_id: uuid.UUID | None = None,
    ) -> set[str]:
        stmt = select(Account.id, Account.social_bindings).where(Account.owner_id == owner_id)
        if current_account_id is not None:
            stmt = stmt.where(Account.id != current_account_id)
        rows = (await self.db.execute(stmt)).all()

        excluded_channel_ids: set[str] = set()
        for _, bindings in rows:
            if not isinstance(bindings, list):
                continue
            for binding in bindings:
                if not isinstance(binding, dict):
                    continue
                if binding.get("platform") != platform:
                    continue
                channel_id = str(binding.get("channel_id") or "").strip()
                if channel_id:
                    excluded_channel_ids.add(channel_id)
        return excluded_channel_ids
