"""
测试脚本：调用 reserve_ai_accounts_for_channel_openapi 并验证新增的 KOL 链路逻辑

新增 KOL 逻辑回顾：
    - reserve 时为每条 (account, platform) 调 build_long_link + encode_short_link
    - 写入 account_channel_reservations.kol_long_link / kol_short_link
    - 响应里以 link_info[{name, link}] 形式回吐短链

接口：POST {BASE_URL}/api/v1/open-api/accounts/channel-reservations

⚠️ 真的会写库（status=confirmed）。本地或测试环境跑。

环境变量（从 backend/.env 读取，由 app.core.config.settings 提供）：
    ACCOUNT_CHANNEL_API_KEY  必填，请求头 X-API-Key
    ACCOUNT_CHANNEL_OWNER_ID 可选，不传则由服务端兜底；--owner-id 可覆盖
    KOL_LONG_LINK_BASE_URL / SHORT_LINK_ENCODE_API / SHORT_LINK_DISPLAY_HOST
        这三项是 build_long_link / encode_short_link 真正消费的配置；
        本脚本只是验证下游，不直接用。

被测服务的 BASE_URL：
    优先取 --base-url；其次 TEST_RESERVE_BASE_URL 环境变量；最后默认 http://localhost:8000

用法：
    cd backend
    uv run python scripts/test_reserve_ai_accounts.py \
        --base-url http://localhost:8000 \
        --gender female --platform youtube --count 1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.core.config import settings


ENDPOINT = "/api/v1/open-api/accounts/channel-reservations"


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "***"
    return f"{value[:4]}***{value[-2:]}"


def _resolve_base_url(cli_value: str | None) -> str:
    if cli_value:
        return cli_value.rstrip("/")
    env = os.environ.get("TEST_RESERVE_BASE_URL")
    if env:
        return env.rstrip("/")
    return "http://localhost:8000"


def _call_endpoint(base_url: str, body: dict, headers: dict, timeout: float, verify: bool) -> httpx.Response:
    url = base_url + ENDPOINT
    with httpx.Client(timeout=timeout, verify=verify) as client:
        return client.post(url, headers=headers, json=body)


def _print_link_info_summary(payload: dict[str, Any]) -> tuple[int, int]:
    """返回 (有 short link 的条数, 总条数)。"""
    items = payload.get("items") or []
    with_link = 0
    print("\n── KOL 链路检查 ───────────────────────────────────")
    for idx, it in enumerate(items, 1):
        acc_id = it.get("account_id")
        name = it.get("account_name")
        link_info = it.get("link_info") or []
        if link_info:
            with_link += 1
            for li in link_info:
                print(f"  [{idx}] account={acc_id} name={name!r}")
                print(f"      ✓ {li.get('name')}: {li.get('link')}")
        else:
            print(f"  [{idx}] account={acc_id} name={name!r}")
            print(f"      ✗ 没有 link_info（账号可能缺 kol_user_id，或短链 API 失败）")
    print(f"\n  共 {len(items)} 条 reservation，{with_link} 条带 short link")
    return with_link, len(items)


async def _verify_db(account_ids: list[uuid.UUID], platform: str) -> None:
    """从 DB 查这些 reservation，检查 kol_long_link / kol_short_link 是否写入。"""
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.account_channel_reservation import AccountChannelReservation

    if not account_ids:
        return
    print("\n── DB 校验（account_channel_reservations）──────────")
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(AccountChannelReservation)
            .where(AccountChannelReservation.account_id.in_(account_ids))
            .where(AccountChannelReservation.platform == platform)
        )).scalars().all()
        rows_by_account = {r.account_id: r for r in rows}
        for acc_id in account_ids:
            r = rows_by_account.get(acc_id)
            if not r:
                print(f"  account={acc_id} → 未找到 reservation")
                continue
            print(
                f"  account={acc_id} status={r.status} "
                f"long={'✓' if r.kol_long_link else '✗'} "
                f"short={'✓' if r.kol_short_link else '✗'}"
            )
            if r.kol_long_link:
                print(f"      long  = {r.kol_long_link}")
            if r.kol_short_link:
                print(f"      short = {r.kol_short_link}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="被测服务 base url；默认读 TEST_RESERVE_BASE_URL 或 http://localhost:8000")
    parser.add_argument("--gender", default="female", choices=["male", "female", "unisex"])
    parser.add_argument("--platform", default="youtube", choices=["youtube", "tiktok", "instagram"])
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--source", default="openapi")
    parser.add_argument("--owner-id", help="覆盖 settings.account_channel_owner_id；默认走服务端兜底")
    parser.add_argument("--api-key-in-body", action="store_true", help="把 api_key 放在 body 里而不是 X-API-Key header")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--insecure", action="store_true", help="跳过 TLS 校验")
    parser.add_argument("--dry-run", action="store_true", help="只打印 payload，不发请求")
    parser.add_argument("--skip-db-check", action="store_true", help="不查 DB 校验 kol_long_link / kol_short_link")
    args = parser.parse_args()

    api_key = settings.account_channel_api_key
    if not api_key:
        print("[ERROR] settings.account_channel_api_key 为空，检查 .env 的 ACCOUNT_CHANNEL_API_KEY", file=sys.stderr)
        return 2

    owner_id = args.owner_id or settings.account_channel_owner_id or None
    base_url = _resolve_base_url(args.base_url)

    body: dict = {
        "gender": args.gender,
        "platform": args.platform,
        "count": args.count,
        "source": args.source,
    }
    if owner_id:
        body["owner_id"] = owner_id

    headers = {"Content-Type": "application/json"}
    if args.api_key_in_body:
        body["api_key"] = api_key
    else:
        headers["X-API-Key"] = api_key

    masked_headers = {**headers, "X-API-Key": _mask(headers.get("X-API-Key"))} if "X-API-Key" in headers else headers
    masked_body = {**body, "api_key": _mask(body["api_key"])} if "api_key" in body else body

    print("=" * 60)
    print(f"POST {base_url}{ENDPOINT}")
    print("Headers:", json.dumps(masked_headers, ensure_ascii=False))
    print("Body:   ", json.dumps(masked_body, ensure_ascii=False))
    print("KOL 配置：")
    print(f"  KOL_LONG_LINK_BASE_URL = {settings.kol_long_link_base_url}")
    print(f"  SHORT_LINK_ENCODE_API  = {settings.short_link_encode_api}")
    print(f"  SHORT_LINK_DISPLAY_HOST= {settings.short_link_display_host}")
    print("=" * 60)

    if args.dry_run:
        print("[dry-run] 未发起请求。")
        return 0

    try:
        resp = _call_endpoint(base_url, body, headers, args.timeout, not args.insecure)
    except httpx.HTTPError as exc:
        print(f"[ERROR] 请求失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(f"\nStatus: {resp.status_code} {resp.reason_phrase}")
    try:
        payload = resp.json()
    except ValueError:
        print("Response body (non-JSON):")
        print(resp.text)
        return 1 if resp.status_code >= 400 else 0

    print("Response body:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if resp.status_code >= 400:
        return 1

    if not isinstance(payload, dict):
        return 0

    items = payload.get("items") or []
    print(
        f"\n摘要：requested={payload.get('requested_count')} "
        f"returned={payload.get('returned_count')} "
        f"confirmed={payload.get('confirmed_count')} items={len(items)}"
    )

    _print_link_info_summary(payload)

    if not args.skip_db_check and items:
        try:
            account_ids = [uuid.UUID(str(it.get("account_id"))) for it in items if it.get("account_id")]
            asyncio.run(_verify_db(account_ids, args.platform))
        except Exception as exc:
            print(f"\n[WARN] DB 校验失败（可跳过用 --skip-db-check）：{type(exc).__name__}: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
