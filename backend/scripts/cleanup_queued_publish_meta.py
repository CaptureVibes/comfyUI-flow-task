"""
清洗「库存」（sub_task.status='queued'）中视频的 publish_meta 标题 / 描述：

- 标题：剥掉旧前缀 `👇 👀 Get my exact look here 👀 👇` / 旧后缀
  `Get my exact look here 👀 👇`，重新按当前规则拼新前缀
  `👆Outfit linked in bio`（仅对 product_code_mode='with_code' 账号）。
- 描述：去掉旧版「Love this look? Search code XXX on Alvin's Club…」引流行，
  在最前面补一段
  `You can find this outfit through the link in my bio💗`
  （仅 with_code 账号）。

without_code 账号的 publish_meta 不做处理（它本来就没有这些前缀 / 引流行）。

幂等：检测到已是新格式 / 已含 bio 头时跳过，可安全多次执行。

用法：
    cd backend
    uv run python scripts/cleanup_queued_publish_meta.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.video_task import VideoSubTask, VideoTask
from app.services.publish_meta_service import (
    _BIO_LINK_DESC_HEADER,
    _PRODUCT_CODE_TITLE_LEGACY_PREFIX,
    _PRODUCT_CODE_TITLE_LEGACY_SUFFIX,
    _PRODUCT_CODE_TITLE_PREFIX,
    _build_product_code_title,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cleanup_queued_publish_meta")


_OLD_CODE_LINE_PREFIX = "Love this look?"
_OLD_CODE_LINE_MARK = "Search code"


def _clean_description(desc: str) -> str:
    """删除旧版「Love this look? Search code XXX」引流行，并在最前补 bio 头。"""
    if desc is None:
        desc = ""
    out_lines: list[str] = []
    for line in desc.split("\n"):
        s = line.strip()
        if s.startswith(_OLD_CODE_LINE_PREFIX) and _OLD_CODE_LINE_MARK in s:
            continue
        out_lines.append(line)
    cleaned = "\n".join(out_lines)
    # 折叠 3+ 个连续空行到 2 个
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    cleaned = cleaned.strip()

    if cleaned.startswith(_BIO_LINK_DESC_HEADER):
        # 已是新格式
        return cleaned
    return f"{_BIO_LINK_DESC_HEADER}\n\n{cleaned}" if cleaned else _BIO_LINK_DESC_HEADER


def _needs_title_rewrite(title: str) -> bool:
    if title is None:
        return False
    if _PRODUCT_CODE_TITLE_LEGACY_PREFIX in title:
        return True
    if title.endswith(_PRODUCT_CODE_TITLE_LEGACY_SUFFIX):
        return True
    if not title.startswith(_PRODUCT_CODE_TITLE_PREFIX):
        # 没有任何前缀 / 后缀但又是 with_code 账号——补上新前缀
        return True
    return False


def _needs_desc_rewrite(desc: str) -> bool:
    if not desc:
        return True
    if _OLD_CODE_LINE_PREFIX in desc and _OLD_CODE_LINE_MARK in desc:
        return True
    if not desc.lstrip().startswith(_BIO_LINK_DESC_HEADER):
        return True
    return False


async def cleanup(dry_run: bool) -> dict:
    title_changed = 0
    desc_changed = 0
    skipped_no_publish_meta = 0
    skipped_without_code = 0
    skipped_idempotent = 0
    total = 0

    async with SessionLocal() as db:
        # 拉取 queued 子任务（含父任务以拿 account_id）
        stmt = (
            select(VideoSubTask)
            .where(VideoSubTask.status == "queued")
            .options(selectinload(VideoSubTask.task))
        )
        sub_tasks = (await db.execute(stmt)).scalars().all()
        logger.info("queued 子任务数: %d", len(sub_tasks))

        # 提前批量取 account.product_code_mode
        account_ids = {st.task.account_id for st in sub_tasks if st.task and st.task.account_id}
        modes: dict = {}
        if account_ids:
            rows = (await db.execute(
                select(Account.id, Account.product_code_mode).where(Account.id.in_(account_ids))
            )).all()
            modes = {aid: mode for aid, mode in rows}

        for st in sub_tasks:
            total += 1
            meta = st.publish_meta if isinstance(st.publish_meta, dict) else None
            # 不再按 publish_meta.status 过滤；只要 meta 存在就尝试清洗（包括
            # generating / failed 等状态，按新规则统一刷一遍）
            if not meta:
                skipped_no_publish_meta += 1
                continue
            account_id = st.task.account_id if st.task else None
            mode = modes.get(account_id, "without_code")
            if mode != "with_code":
                skipped_without_code += 1
                continue

            old_title = str(meta.get("title") or "")
            old_desc = str(meta.get("description") or "")

            need_title = _needs_title_rewrite(old_title)
            need_desc = _needs_desc_rewrite(old_desc)
            if not need_title and not need_desc:
                skipped_idempotent += 1
                continue

            new_meta = dict(meta)
            if need_title:
                new_title = _build_product_code_title(old_title)
                if new_title != old_title:
                    new_meta["title"] = new_title
                    title_changed += 1
            if need_desc:
                new_desc = _clean_description(old_desc)
                if new_desc != old_desc:
                    new_meta["description"] = new_desc
                    desc_changed += 1

            if not dry_run:
                st.publish_meta = new_meta

        if not dry_run:
            await db.commit()

    return {
        "total_queued": total,
        "title_changed": title_changed,
        "desc_changed": desc_changed,
        "skipped_no_publish_meta": skipped_no_publish_meta,
        "skipped_without_code": skipped_without_code,
        "skipped_idempotent": skipped_idempotent,
    }


async def main_async(args: argparse.Namespace) -> None:
    summary = await cleanup(dry_run=args.dry_run)
    logger.info(
        "处理完成（%s）：queued=%d, title_changed=%d, desc_changed=%d, "
        "skip_no_meta=%d, skip_without_code=%d, skip_idempotent=%d",
        "DRY RUN" if args.dry_run else "已写库",
        summary["total_queued"],
        summary["title_changed"],
        summary["desc_changed"],
        summary["skipped_no_publish_meta"],
        summary["skipped_without_code"],
        summary["skipped_idempotent"],
    )


def main() -> None:
    p = argparse.ArgumentParser(description="清洗库存中视频的 publish_meta 标题 / 描述")
    p.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
