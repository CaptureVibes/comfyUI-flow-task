"""External vendor 回调端点（无 JWT 鉴权，靠 X-API-Key + DB 校验）。

POST /api/v1/external/supplement-callback
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from app.schemas.external_supplement import (
    SupplementCallbackBody,
    SupplementCallbackResponse,
)
from app.services.external_supplement_service import handle_supplement_callback

logger = logging.getLogger("app.external_supplement")

router = APIRouter(prefix="/external", tags=["external-supplement"])


@router.post("/supplement-callback", response_model=SupplementCallbackResponse)
async def supplement_callback(
    body: SupplementCallbackBody,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> SupplementCallbackResponse:
    """vendor 回调入口：按 request_id + X-API-Key 校验，再交给 service 入库。"""
    logger.info(
        "[ext_supp][callback] RAW REQUEST: x_api_key_present=%s request_id=%s mode=%s final=%s items=%d total_videos=%d body=%s",
        bool(x_api_key),
        body.request_id,
        body.mode,
        body.final,
        len(body.items),
        sum(len(it.videos) for it in body.items),
        body.model_dump_json()[:5000],
    )
    if not x_api_key:
        raise HTTPException(status_code=401, detail="missing X-API-Key")

    result = await handle_supplement_callback(
        request_id=body.request_id,
        mode=body.mode,
        final=body.final,
        items=body.items,
        header_secret=x_api_key,
    )
    http_status = result.pop("http_status", 200)
    if http_status == 404:
        raise HTTPException(status_code=404, detail=result.get("message") or "not found")
    if http_status == 401:
        raise HTTPException(status_code=401, detail=result.get("message") or "unauthorized")
    return SupplementCallbackResponse(**result)
