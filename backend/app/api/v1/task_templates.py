from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenData, get_current_user
from app.db.session import get_db
from app.schemas.task import (
    TaskRead,
    TaskTemplateCreate,
    TaskTemplateCreateTaskRequest,
    TaskTemplateDeleteResponse,
    TaskTemplateListItem,
    TaskTemplateListResponse,
    TaskTemplatePatch,
    TaskTemplateRead,
)
from app.services.template_service import (
    create_task_from_template,
    create_template,
    delete_template,
    get_template_or_404,
    list_templates,
    patch_template,
)

router = APIRouter(prefix="/task-templates", tags=["task-templates"])


@router.post("", response_model=TaskTemplateRead)
async def create_template_api(
    payload: TaskTemplateCreate,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskTemplateRead:
    owner_id = None if current_user.is_admin else current_user.user_id
    template = await create_template(session, payload, owner_id=owner_id)
    return TaskTemplateRead.model_validate(template)


@router.get("", response_model=TaskTemplateListResponse)
async def list_templates_api(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskTemplateListResponse:
    owner_id = None if current_user.is_admin else current_user.user_id
    items, total = await list_templates(session, page=page, page_size=page_size, owner_id=owner_id)
    return TaskTemplateListResponse(
        items=[TaskTemplateListItem.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{template_id}", response_model=TaskTemplateRead)
async def get_template_api(
    template_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskTemplateRead:
    owner_id = None if current_user.is_admin else current_user.user_id
    template = await get_template_or_404(session, template_id, owner_id=owner_id)
    return TaskTemplateRead.model_validate(template)


@router.patch("/{template_id}", response_model=TaskTemplateRead)
async def patch_template_api(
    template_id: UUID,
    payload: TaskTemplatePatch,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskTemplateRead:
    owner_id = None if current_user.is_admin else current_user.user_id
    template = await get_template_or_404(session, template_id, owner_id=owner_id)
    updated = await patch_template(session, template=template, payload=payload)
    return TaskTemplateRead.model_validate(updated)


@router.delete("/{template_id}", response_model=TaskTemplateDeleteResponse)
async def delete_template_api(
    template_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskTemplateDeleteResponse:
    owner_id = None if current_user.is_admin else current_user.user_id
    await delete_template(session, template_id, owner_id=owner_id)
    return TaskTemplateDeleteResponse(id=template_id)


@router.post("/{template_id}/create-task", response_model=TaskRead)
async def create_task_from_template_api(
    template_id: UUID,
    payload: TaskTemplateCreateTaskRequest,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TaskRead:
    owner_id = None if current_user.is_admin else current_user.user_id
    template = await get_template_or_404(session, template_id, owner_id=owner_id)
    task = await create_task_from_template(session, template=template, payload=payload, owner_id=owner_id)
    return TaskRead.model_validate(task)
