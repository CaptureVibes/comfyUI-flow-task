"""move KOL long/short link storage from accounts.kol_links to account_channel_reservations

Revision ID: g030_move_kol_links
Revises: g029_drop_kol_id
Create Date: 2026-05-21

之前把 KOL 短链放在 ``accounts.kol_links`` JSON 列里按 platform key 缓存，但
KOL 长/短链本来就是 per-reservation 的（YouTube 长链有专属 ``sf=youtube_short_us``
后缀），放在 ``account_channel_reservations`` 才符合数据自然形状。

- 给 ``account_channel_reservations`` 增加 ``kol_long_link`` / ``kol_short_link``
- 删 ``accounts.kol_links`` 列
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "g030_move_kol_links"
down_revision = "g029_drop_kol_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    res_cols = {c["name"] for c in inspect(bind).get_columns("account_channel_reservations")}
    if "kol_long_link" not in res_cols:
        op.add_column("account_channel_reservations", sa.Column("kol_long_link", sa.Text(), nullable=True))
    if "kol_short_link" not in res_cols:
        op.add_column("account_channel_reservations", sa.Column("kol_short_link", sa.Text(), nullable=True))

    account_cols = {c["name"] for c in inspect(bind).get_columns("accounts")}
    if "kol_links" in account_cols:
        op.drop_column("accounts", "kol_links")


def downgrade() -> None:
    bind = op.get_bind()
    account_cols = {c["name"] for c in inspect(bind).get_columns("accounts")}
    if "kol_links" not in account_cols:
        op.add_column("accounts", sa.Column("kol_links", sa.JSON(), nullable=True))

    res_cols = {c["name"] for c in inspect(bind).get_columns("account_channel_reservations")}
    if "kol_short_link" in res_cols:
        op.drop_column("account_channel_reservations", "kol_short_link")
    if "kol_long_link" in res_cols:
        op.drop_column("account_channel_reservations", "kol_long_link")
