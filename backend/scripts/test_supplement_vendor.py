"""StyleDNA 视频补充服务 outbound 联调脚本（参数全部硬编码）。

直接 `python scripts/test_supplement_vendor.py` 就跑。

流程：
1. 调健康检查 /healthz
2. 构造 outbound payload
3. POST 到 vendor /supplement-requests
4. 打印响应

callback 域名 echoootx.top 需要 vendor 先把它加进 SUPPLEMENT_CALLBACK_ALLOWED_HOSTS。
"""
from __future__ import annotations

import json
import sys
import uuid

import httpx


# ── 硬编码参数 ─────────────────────────────────────────────────────────────────

VENDOR_BASE = "https://ws.alvinsclub.ai/supplement-vendor"
BEARER_TOKEN = "c8d38ea56007e1cddd343a478ce7d7cb3898c0ec6b77678f77194e2085f8ac19"

CALLBACK_URL = "http://echoootx.top/api/v1/external/supplement-callback"
CALLBACK_SECRET = "ec_cb_test_key_001"

HANDLE = "khaby.lame"
TARGET_VIDEO_COUNT = 2
MODE = "auto"  # "auto" 或 "exclusive"

FILTERS: dict = {
    # "min_view_count": 100000,
    # "published_after": "2025-01-01",
    # "max_duration_seconds": 60,
}

EXISTING_VIDEO_URLS: list[str] = []


def check_health() -> None:
    url = f"{VENDOR_BASE}/healthz"
    print(f"== Health check ==\nGET {url}")
    try:
        r = httpx.get(url, timeout=10.0)
        print(f"HTTP {r.status_code}: {r.text}\n")
    except Exception as exc:
        print(f"Health check failed: {exc}\n")


def submit_request() -> tuple[int, dict | str]:
    url = f"{VENDOR_BASE}/supplement-requests"
    request_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())

    payload = {
        "request_id": request_id,
        "callback_url": CALLBACK_URL,
        "callback_auth": {
            "header_name": "X-API-Key",
            "header_value": CALLBACK_SECRET,
        },
        "mode": MODE,
        "platform": "tiktok",
        "target_video_count": TARGET_VIDEO_COUNT,
        "filters": FILTERS,
        "items": [
            {
                "account_id": account_id,
                "blogger": {
                    "handle": HANDLE,
                    "profile_url": f"https://www.tiktok.com/@{HANDLE}",
                },
                "existing_video_urls": EXISTING_VIDEO_URLS,
            }
        ],
    }

    print(f"== Outbound request ==\nPOST {url}")
    print(f"request_id: {request_id}")
    print(f"account_id: {account_id}")
    print(f"handle:     {HANDLE}, target: {TARGET_VIDEO_COUNT}, mode: {MODE}")
    print(f"callback:   {CALLBACK_URL}")
    print(f"secret:     {CALLBACK_SECRET}")
    print("\nPayload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(url, headers=headers, json=payload, timeout=15.0)
    except httpx.RequestError as exc:
        print(f"✗ Request error: {exc}")
        return -1, str(exc)

    print(f"== Response ==\nHTTP {r.status_code}")
    try:
        body = r.json()
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return r.status_code, body
    except Exception:
        print(r.text)
        return r.status_code, r.text


def main() -> None:
    check_health()
    status, body = submit_request()
    print()
    if status == 200 and isinstance(body, dict) and body.get("status") == "accepted":
        print("✓ Vendor accepted the request")
        print(f"  message: {body.get('message')}")
        print(f"  accepted_items: {body.get('accepted_items')}")
        print(f"  request_id: {body.get('request_id')}")
        print(f"\n回调会发到 {CALLBACK_URL}（Header: X-API-Key: {CALLBACK_SECRET}）")
        sys.exit(0)
    else:
        print("✗ 请求未被接受")
        sys.exit(1)


if __name__ == "__main__":
    main()
