from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import WebSocket

from app.db.session import SessionLocal
from app.models.enums import TaskStatus
from app.models.task import Task

logger = logging.getLogger("app.execution")

# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

MAX_EVENT_LOG = 300
PERSIST_FLUSH_INTERVAL_SECONDS = 2.0
STATE_CLEANUP_INTERVAL_SECONDS = 3600.0
STATE_RETENTION_SECONDS = 3600.0

# ──────────────────────────────────────────────
# 全局内存状态（单例，仅在本进程内有效）
# ──────────────────────────────────────────────

ws_connections: dict[str, set[WebSocket]] = {}
execution_states: dict[str, dict] = {}
dirty_execution_task_ids: set[str] = set()
persist_worker_task: asyncio.Task | None = None
cleanup_worker_task: asyncio.Task | None = None
listener_stop_events: dict[str, asyncio.Event] = {}
listener_tasks: dict[str, asyncio.Task] = {}


# ──────────────────────────────────────────────
# 状态构建/读取/更新
# ──────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_log_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def new_execution_state(task_id: str, *, status_value: str) -> dict:
    return {
        "task_id": task_id,
        "status": status_value,
        "prompt_id": "",
        "prompt_ids": [],
        "completed_prompt_ids": [],
        "current_node_id": "",
        "current_node_title": "",
        "current_node_class_type": "",
        "target_endpoint": {"server_ip": "", "port": 0, "base_url": ""},
        "progress": {"node_id": "", "node_title": "", "node_class_type": "", "value": 0, "max": 0},
        "error_message": "",
        "event_log": [],
        "completed_node_count": 0,
        "updated_at": now_iso(),
    }


def build_workflow_node_map(workflow_json: dict | None) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if not isinstance(workflow_json, dict):
        return result
    for raw_node_id, raw_node in workflow_json.items():
        node_id = str(raw_node_id)
        if not isinstance(raw_node, dict):
            result[node_id] = {"title": "", "class_type": ""}
            continue
        meta = raw_node.get("_meta") or {}
        title = meta.get("title", "") if isinstance(meta, dict) else ""
        class_type = raw_node.get("class_type", "")
        result[node_id] = {
            "title": str(title or ""),
            "class_type": str(class_type or ""),
        }
    return result


def resolve_node_meta(task_id: str, node_id: str | None) -> tuple[str, str]:
    if not node_id:
        return "", ""
    state = execution_states.get(task_id) or {}
    node_map = state.get("_node_map") or {}
    if not isinstance(node_map, dict):
        return "", ""
    info = node_map.get(str(node_id)) or {}
    if not isinstance(info, dict):
        return "", ""
    return str(info.get("title", "") or ""), str(info.get("class_type", "") or "")


def format_node_display(node_id: str | None, node_title: str, node_class_type: str) -> str:
    if not node_id:
        return "-"
    if node_title:
        return f"{node_id} ({node_title})"
    if node_class_type:
        return f"{node_id} ({node_class_type})"
    return str(node_id)


def public_execution_state(state_snapshot: dict | None) -> dict | None:
    if not isinstance(state_snapshot, dict):
        return None
    return {k: v for k, v in state_snapshot.items() if not str(k).startswith("_")}


def append_event_log(task_id: str, message: str, level: str = "info") -> None:
    state = execution_states.get(task_id)
    if state is None:
        return
    entries = state.setdefault("event_log", [])
    entries.append({"time": now_log_time(), "message": message, "type": level})
    if len(entries) > MAX_EVENT_LOG:
        state["event_log"] = entries[-MAX_EVENT_LOG:]
    state["updated_at"] = now_iso()
    mark_dirty(task_id)


def mark_dirty(task_id: str) -> None:
    if not task_id:
        return
    dirty_execution_task_ids.add(task_id)
    ensure_persist_worker()
    ensure_cleanup_worker()


# ──────────────────────────────────────────────
# Worker 管理
# ──────────────────────────────────────────────


def ensure_persist_worker() -> None:
    global persist_worker_task
    if persist_worker_task is not None and not persist_worker_task.done():
        return
    loop = asyncio.get_running_loop()
    persist_worker_task = loop.create_task(_persist_worker_loop())


def ensure_cleanup_worker() -> None:
    global cleanup_worker_task
    if cleanup_worker_task is not None and not cleanup_worker_task.done():
        return
    loop = asyncio.get_running_loop()
    cleanup_worker_task = loop.create_task(_cleanup_worker_loop())


