"""把 docs/channel_kol.csv 里的 kol_user_id 回填到对应 Account，并按 reservation 的
platform 生成 KOL 长/短链写回 reservation 行。

CSV 列顺序：``channel_name, channel_id, kol_user_id``（后续空列忽略）。

逻辑：
1. 按 ``channel_id`` 在 ``account_channel_reservations`` 拿到全部匹配的 reservation
   （可能跨多个 platform）。
2. 把 ``accounts.kol_user_id`` 写成 CSV 里的值（已存在则覆盖）。
3. 对每条 reservation：``build_long_link(kol_user_id, reservation.platform)`` →
   ``encode_short_link``，结果写回 ``reservation.kol_long_link`` /
   ``reservation.kol_short_link``。已经有 short 链的 reservation 跳过外部 API 调用。

默认 dry run；加 ``--apply`` 才真正 commit。
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import select

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.account_channel_reservation import AccountChannelReservation  # noqa: E402
from app.services.kol_service import build_long_link, encode_short_link  # noqa: E402

logger = logging.getLogger("backfill_kol_user_id")
_DEFAULT_CSV = _BACKEND_DIR.parent / "docs" / "channel_kol.csv"


class CsvRow(NamedTuple):
    channel_name: str
    channel_id: str
    kol_user_id: str
    line_no: int


def load_csv(path: Path) -> list[CsvRow]:
    rows: list[CsvRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for idx, raw in enumerate(csv.reader(fh), start=1):
            if not raw or all(not (c or "").strip() for c in raw):
                continue
            cells = [c.strip() for c in raw]
            if len(cells) < 3:
                logger.warning("line %d: 列数不足，跳过 raw=%s", idx, raw)
                continue
            channel_name, channel_id, kol_user_id, *_ = cells
            if not channel_id or not kol_user_id:
                logger.warning(
                    "line %d: channel_id 或 kol_user_id 为空，跳过 (%s, %s, %s)",
                    idx, channel_name, channel_id, kol_user_id,
                )
                continue
            rows.append(CsvRow(channel_name, channel_id, kol_user_id, idx))
    return rows


async def backfill(csv_path: Path, apply: bool) -> dict[str, int]:
    rows = load_csv(csv_path)
    logger.info("CSV %s 解析出 %d 行有效记录", csv_path, len(rows))
    stats = {
        "total": len(rows),
        "not_found": 0,
        "accounts_updated": 0,
        "reservations_updated": 0,
        "short_link_failed": 0,
        "short_link_skipped_existing": 0,
    }

    async with SessionLocal() as session:
        for row in rows:
            reservations = (
                await session.execute(
                    select(AccountChannelReservation)
                    .where(AccountChannelReservation.channel_id == row.channel_id)
                )
            ).scalars().all()
            if not reservations:
                stats["not_found"] += 1
                logger.info(
                    "[NOT_FOUND] line=%d channel_id=%s channel_name=%s",
                    row.line_no, row.channel_id, row.channel_name,
                )
                continue

            # 写 account.kol_user_id（一个 account 只写一次即可，即便有多条 reservation）
            account_ids = {r.account_id for r in reservations}
            for account_id in account_ids:
                account = await session.scalar(select(Account).where(Account.id == account_id))
                if account is None:
                    logger.warning(
                        "[NO_ACCOUNT] line=%d channel_id=%s reservation 存在但 account_id=%s 找不到",
                        row.line_no, row.channel_id, account_id,
                    )
                    continue
                account.kol_user_id = row.kol_user_id
                stats["accounts_updated"] += 1

            # 写每条 reservation 的 kol_long_link / kol_short_link
            for reservation in reservations:
                if reservation.kol_short_link:
                    stats["short_link_skipped_existing"] += 1
                    logger.info(
                        "[SKIP_EXISTING] line=%d reservation_id=%s platform=%s 已有 short_link",
                        row.line_no, reservation.id, reservation.platform,
                    )
                    continue
                long_link = build_long_link(row.kol_user_id, reservation.platform)
                try:
                    encoded = await encode_short_link(long_link)
                    short_link = encoded.get("short") or None
                except Exception:
                    stats["short_link_failed"] += 1
                    logger.exception(
                        "[ENCODE_FAIL] line=%d reservation_id=%s platform=%s long=%s",
                        row.line_no, reservation.id, reservation.platform, long_link,
                    )
                    reservation.kol_long_link = long_link
                    reservation.kol_short_link = None
                    continue
                reservation.kol_long_link = long_link
                reservation.kol_short_link = short_link
                stats["reservations_updated"] += 1
                logger.info(
                    "[UPDATE] line=%d reservation_id=%s platform=%s short_link=%s",
                    row.line_no, reservation.id, reservation.platform, short_link,
                )

        if apply:
            await session.commit()
            logger.info(
                "已提交：accounts=%d reservations=%d",
                stats["accounts_updated"], stats["reservations_updated"],
            )
        else:
            await session.rollback()
            logger.info("DRY RUN（默认）：本次未写库；如需写库追加 --apply")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill accounts.kol_user_id + reservations.kol_long/short_link from CSV")
    parser.add_argument("--csv", default=str(_DEFAULT_CSV), help="CSV 路径（默认 docs/channel_kol.csv）")
    parser.add_argument("--apply", action="store_true", help="真正写库；不传则 dry run")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV 不存在：{csv_path}")

    stats = asyncio.run(backfill(csv_path, apply=args.apply))
    print("=" * 60)
    print(f"CSV total rows                  : {stats['total']}")
    print(f"  → not_found                   : {stats['not_found']}")
    print(f"  → accounts_updated            : {stats['accounts_updated']}")
    print(f"  → reservations_updated        : {stats['reservations_updated']}")
    print(f"  → short_link_skipped_existing : {stats['short_link_skipped_existing']}")
    print(f"  → short_link_failed           : {stats['short_link_failed']}")
    print(f"apply={args.apply}")


if __name__ == "__main__":
    main()
