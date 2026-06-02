"""add kol_link_clicks to video_publications

Revision ID: g042_kol_link_clicks
Revises: g041_accounts_hidden
Create Date: 2026-06-02

video_publications:
  - kol_link_clicks (Integer, nullable): 发布后 24h 内 KOL Link 的点击次数（来自 BigQuery）
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "g042_kol_link_clicks"
down_revision = "g041_accounts_hidden"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_publications",
        sa.Column("kol_link_clicks", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("video_publications", "kol_link_clicks")
