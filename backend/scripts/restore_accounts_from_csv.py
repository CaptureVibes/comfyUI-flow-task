"""
从 CSV 备份回填 accounts 表里被「一键继续」误清的字段。

策略：
- 只对生产现状是「被清空」状态的账号做回填（photo_url IS NULL 或 photo_candidates 为空），
  避免覆盖你后来手动改过 / 新建的账号。
- 不动 publish_*, classification_*, performance_snapshot 等运行时字段——这些可能在
  备份之后已经更新过，回填会造成回退。

用法：
    cd backend
    .venv/bin/python scripts/restore_accounts_from_csv.py            # dry-run 预览
    .venv/bin/python scripts/restore_accounts_from_csv.py --apply    # 真正写入
    .venv/bin/python scripts/restore_accounts_from_csv.py --apply --force
        # --force：忽略「现状已被清空」的判断，强制按 CSV 覆盖（仅 RESTORE_FIELDS 列）
"""
from __future__ import annotations

import asyncio
import csv
import json
import sys
import uuid
from pathlib import Path

# 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.account import Account  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "studio_results_20260430_1804.csv"

# 仅这些字段会被回填；其它列即使 CSV 里有，也不会动。
RESTORE_FIELDS = [
    "photo_url",
    "avatar_url",
    "ai_generation_state",
    "ai_generation_status",
    "ai_generation_error",
    # 这几个在 _persist_states 里只在 generated_* 非空时才写过来——
    # 一键继续清的是 generated_*，但 Account 列上的 name/handle/signature/gender
    # 实际上没被清。回填时只在生产为空时补一下，避免覆盖手动改过的。
    "account_name",
    "account_handle",
    "account_signature",
    "gender",
]

# 这几个字段是 JSON 列，CSV 里是字符串。
JSON_FIELDS = {"ai_generation_state"}


def _parse_value(field: str, raw: str | None):
    if raw is None or raw == "":
        return None
    if field in JSON_FIELDS:
        try:
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"字段 {field} 不是合法 JSON: {exc}") from exc
    return raw


def _needs_restore(acc: Account) -> bool:
    """生产现状判断：photo_url 为空，或 ai_generation_state 里 photo_candidates 为空，视为被清。"""
    if acc.photo_url is None:
        return True
    state = acc.ai_generation_state or {}
    candidates = state.get("photo_candidates") if isinstance(state, dict) else None
    if not candidates:
        return True
    return False


async def main() -> None:
    apply = "--apply" in sys.argv
    force = "--force" in sys.argv

    if not CSV_PATH.exists():
        print(f"CSV 不存在: {CSV_PATH}")
        sys.exit(1)

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"读入 CSV {len(rows)} 行；CSV={CSV_PATH}")
    print(f"模式: {'APPLY' if apply else 'DRY-RUN'}{' + FORCE' if force else ''}")
    print(f"回填字段: {RESTORE_FIELDS}")
    print()

    updated = 0
    skipped_intact = 0
    skipped_csv_empty = 0
    missing = 0
    bad_uuid = 0

    async with SessionLocal() as session:
        for row in rows:
            raw_id = (row.get("id") or "").strip()
            if not raw_id:
                continue
            try:
                aid = uuid.UUID(raw_id)
            except ValueError:
                bad_uuid += 1
                continue

            acc = await session.get(Account, aid)
            if not acc:
                missing += 1
                continue

            if not force and not _needs_restore(acc):
                skipped_intact += 1
                continue

            csv_photo = row.get("photo_url") or ""
            if not csv_photo:
                # CSV 里这行也没有 photo_url，回填没意义
                skipped_csv_empty += 1
                continue

            for col in RESTORE_FIELDS:
                if col not in row:
                    continue
                val = _parse_value(col, row.get(col))
                if val is None:
                    continue
                # name/handle/signature/gender 仅在生产为空时才补，避免回退手改
                if col in {"account_name", "account_handle", "account_signature", "gender"}:
                    if getattr(acc, col):
                        continue
                setattr(acc, col, val)

            updated += 1
            print(f"  恢复 {aid}  name={acc.account_name}  photo_url={(acc.photo_url or '')[:60]}")

        print()
        print(
            f"总览: 待写 {updated}  跳过(已完整) {skipped_intact}  "
            f"跳过(CSV 也空) {skipped_csv_empty}  生产不存在 {missing}  非法uuid {bad_uuid}"
        )

        if apply:
            await session.commit()
            print("已 commit。")
        else:
            await session.rollback()
            print("DRY-RUN，未提交。加 --apply 真正写入。")


if __name__ == "__main__":
    asyncio.run(main())
