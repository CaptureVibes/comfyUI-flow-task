from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, require_current_user
from app.db.session import get_db
from app.schemas.settings import ComfyUIPortStatusItem, ComfyUIPortsStatusResponse, ComfyUISettingsPayload, EvoLinkSettingsPayload
from app.services.comfyui_settings_service import (
    fetch_ports_runtime_status,
    get_or_create_comfyui_settings,
    normalize_ports,
    normalize_server_ip,
    update_comfyui_settings,
)
from app.services.evolink_settings_service import get_or_create_evolink_settings, update_evolink_settings

router = APIRouter(prefix="/settings", tags=["settings"])


async def _require_admin(
    token: TokenData = Depends(require_current_user),
) -> TokenData:
    if not token.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return token


@router.get("/comfyui", response_model=ComfyUISettingsPayload)
async def get_comfyui_settings(session: AsyncSession = Depends(get_db)) -> ComfyUISettingsPayload:
    config = await get_or_create_comfyui_settings(session)
    return ComfyUISettingsPayload(
        server_ip=normalize_server_ip(config.server_ip),
        ports=normalize_ports([int(item) for item in (config.ports or [])]),
    )


@router.put("/comfyui", response_model=ComfyUISettingsPayload)
async def put_comfyui_settings(
    payload: ComfyUISettingsPayload,
    _: str = Depends(_require_admin),
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
        server_ip=normalize_server_ip(updated.server_ip),
        ports=normalize_ports([int(item) for item in (updated.ports or [])]),
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


def _row_to_evolink_payload(row) -> EvoLinkSettingsPayload:
    return EvoLinkSettingsPayload(
        api_key=row.api_key,
        api_base_url=row.api_base_url,
        understand_model=row.understand_model,
        understand_prompt=row.understand_prompt,
        understand_temperature=row.understand_temperature,
        understand_output_format=row.understand_output_format,
        understand_json_schema=row.understand_json_schema,
    )


@router.get("/evolink", response_model=EvoLinkSettingsPayload)
async def get_evolink_settings(session: AsyncSession = Depends(get_db)) -> EvoLinkSettingsPayload:
    row = await get_or_create_evolink_settings(session)
    return _row_to_evolink_payload(row)


@router.put("/evolink", response_model=EvoLinkSettingsPayload)
async def put_evolink_settings(
    payload: EvoLinkSettingsPayload,
    _: str = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> EvoLinkSettingsPayload:
    row = await update_evolink_settings(session, payload)
    return _row_to_evolink_payload(row)
