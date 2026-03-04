from __future__ import annotations

import asyncio
import logging

from app.models.enums import TaskStatus
from app.services.comfyui_service import ComfyEvent, listen_comfyui_ws
from app.services.execution_state import (
    append_event_log,
    broadcast_to_task,
    build_workflow_node_map,
    execution_states,
    format_node_display,
    listener_stop_events,
    listener_tasks,
    mark_dirty,
    now_iso,
    resolve_node_meta,
    set_task_status,
)

logger = logging.getLogger("app.execution")


async def run_comfyui_listener(
    *,
    client_id: str,
    task_id: str,
    ws_base_url: str,
    prompt_ids: set[str],
    stop_event: asyncio.Event | None = None,
    connected_event: asyncio.Event | None = None,
) -> None:
    """后台任务：连接 ComfyUI WS，接收事件，广播给前端。"""
    runtime_stop_event = stop_event or asyncio.Event()
    completed_prompts: set[str] = set()
    has_error = False
    last_error_message = ""
    finalized = False

    async def finalize_if_done() -> None:
        nonlocal finalized
        if finalized:
            return
        if not prompt_ids or completed_prompts < prompt_ids:
            return
        finalized = True
        logger.info("All prompts completed for task %s", task_id)
        final_status = TaskStatus.fail if has_error else TaskStatus.success
        final_message = last_error_message if has_error else "ComfyUI execution completed"
        logger.info(
            "Finalizing task: task_id=%s final_status=%s completed_prompt_ids=%s",
            task_id,
            final_status.value,
            sorted(completed_prompts),
        )
        state = execution_states.get(task_id)
        if state is not None:
            state["status"] = final_status.value
            state["current_node_id"] = ""
            state["current_node_title"] = ""
            state["current_node_class_type"] = ""
            state["error_message"] = last_error_message if has_error else ""
            state["updated_at"] = now_iso()
        if has_error:
            append_event_log(task_id, "执行结束，存在错误", "error")
        else:
            append_event_log(task_id, "所有节点执行完成 ✓", "success")
        await set_task_status(task_id=task_id, status_value=final_status, message=final_message)
        await broadcast_to_task(task_id, {"type": "all_completed", "data": {"status": final_status.value}})
        runtime_stop_event.set()

    async def on_event(event: ComfyEvent) -> None:
        nonlocal has_error, last_error_message
        if runtime_stop_event.is_set():
            return
        logger.info(
            "Execution event relayed: task_id=%s type=%s prompt_id=%s node_id=%s",
            task_id, event.event_type, event.prompt_id, event.node_id,
        )
        message: dict = {"type": event.event_type, "prompt_id": event.prompt_id, "data": {}}
        node_id = str(event.node_id) if event.node_id is not None else None
        node_title, node_class_type = resolve_node_meta(task_id, node_id)
        node_display = format_node_display(node_id, node_title, node_class_type)

        if event.event_type == "execution_start":
            if event.prompt_id:
                prompt_ids.add(event.prompt_id)
                state = execution_states.get(task_id)
                if state is not None:
                    state["prompt_id"] = event.prompt_id
                    state["prompt_ids"] = sorted(prompt_ids)
                    state["completed_node_count"] = 0
                    state["updated_at"] = now_iso()
                    mark_dirty(task_id)
            return

        if event.event_type == "executing":
            message["data"].update({"node_id": node_id, "node_title": node_title, "node_class_type": node_class_type})
            state = execution_states.get(task_id)
            if state is not None:
                state["current_node_id"] = node_id or ""
                state["current_node_title"] = node_title
                state["current_node_class_type"] = node_class_type
                state["updated_at"] = now_iso()
            if node_id:
                append_event_log(task_id, f"执行节点: {node_display}", "info")
            if event.node_id is None and event.prompt_id:
                completed_prompts.add(event.prompt_id)

        elif event.event_type == "progress":
            message["data"].update({
                "node_id": node_id, "node_title": node_title, "node_class_type": node_class_type,
                "value": event.progress_value, "max": event.progress_max,
            })
            state = execution_states.get(task_id)
            if state is not None:
                state["progress"] = {
                    "node_id": node_id or "", "node_title": node_title, "node_class_type": node_class_type,
                    "value": int(event.progress_value or 0), "max": int(event.progress_max or 0),
                }
                state["updated_at"] = now_iso()

        elif event.event_type == "executed":
            message["data"].update({"node_id": node_id, "node_title": node_title, "node_class_type": node_class_type})
            if node_id:
                state = execution_states.get(task_id)
                if state is not None:
                    state["completed_node_count"] = int(state.get("completed_node_count") or 0) + 1
                    state["updated_at"] = now_iso()
                append_event_log(task_id, f"节点 {node_display} 执行完毕", "success")

        elif event.event_type == "execution_error":
            has_error = True
            last_error_message = event.extra.get("exception_message") or "ComfyUI execution_error"
            message["data"].update({
                "node_id": node_id, "node_title": node_title, "node_class_type": node_class_type,
                "exception_message": event.extra.get("exception_message"),
            })
            append_event_log(task_id, f"节点 {node_display} 错误: {last_error_message}", "error")
            state = execution_states.get(task_id)
            if state is not None:
                state["status"] = TaskStatus.fail.value
                state["error_message"] = last_error_message
                state["updated_at"] = now_iso()
            if event.prompt_id:
                completed_prompts.add(event.prompt_id)

        elif event.event_type == "execution_cached":
            nodes = event.extra.get("nodes", [])
            if not isinstance(nodes, list):
                nodes = []
            node_infos = []
            for raw_node in nodes:
                cached_node_id = str(raw_node)
                cached_title, cached_class_type = resolve_node_meta(task_id, cached_node_id)
                node_infos.append({"node_id": cached_node_id, "node_title": cached_title, "node_class_type": cached_class_type})
            message["data"]["nodes"] = [info["node_id"] for info in node_infos]
            message["data"]["node_infos"] = node_infos
            if node_infos:
                labels = [format_node_display(info["node_id"], info["node_title"], info["node_class_type"]) for info in node_infos]
                append_event_log(task_id, f"缓存节点: {', '.join(labels)}", "info")
                state = execution_states.get(task_id)
                if state is not None:
                    state["completed_node_count"] = int(state.get("completed_node_count") or 0) + len(node_infos)
                    state["updated_at"] = now_iso()

        state = execution_states.get(task_id)
        if state is not None:
            state["completed_prompt_ids"] = sorted(completed_prompts)
            state["updated_at"] = now_iso()
            mark_dirty(task_id)

        await broadcast_to_task(task_id, message)
        await finalize_if_done()

    try:
        await listen_comfyui_ws(
            client_id,
            ws_base_url=ws_base_url,
            on_event=on_event,
            stop_event=runtime_stop_event,
            prompt_ids=prompt_ids,
            connected_event=connected_event,
        )
        await finalize_if_done()
        if not runtime_stop_event.is_set():
            message_str = "Lost connection to ComfyUI before completion"
            state = execution_states.get(task_id)
            if state is not None:
                state["status"] = TaskStatus.fail.value
                state["error_message"] = message_str
                state["updated_at"] = now_iso()
            append_event_log(task_id, message_str, "error")
            await set_task_status(task_id=task_id, status_value=TaskStatus.fail, message=message_str)
            await broadcast_to_task(task_id, {"type": "listener_error", "data": {"message": message_str}})
    except Exception:
        logger.exception("ComfyUI listener failed for task %s", task_id)
        state = execution_states.get(task_id)
        if state is not None:
            state["status"] = TaskStatus.fail.value
            state["error_message"] = "Lost connection to ComfyUI"
            state["updated_at"] = now_iso()
        append_event_log(task_id, "Lost connection to ComfyUI", "error")
        await set_task_status(task_id=task_id, status_value=TaskStatus.fail, message="Lost connection to ComfyUI")
        await broadcast_to_task(task_id, {"type": "listener_error", "data": {"message": "Lost connection to ComfyUI"}})
    finally:
        current_stop_event = listener_stop_events.get(task_id)
        if current_stop_event is runtime_stop_event:
            listener_stop_events.pop(task_id, None)
        listener_task = listener_tasks.get(task_id)
        if listener_task is asyncio.current_task():
            listener_tasks.pop(task_id, None)
