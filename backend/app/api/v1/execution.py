from __future__ import annotations

import asyncio
import json
import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.enums import TaskStatus
from app.services.comfyui_listener import run_comfyui_listener
from app.services.comfyui_service import build_ws_base_url, fetch_queue_status
from app.services.comfyui_service import (
    delete_prompt_from_queue,
    fetch_queue_prompt_ids,
    interrupt_execution,
    submit_prompt,
)
from app.services.comfyui_settings_service import ensure_allowed_endpoint, parse_endpoint_from_execution_state
from app.services.execution_state import (
    append_event_log,
    broadcast_to_task,
    build_workflow_node_map,
    ensure_cleanup_worker,
    execution_states,
    listener_stop_events,
    listener_tasks,
    load_persisted_state,
    mark_dirty,
    new_execution_state,
    now_iso,
    public_execution_state,
    set_task_status,
    ws_connections,
)
from app.core.security import TokenData, get_current_user, verify_access_token
from app.services.task_service import bind_task_id_to_workflow, get_task_or_404

router = APIRouter(prefix="/execution", tags=["execution"])
# Separate router for WS endpoints — no global auth dependency (browsers can't send Bearer headers)
ws_router = APIRouter(prefix="/execution", tags=["execution-ws"])

logger = logging.getLogger("app.execution")


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────


class ExecuteTaskRequest(BaseModel):
    server_ip: str
    port: int


class ExecuteEndpoint(BaseModel):
    server_ip: str
    port: int
    base_url: str


class ExecuteTaskResponse(BaseModel):
    task_id: UUID
    prompt_id: str
    endpoint: ExecuteEndpoint


class CancelTaskResponse(BaseModel):
    task_id: UUID
    status: str
    message: str


# ──────────────────────────────────────────────
# 辅助：构建失败状态
# ──────────────────────────────────────────────


def _make_fail_state(task_id_str: str, workflow_json: dict | None, endpoint) -> dict:
    state = new_execution_state(task_id_str, status_value=TaskStatus.fail.value)
    state["_node_map"] = build_workflow_node_map(workflow_json)
    state["target_endpoint"] = {"server_ip": endpoint.server_ip, "port": endpoint.port, "base_url": endpoint.base_url}
    return state


# ──────────────────────────────────────────────
# Execute Task
# ──────────────────────────────────────────────


