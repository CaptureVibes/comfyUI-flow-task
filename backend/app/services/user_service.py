from __future__ import annotations

import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")
    return user


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
    is_admin: bool = False,
) -> User:
    existing = await get_user_by_username(session, username)
    if existing is not None:
        raise ValidationError(f"Username '{username}' already exists")
    if len(password) < 6:
        raise ValidationError("Password must be at least 6 characters")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_admin=is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def change_password(
    session: AsyncSession,
    user_id: uuid.UUID,
    old_password: str,
    new_password: str,
) -> User:
    user = await get_user_by_id(session, user_id)
    if not verify_password(old_password, user.hashed_password):
        raise ValidationError("Current password is incorrect")
    if len(new_password) < 6:
        raise ValidationError("New password must be at least 6 characters")

    user.hashed_password = hash_password(new_password)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: uuid.UUID, current_user_id: uuid.UUID) -> None:
    user = await get_user_by_id(session, user_id)
    if user.id == current_user_id:
        raise ValidationError("Cannot delete your own account")
    await session.delete(user)
    await session.commit()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(session, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def update_profile(
    session: AsyncSession,
    user_id: uuid.UUID,
    display_name: str | None = None,
    bio: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Update current user's profile fields."""
    user = await get_user_by_id(session, user_id)
    if display_name is not None:
        user.display_name = display_name
    if bio is not None:
        user.bio = bio
    if avatar_url is not None:
        user.avatar_url = avatar_url
    await session.commit()
    await session.refresh(user)
    return user
