"""fix kol_provision_status for accounts that already have kol_user_id

Revision ID: g031_fix_kol_status
Revises: g030_move_kol_links
Create Date: 2026-05-21

backfill 脚本写了 ``kol_user_id`` 但没改 ``kol_provision_status``，导致前端把这些
账号显示成「KOL 生成中」。这里一次性把已经有 kol_user_id 的账号 status 校正到
``success``。

幂等：再次执行 ``alembic upgrade head`` 不会出错；downgrade 仅记日志、不还原数据。
"""
from __future__ import annotations

from alembic import op


revision = "g031_fix_kol_status"
down_revision = "g030_move_kol_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE accounts
        SET kol_provision_status = 'success',
            kol_provision_error = NULL
        WHERE kol_user_id IS NOT NULL
          AND kol_provision_status <> 'success'
        """
    )


def downgrade() -> None:
    # 数据级修正无法精确还原（不知道之前是 pending 还是 failed），不做处理
    pass
