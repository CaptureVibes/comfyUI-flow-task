from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenData, create_access_token, get_current_user
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.schemas.user import (
    UserChangePassword,
    UserCreate,
    UserDeleteResponse,
    UserProfile,
    UserProfileUpdate,
    UserListResponse,
    UserRead,
)
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Login (public) ──────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login_api(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> LoginResponse:
    user = await user_service.authenticate_user(session, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    return LoginResponse(
        access_token=create_access_token(user.username, user_id=user.id, is_admin=user.is_admin),
        expires_in=settings.auth_token_expire_minutes * 60,
        username=user.username,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=MeResponse)
async def me_api(current_user: TokenData = Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=current_user.username, is_admin=current_user.is_admin)


# ── User management (admin only) ─────────────────────────────────────────────

def _require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user


@router.get("/users", response_model=UserListResponse)
async def list_users_api(
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> UserListResponse:
    users = await user_service.list_users(session)
    return UserListResponse(items=[UserRead.model_validate(u) for u in users], total=len(users))


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_api(
    payload: UserCreate,
    _: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await user_service.create_user(
        session, username=payload.username, password=payload.password, is_admin=payload.is_admin
    )
    return UserRead.model_validate(user)


@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
async def delete_user_api(
    user_id: uuid.UUID,
    current_user: TokenData = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> UserDeleteResponse:
    await user_service.delete_user(session, user_id=user_id, current_user_id=current_user.user_id)
    return UserDeleteResponse()


# ── Change own password (any authenticated user) ─────────────────────────────

@router.post("/change-password", response_model=MeResponse)
async def change_password_api(
    payload: UserChangePassword,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MeResponse:
    await user_service.change_password(
        session, user_id=current_user.user_id, old_password=payload.old_password, new_password=payload.new_password
    )
    return MeResponse(username=current_user.username, is_admin=current_user.is_admin)


# ── User profile (any authenticated user) ─────────────────────────────────────

@router.get("/profile", response_model=UserProfile)
async def get_profile_api(
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserProfile:
    """Get current user's full profile."""
    user = await user_service.get_user_by_id(session, current_user.user_id)
    return UserProfile.model_validate(user)


@router.patch("/profile", response_model=UserProfile)
async def update_profile_api(
    payload: UserProfileUpdate,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserProfile:
    """Update current user's profile fields."""
    user = await user_service.update_profile(
        session,
        user_id=current_user.user_id,
        display_name=payload.display_name,
        bio=payload.bio,
        avatar_url=payload.avatar_url,
    )
    return UserProfile.model_validate(user)
