"""
最简单的外部 AI 博主频道接口测试脚本。

用法：
1. 手动填写下面的 BASE_URL / API_KEY / OWNER_ID。
2. 按需要填写 CONFIRM_* 和 BIND_*。
3. 修改 ACTION 为 "reserve" / "confirm" / "bind"。
4. 执行：
   cd backend
   uv run python scripts/test_account_channel_openapi.py
"""
from __future__ import annotations

import json

import httpx


BASE_URL = "http://127.0.0.1:8000/api/v1"
API_KEY = ""  # 填入 ACCOUNT_CHANNEL_API_KEY
OWNER_ID = "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c"

# reserve 参数
RESERVE_GENDER = "female"  # male / female / unisex
RESERVE_PLATFORM = "tiktok"  # youtube / tiktok / instagram
RESERVE_COUNT = 1
RESERVE_SOURCE = "openapi"

# confirm 参数
CONFIRM_ACCOUNT_ID = "c673e254-5eae-4b87-a1d3-b247258476b4"
CONFIRM_PLATFORM = "tiktok"  # youtube / tiktok / instagram

# bind 参数
BIND_ACCOUNT_ID = "c673e254-5eae-4b87-a1d3-b247258476b4"
BIND_PLATFORM = "tiktok"  # youtube / tiktok / instagram
BIND_CHANNEL_ID = "test"
BIND_CHANNEL_NAME = "test"
BIND_USERNAME = "@test"
BIND_CHANNEL_SOURCE = "openapi"

# 改这里选择要测试的接口：reserve / confirm / bind
ACTION = "reserve"


def post(path: str, payload: dict) -> None:
    url = f"{BASE_URL.rstrip('/')}{path}"
    headers = {"X-API-Key": API_KEY}
    print("POST", url)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        resp = client.post(url, json=payload, headers=headers)
    print("HTTP", resp.status_code)
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(resp.text)


def reserve() -> None:
    post(
        "/open-api/accounts/channel-reservations",
        {
            "owner_id": OWNER_ID,
            "gender": RESERVE_GENDER,
            "platform": RESERVE_PLATFORM,
            "count": RESERVE_COUNT,
            "source": RESERVE_SOURCE,
        },
    )


def confirm() -> None:
    post(
        "/open-api/accounts/channel-reservations/confirm",
        {
            "owner_id": OWNER_ID,
            "account_id": CONFIRM_ACCOUNT_ID,
            "platform": CONFIRM_PLATFORM,
        },
    )


def bind() -> None:
    post(
        f"/open-api/accounts/{BIND_ACCOUNT_ID}/channel-bindings",
        {
            "owner_id": OWNER_ID,
            "platform": BIND_PLATFORM,
            "channel_id": BIND_CHANNEL_ID,
            "channel_name": BIND_CHANNEL_NAME,
            "username": BIND_USERNAME,
            "channel_source": BIND_CHANNEL_SOURCE,
        },
    )


if __name__ == "__main__":
    if ACTION == "reserve":
        reserve()
    elif ACTION == "confirm":
        confirm()
    elif ACTION == "bind":
        bind()
    else:
        raise SystemExit(f"Unknown ACTION: {ACTION}")
