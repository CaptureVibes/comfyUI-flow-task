from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.db.init_db import init_db
from app.services.task_scheduler_service import start_task_scheduler, stop_task_scheduler
from app.services.video_ai_service import start_video_ai_queue_processor, stop_video_ai_queue_processor
from app.services.ai_account_service import start_ai_account_queue_processor, stop_ai_account_queue_processor, recover_stuck_accounts_on_startup
from app.services.video_publication_service import start_video_publication_poller, stop_video_publication_poller
from app.services.video_stats_collector import stop_video_stats_collector
from app.services.account_publish_scheduler import start_account_publish_scheduler, stop_account_publish_scheduler
from app.services.video_task_service import (
    recover_stuck_video_scoring_on_startup,
    start_video_scoring_queue_processor,
    stop_video_scoring_queue_processor,
)

setup_logging(settings.log_level, settings.log_dir)
logger = logging.getLogger("app")

app = FastAPI(title="Task Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    path_with_query = request.url.path
    if request.url.query:
        path_with_query = f"{path_with_query}?{request.url.query}"

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "[%s] %s %s -> 500 (%.2fms)",
            request_id,
            request.method,
            path_with_query,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] %s %s -> %s (%.2fms)",
        request_id,
        request.method,
        path_with_query,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    # 允许任意来源通过 iframe 嵌入本站
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response


@app.on_event("startup")
async def startup_event() -> None:
    if len(settings.auth_secret) < 32:
        raise RuntimeError("AUTH_SECRET must be at least 32 characters long. Set it via environment variable.")
    logger.info("Starting API with env=%s db=%s", settings.app_env, settings.database_url)
    if settings.auto_create_tables:
        await init_db()
    start_task_scheduler()
    start_video_ai_queue_processor()
    start_ai_account_queue_processor()
    await recover_stuck_accounts_on_startup()
    start_video_scoring_queue_processor()
    await recover_stuck_video_scoring_on_startup()
    start_video_publication_poller()
    # start_video_stats_collector()  # 暂停：每日统计定时任务
    start_account_publish_scheduler()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await stop_task_scheduler()
    await stop_video_ai_queue_processor()
    await stop_ai_account_queue_processor()
    await stop_video_scoring_queue_processor()
    await stop_video_publication_poller()
    await stop_video_stats_collector()
    await stop_account_publish_scheduler()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(api_router)
