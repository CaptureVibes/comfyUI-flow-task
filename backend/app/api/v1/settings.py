from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, require_current_user
from app.db.session import get_db
from app.schemas.settings import (
    ComfyUIPortStatusItem,
    ComfyUIPortsStatusResponse,
    ComfyUISettingsPayload,
    PipelineSettingsPayload,
    SystemSettingsPayload,
)
from app.services.comfyui_settings_service import (
    fetch_ports_runtime_status,
    get_or_create_comfyui_settings,
    normalize_ports,
    normalize_server_ip,
    update_comfyui_settings,
)
from app.services.pipeline_settings_service import get_or_create_pipeline_settings, update_pipeline_settings
from app.services.system_settings_service import get_or_create_system_settings, update_system_settings

router = APIRouter(prefix="/settings", tags=["settings"])


async def _require_admin(
    token: TokenData = Depends(require_current_user),
) -> TokenData:
    if not token.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return token


# ---------------------------------------------------------------------------
# System settings (admin only)
# ---------------------------------------------------------------------------

@router.get("/system", response_model=SystemSettingsPayload)
async def get_system_settings(
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> SystemSettingsPayload:
    row = await get_or_create_system_settings(session)
    return SystemSettingsPayload(
        comfyui_server_ip=row.comfyui_server_ip,
        comfyui_ports=row.comfyui_ports or [],
        evolink_api_key=row.evolink_api_key,
        evolink_api_base_url=row.evolink_api_base_url,
    )


@router.put("/system", response_model=SystemSettingsPayload)
async def put_system_settings(
    payload: SystemSettingsPayload,
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> SystemSettingsPayload:
    try:
        row = await update_system_settings(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SystemSettingsPayload(
        comfyui_server_ip=row.comfyui_server_ip,
        comfyui_ports=row.comfyui_ports or [],
        evolink_api_key=row.evolink_api_key,
        evolink_api_base_url=row.evolink_api_base_url,
    )


# ---------------------------------------------------------------------------
# Pipeline settings (per-user)
# ---------------------------------------------------------------------------

@router.get("/pipeline", response_model=PipelineSettingsPayload)
async def get_pipeline_settings(
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> PipelineSettingsPayload:
    row = await get_or_create_pipeline_settings(session, owner_id=token.user_id)
    return PipelineSettingsPayload(
        understand_model=row.understand_model,
        understand_prompt=row.understand_prompt,
        understand_temperature=row.understand_temperature,
        understand_output_format=row.understand_output_format,
        understand_json_schema=row.understand_json_schema,
        imagegen_model=row.imagegen_model,
        imagegen_prompt=row.imagegen_prompt,
        imagegen_size=row.imagegen_size,
        imagegen_quality=row.imagegen_quality,
        splitting_api_url=row.splitting_api_url,
        face_removing_api_url=row.face_removing_api_url,
        face_removing_score_thresh=row.face_removing_score_thresh,
        face_removing_margin_scale=row.face_removing_margin_scale,
        face_removing_head_top_ratio=row.face_removing_head_top_ratio,
        upscaling_scale=row.upscaling_scale,
    )


@router.put("/pipeline", response_model=PipelineSettingsPayload)
async def put_pipeline_settings(
    payload: PipelineSettingsPayload,
    token: TokenData = Depends(require_current_user),
    session: AsyncSession = Depends(get_db),
) -> PipelineSettingsPayload:
    row = await update_pipeline_settings(session, owner_id=token.user_id, payload=payload)
    return PipelineSettingsPayload(
        understand_model=row.understand_model,
        understand_prompt=row.understand_prompt,
        understand_temperature=row.understand_temperature,
        understand_output_format=row.understand_output_format,
        understand_json_schema=row.understand_json_schema,
        imagegen_model=row.imagegen_model,
        imagegen_prompt=row.imagegen_prompt,
        imagegen_size=row.imagegen_size,
        imagegen_quality=row.imagegen_quality,
        splitting_api_url=row.splitting_api_url,
        face_removing_api_url=row.face_removing_api_url,
        face_removing_score_thresh=row.face_removing_score_thresh,
        face_removing_margin_scale=row.face_removing_margin_scale,
        face_removing_head_top_ratio=row.face_removing_head_top_ratio,
        upscaling_scale=row.upscaling_scale,
    )


# ---------------------------------------------------------------------------
# ComfyUI shortcuts (兼容旧前端调用，读写 system_settings 的 comfyui 字段)
# ---------------------------------------------------------------------------

@router.get("/comfyui", response_model=ComfyUISettingsPayload)
async def get_comfyui_settings(session: AsyncSession = Depends(get_db)) -> ComfyUISettingsPayload:
    config = await get_or_create_comfyui_settings(session)
    return ComfyUISettingsPayload(
        server_ip=normalize_server_ip(config.comfyui_server_ip),
        ports=normalize_ports([int(item) for item in (config.comfyui_ports or [])]),
    )


@router.put("/comfyui", response_model=ComfyUISettingsPayload)
async def put_comfyui_settings(
    payload: ComfyUISettingsPayload,
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> ComfyUISettingsPayload:
    try:
        updated = await update_comfyui_settings(
            session,
            server_ip=payload.server_ip,
            ports=payload.ports,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ComfyUISettingsPayload(
        server_ip=normalize_server_ip(updated.comfyui_server_ip),
        ports=normalize_ports([int(item) for item in (updated.comfyui_ports or [])]),
    )


@router.get("/comfyui/ports/status", response_model=ComfyUIPortsStatusResponse)
async def get_comfyui_port_status(session: AsyncSession = Depends(get_db)) -> ComfyUIPortsStatusResponse:
    server_ip, refreshed_at, items = await fetch_ports_runtime_status(session)
    return ComfyUIPortsStatusResponse(
        server_ip=server_ip,
        refreshed_at=refreshed_at,
        items=[
            ComfyUIPortStatusItem(
                port=item.port,
                base_url=item.base_url,
                reachable=item.reachable,
                level=item.level,
                running_count=item.running_count,
                pending_count=item.pending_count,
                error=item.error,
            )
            for item in items
        ],
    )
