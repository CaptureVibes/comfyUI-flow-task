from __future__ import annotations

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import account, comfyui_setting, evolink_setting, generated_image, generated_video, photo, subtask, task, task_template, tiktok_blogger, user, video_ai_template, video_source  # noqa: F401


async def init_db() -> None:
    """
    创建所有表（如果不存在）。
    schema 变更请使用 Alembic 迁移（alembic upgrade head），
    此处仅作初始建表，适用于开发环境快速启动。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _seed_admin()


async def _seed_admin() -> None:
    """如果 users 表为空，则创建初始 admin 账户（用户名和密码来自环境变量）。"""
    from app.core.config import settings
    from app.services.user_service import create_user, list_users

    async with SessionLocal() as session:
        existing = await list_users(session)
        if existing:
            return  # 已有用户，跳过

        await create_user(
            session,
            username=settings.admin_username,
            password=settings.admin_password,
            is_admin=True,
        )
