from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class TokenData:
    """Decoded token payload — no DB lookup needed."""
    username: str
    user_id: uuid.UUID
    is_admin: bool


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(subject: str, user_id: uuid.UUID, is_admin: bool) -> str:
    payload = {
        "sub": subject,
        "uid": str(user_id),
        "adm": is_admin,
        "exp": int(time.time()) + settings.auth_token_expire_minutes * 60,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)

    signature = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_part = _b64url_encode(signature)

    return f"{payload_part}.{sig_part}"


def verify_access_token(token: str) -> TokenData:
    """Verify token signature and expiry, return TokenData (no DB query)."""
    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    payload_part, sig_part = parts
    expected_sig = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(sig_part, _b64url_encode(expected_sig)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc

    exp = int(payload.get("exp", 0))
    if exp < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    uid_raw = payload.get("uid")
    try:
        user_id = uuid.UUID(uid_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token user_id") from exc

    is_admin = bool(payload.get("adm", False))

    return TokenData(username=sub, user_id=user_id, is_admin=is_admin)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenData:
    """
    Validate Bearer token and return TokenData — no DB query.
    Use this as a FastAPI dependency wherever you need the current user.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return verify_access_token(credentials.credentials)


# ---------------------------------------------------------------------------
# Back-compat alias — remove once all callers are migrated
# ---------------------------------------------------------------------------
require_current_user = get_current_user