@router.post("/task/{task_id}", response_model=ExecuteTaskResponse)
async def execute_task(
    task_id: UUID,
    payload: ExecuteTaskRequest,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ExecuteTaskResponse:
    owner_id = None if current_user.is_admin else current_user.user_id
    task = await get_task_or_404(session, task_id, owner_id=owner_id)
    workflow_json, workflow_changed, matched_node_count = bind_task_id_to_workflow(task.workflow_json, task.id)
    if workflow_changed:
        task.workflow_json = workflow_json
        logger.info("GetTaskInfoNode task_id bound: task_id=%s matched_nodes=%s", task_id, matched_node_count)

    if task.status == TaskStatus.running:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is already running")

    if not workflow_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has no workflow JSON. Upload a workflow before executing.",
        )

    try:
        endpoint = await ensure_allowed_endpoint(session, server_ip=payload.server_ip, port=payload.port)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    probe_running_count, probe_pending_count, probe_error = await fetch_queue_status(api_base_url=endpoint.base_url)
    if probe_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected ComfyUI endpoint is unreachable: {probe_error}",
        )

    logger.info(
        "Execute task: task_id=%s status=%s node_count=%s endpoint=%s queue_running=%s queue_pending=%s",
        task_id, task.status.value if task.status else None,
        len(workflow_json) if isinstance(workflow_json, dict) else 0,
        endpoint.base_url, probe_running_count, probe_pending_count,
    )

    client_id = uuid.uuid4().hex
    ws_base_url = build_ws_base_url(endpoint.base_url)
    task_id_str = str(task_id)
    prompt_ids: set[str] = set()
    listener_stop_event = asyncio.Event()
    listener_connected_event = asyncio.Event()

    old_stop_event = listener_stop_events.pop(task_id_str, None)
    listener_tasks.pop(task_id_str, None)
    if old_stop_event is not None:
        old_stop_event.set()

    task.status = TaskStatus.running
    task.comfy_message = "Execution requested"
    await session.commit()

    initial_state = new_execution_state(task_id_str, status_value=TaskStatus.running.value)
    initial_state["_node_map"] = build_workflow_node_map(workflow_json)
    initial_state["target_endpoint"] = {"server_ip": endpoint.server_ip, "port": endpoint.port, "base_url": endpoint.base_url}
    execution_states[task_id_str] = initial_state
    append_event_log(task_id_str, "执行请求已提交，等待 ComfyUI 响应…", "info")
    append_event_log(task_id_str, f"目标端口: {endpoint.server_ip}:{endpoint.port}", "info")
    mark_dirty(task_id_str)

    listener_task = asyncio.create_task(
        run_comfyui_listener(
            client_id=client_id,
            task_id=task_id_str,
            ws_base_url=ws_base_url,
            prompt_ids=prompt_ids,
            stop_event=listener_stop_event,
            connected_event=listener_connected_event,
        )
    )
    listener_stop_events[task_id_str] = listener_stop_event
    listener_tasks[task_id_str] = listener_task

    try:
        await asyncio.wait_for(listener_connected_event.wait(), timeout=3.0)
        logger.info("ComfyUI listener connected: task_id=%s client_id=%s", task_id, client_id)
    except asyncio.TimeoutError:
        logger.warning("ComfyUI listener timeout, proceeding: task_id=%s client_id=%s", task_id, client_id)

    result = await submit_prompt(workflow_json, client_id=client_id, api_base_url=endpoint.base_url)
    logger.info("ComfyUI submit: task_id=%s prompt_id=%s error=%s", task_id, result.prompt_id or "", result.error or "")

    if result.error:
        listener_stop_event.set()
        await set_task_status(task_id=task_id_str, status_value=TaskStatus.fail, message=result.error)
        state = execution_states.get(task_id_str) or _make_fail_state(task_id_str, workflow_json, endpoint)
        execution_states[task_id_str] = state
        state["status"] = TaskStatus.fail.value
        state["error_message"] = result.error
        state["updated_at"] = now_iso()
        append_event_log(task_id_str, f"提交 ComfyUI 失败: {result.error}", "error")
        await broadcast_to_task(task_id_str, {"type": "listener_error", "data": {"message": f"ComfyUI submission failed: {result.error}"}})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"ComfyUI submission failed: {result.error}")

    if not result.prompt_id:
        listener_stop_event.set()
        msg = "ComfyUI returned empty prompt_id"
        await set_task_status(task_id=task_id_str, status_value=TaskStatus.fail, message=msg)
        state = execution_states.get(task_id_str) or _make_fail_state(task_id_str, workflow_json, endpoint)
        execution_states[task_id_str] = state
        state["status"] = TaskStatus.fail.value
        state["error_message"] = msg
        state["updated_at"] = now_iso()
        append_event_log(task_id_str, msg, "error")
        await broadcast_to_task(task_id_str, {"type": "listener_error", "data": {"message": msg}})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)

    task.comfy_message = None
    await session.commit()
    prompt_ids.add(result.prompt_id)

    state = execution_states.get(task_id_str)
    if state is None:
        state = new_execution_state(task_id_str, status_value=TaskStatus.running.value)
        state["_node_map"] = build_workflow_node_map(workflow_json)
        execution_states[task_id_str] = state
    state["status"] = TaskStatus.running.value
    state["prompt_id"] = result.prompt_id
    state["prompt_ids"] = sorted(prompt_ids)
    state["target_endpoint"] = {"server_ip": endpoint.server_ip, "port": endpoint.port, "base_url": endpoint.base_url}
    state["error_message"] = ""
    state["updated_at"] = now_iso()
    append_event_log(task_id_str, "执行开始", "info")
    mark_dirty(task_id_str)
    await broadcast_to_task(task_id_str, {"type": "execution_start", "prompt_id": result.prompt_id, "data": {"prompt_id": result.prompt_id}})

    return ExecuteTaskResponse(
        task_id=task.id,
        prompt_id=result.prompt_id,
        endpoint=ExecuteEndpoint(server_ip=endpoint.server_ip, port=endpoint.port, base_url=endpoint.base_url),
    )


# ──────────────────────────────────────────────
# Cancel Task
# ──────────────────────────────────────────────


