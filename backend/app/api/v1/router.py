from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import accounts, auth, callbacks, execution, settings, subtasks, task_templates, tasks, uploads, video_ai_templates, video_sources
from app.core.security import get_current_user

api_router = APIRouter(prefix="/api/v1")

# ── Public routes (no auth required) ──────────────────────────────────────────
api_router.include_router(auth.router)       # /auth/login is public
api_router.include_router(callbacks.router)  # internal webhook callbacks

# ── Protected routes (Bearer token required) ──────────────────────────────────
_auth_dep = [Depends(get_current_user)]

api_router.include_router(tasks.router, dependencies=_auth_dep)
api_router.include_router(subtasks.router, dependencies=_auth_dep)
api_router.include_router(task_templates.router, dependencies=_auth_dep)
api_router.include_router(uploads.router, dependencies=_auth_dep)
api_router.include_router(execution.router, dependencies=_auth_dep)
# WebSocket routes use query-param token auth (browsers can't send Authorization headers)
api_router.include_router(execution.ws_router)
api_router.include_router(settings.router, dependencies=_auth_dep)
api_router.include_router(video_sources.router, dependencies=_auth_dep)
api_router.include_router(video_ai_templates.router, dependencies=_auth_dep)
api_router.include_router(accounts.router, dependencies=_auth_dep)