async def _persist_worker_loop() -> None:
    try:
        while True:
            await asyncio.sleep(PERSIST_FLUSH_INTERVAL_SECONDS)
            task_ids = list(dirty_execution_task_ids)
            if not task_ids:
                continue
            dirty_execution_task_ids.difference_update(task_ids)
            await persist_execution_states(task_ids)
    except asyncio.CancelledError:
        task_ids = list(dirty_execution_task_ids)
        if task_ids:
            dirty_execution_task_ids.difference_update(task_ids)
            await persist_execution_states(task_ids)
        raise
    except Exception:
        logger.exception("Execution state persist worker crashed")


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _should_cleanup(task_id: str, state: dict, now_utc: datetime) -> bool:
    if task_id in listener_stop_events:
        return False
    if ws_connections.get(task_id):
        return False
    status_value = str(state.get("status") or "")
    if status_value == TaskStatus.running.value:
        return False
    updated_at = _parse_iso_datetime(state.get("updated_at"))
    if updated_at is None:
        return True
    return (now_utc - updated_at).total_seconds() >= STATE_RETENTION_SECONDS


def cleanup_states_once() -> None:
    if not execution_states:
        return
    now_utc = datetime.now(timezone.utc)
    removable = [
        task_id
        for task_id, state in list(execution_states.items())
        if isinstance(state, dict) and _should_cleanup(task_id, state, now_utc)
    ]
    if not removable:
        return
    for task_id in removable:
        execution_states.pop(task_id, None)
        dirty_execution_task_ids.discard(task_id)
    logger.info("Execution state cleanup: removed=%s", len(removable))


async def _cleanup_worker_loop() -> None:
    try:
        while True:
            await asyncio.sleep(STATE_CLEANUP_INTERVAL_SECONDS)
            cleanup_states_once()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Execution state cleanup worker crashed")


# ──────────────────────────────────────────────
# WebSocket 广播
# ──────────────────────────────────────────────


async def broadcast_to_task(task_id: str, message: dict) -> None:
    clients = ws_connections.get(task_id, set()).copy()
    for ws in clients:
        try:
            await ws.send_json(message)
        except Exception:
            ws_connections.get(task_id, set()).discard(ws)


# ──────────────────────────────────────────────
# DB 持久化
# ──────────────────────────────────────────────


def serialize_state(state_snapshot: dict) -> str:
    public_state = public_execution_state(state_snapshot) or {}
    return json.dumps(public_state, ensure_ascii=False)


def deserialize_state(raw: str) -> dict | None:
    try:
        value = json.loads(raw)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


async def persist_execution_states(task_ids: list[str]) -> None:
    if not task_ids:
        return
    async with SessionLocal() as session:
        for task_id in task_ids:
            state_snapshot = execution_states.get(task_id)
            if state_snapshot is None:
                continue
            try:
                task_uuid = UUID(task_id)
            except ValueError:
                continue
            task = await session.get(Task, task_uuid)
            if not task:
                continue
            task.execution_state = serialize_state(state_snapshot)
        await session.commit()


async def set_task_status(*, task_id: str, status_value: TaskStatus, message: str | None = None) -> None:
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return
    async with SessionLocal() as session:
        task = await session.get(Task, task_uuid)
        if not task:
            return
        task.status = status_value
        task.comfy_message = message
        state_snapshot = execution_states.get(task_id)
        if state_snapshot is not None:
            task.execution_state = serialize_state(state_snapshot)
        await session.commit()


async def load_persisted_state(task_id: str) -> dict | None:
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return None
    async with SessionLocal() as session:
        task = await session.get(Task, task_uuid)
        if not task:
            return None
        persisted = deserialize_state(task.execution_state or "")
        if persisted is None:
            extra = task.extra or {}
            legacy = extra.get("execution_state")
            if isinstance(legacy, dict):
                persisted = legacy
        if not isinstance(persisted, dict):
            return None
        persisted.setdefault("task_id", task_id)
        persisted.setdefault("status", task.status.value if task.status else TaskStatus.pending.value)
        persisted.setdefault("prompt_id", "")
        persisted.setdefault("prompt_ids", [])
        persisted.setdefault("completed_prompt_ids", [])
        persisted.setdefault("current_node_id", "")
        persisted.setdefault("current_node_title", "")
        persisted.setdefault("current_node_class_type", "")
        target_endpoint = persisted.get("target_endpoint")
        if not isinstance(target_endpoint, dict):
            target_endpoint = {}
        target_endpoint.setdefault("server_ip", "")
        target_endpoint.setdefault("port", 0)
        target_endpoint.setdefault("base_url", "")
        persisted["target_endpoint"] = target_endpoint
        progress = persisted.get("progress")
        if not isinstance(progress, dict):
            progress = {}
        progress.setdefault("node_id", "")
        progress.setdefault("node_title", "")
        progress.setdefault("node_class_type", "")
        progress.setdefault("value", 0)
        progress.setdefault("max", 0)
        persisted["progress"] = progress
        persisted.setdefault("error_message", "")
        persisted.setdefault("event_log", [])
        persisted.setdefault("completed_node_count", 0)
        persisted.setdefault("updated_at", now_iso())
        persisted["_node_map"] = build_workflow_node_map(task.workflow_json)
        return persisted