@router.post("/task/{task_id}/cancel", response_model=CancelTaskResponse)
async def cancel_task_execution(
    task_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CancelTaskResponse:
    owner_id = None if current_user.is_admin else current_user.user_id
    task = await get_task_or_404(session, task_id, owner_id=owner_id)
    task_id_str = str(task_id)
    stop_event = listener_stop_events.get(task_id_str)

    if task.status != TaskStatus.running and stop_event is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not running")

    if stop_event is not None:
        stop_event.set()

    state = execution_states.get(task_id_str)
    if state is None:
        state = await load_persisted_state(task_id_str)
        if state is not None:
            execution_states[task_id_str] = state

    endpoint = parse_endpoint_from_execution_state(state)
    target_base_url = endpoint.base_url if endpoint is not None else settings.comfyui_api_base_url
    prompt_ids_from_state: set[str] = set()
    if isinstance(state, dict):
        raw_prompt_id = str(state.get("prompt_id") or "").strip()
        if raw_prompt_id:
            prompt_ids_from_state.add(raw_prompt_id)
        raw_prompt_ids = state.get("prompt_ids")
        if isinstance(raw_prompt_ids, list):
            for raw in raw_prompt_ids:
                pid = str(raw or "").strip()
                if pid:
                    prompt_ids_from_state.add(pid)

    interrupt_error: str | None = None
    queue_running_ids, queue_pending_ids, queue_error = await fetch_queue_prompt_ids(api_base_url=target_base_url)
    if queue_error:
        interrupt_error = queue_error
    else:
        operation_errors: list[str] = []
        matched_any = False
        for pid in sorted(prompt_ids_from_state):
            if pid in queue_pending_ids:
                matched_any = True
                delete_error = await delete_prompt_from_queue(api_base_url=target_base_url, prompt_id=pid)
                if delete_error:
                    operation_errors.append(f"{pid}: {delete_error}")
            elif pid in queue_running_ids:
                matched_any = True
                target_interrupt_error = await interrupt_execution(api_base_url=target_base_url, prompt_id=pid)
                if target_interrupt_error:
                    operation_errors.append(f"{pid}: {target_interrupt_error}")
        if not matched_any and not prompt_ids_from_state:
            logger.info("Cancel without prompt_id: task_id=%s", task_id_str)
        if operation_errors:
            interrupt_error = "; ".join(operation_errors)

    message = "Execution cancelled by user"
    state = execution_states.get(task_id_str)
    if state is None:
        state = new_execution_state(task_id_str, status_value=TaskStatus.cancelled.value)
        state["_node_map"] = build_workflow_node_map(task.workflow_json)
        execution_states[task_id_str] = state

    state["status"] = TaskStatus.cancelled.value
    state["current_node_id"] = ""
    state["current_node_title"] = ""
    state["current_node_class_type"] = ""
    state["error_message"] = ""
    state["updated_at"] = now_iso()
    append_event_log(task_id_str, "执行已取消", "warning")
    if interrupt_error:
        append_event_log(task_id_str, f"ComfyUI 中断请求失败: {interrupt_error}", "warning")
    mark_dirty(task_id_str)

    await set_task_status(task_id=task_id_str, status_value=TaskStatus.cancelled, message=message)
    await broadcast_to_task(task_id_str, {"type": "all_completed", "data": {"status": TaskStatus.cancelled.value}})

    return CancelTaskResponse(task_id=task_id, status=TaskStatus.cancelled.value, message=message)


# ──────────────────────────────────────────────
# WebSocket Endpoint
# ──────────────────────────────────────────────


@ws_router.websocket("/ws/{task_id}")
async def execution_ws(websocket: WebSocket, task_id: str, token: str = ""):
    """
    WebSocket endpoint for execution progress.
    Auth via query param: ws://.../ws/{task_id}?token=<bearer_token>
    Browsers cannot send Authorization headers during WS handshake.
    """
    # Validate token before accepting — no DB query needed, token carries all claims
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        verify_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()

    if task_id not in ws_connections:
        ws_connections[task_id] = set()
    ws_connections[task_id].add(websocket)
    logger.info("WS client connected: task_id=%s total=%d", task_id, len(ws_connections[task_id]))

    ensure_cleanup_worker()
    state_snapshot = execution_states.get(task_id)
    if state_snapshot is None:
        state_snapshot = await load_persisted_state(task_id)
        if state_snapshot is not None:
            execution_states[task_id] = state_snapshot
    if state_snapshot:
        public_state = public_execution_state(state_snapshot)
        if public_state:
            try:
                await websocket.send_json({"type": "state_sync", "data": public_state})
            except Exception:
                logger.debug("Failed to send state_sync: task_id=%s", task_id)

    try:
        while True:
            data = await websocket.receive_text()
            if data:
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        ws_connections.get(task_id, set()).discard(websocket)
        if task_id in ws_connections and not ws_connections[task_id]:
            del ws_connections[task_id]
        logger.info("WS client disconnected: task_id=%s", task_id)
