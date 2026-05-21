"""Open API 共享签名工具。

抽自 video_publication_service.OpenAPIClient，供其它需要调用 Open API 的服务
（如 kol_service）复用，避免重复实现签名/规范化逻辑。
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timezone
from typing import Any


def value_to_sign_str(value: Any) -> str:
    """将参数值规范序列化为签名字符串（与 Open API 服务端保持一致）。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def generate_signature(params: dict, client_secret: str, timestamp: int) -> str:
    """生成 HMAC-SHA256 签名。

    过滤掉 ``signature`` 字段以及空值，按 key 升序拼接，末尾再追加一次 ``timestamp``，
    用 client_secret 做 HMAC-SHA256。
    """
    filtered = {
        k: v
        for k, v in params.items()
        if k != "signature" and v is not None and v != ""
    }
    param_str = "&".join(
        f"{k}={value_to_sign_str(v)}" for k, v in sorted(filtered.items())
    )
    sign_str = f"{param_str}&timestamp={timestamp}"
    return hmac.new(client_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()


def sign_params(params: dict, client_id: str, client_secret: str) -> dict:
    """为请求参数追加 client_id / timestamp / signature，并返回新 dict。"""
    timestamp = int(datetime.now(timezone.utc).timestamp())
    signature = generate_signature(
        {**params, "client_id": client_id, "timestamp": timestamp},
        client_secret,
        timestamp,
    )
    return {
        **params,
        "client_id": client_id,
        "timestamp": timestamp,
        "signature": signature,
    }
