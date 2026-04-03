"""add metrics_snapshot to video_publications

Revision ID: 0056
Revises: 0055
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("video_publications")}
    if "metrics_snapshot" not in columns:
        op.add_column("video_publications", sa.Column("metrics_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("video_publications")}
    if "metrics_snapshot" in columns:
        op.drop_column("video_publications", "metrics_snapshot")
