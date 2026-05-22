"""add local_gcs_video_url to video_sources

Revision ID: g033_add_local_gcs_video_url
Revises: g032_face_photo_classification
Create Date: 2026-05-22

GCS 上传后端的链接落到独立字段 local_gcs_video_url，避免与旧 CDN 链接（仍存
在 local_video_url）混在一起。读取时优先 local_video_url，回退到
local_gcs_video_url。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "g033_add_local_gcs_video_url"
down_revision = "g032_face_photo_classification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("video_sources")}
    if "local_gcs_video_url" not in cols:
        op.add_column(
            "video_sources",
            sa.Column("local_gcs_video_url", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("video_sources")}
    if "local_gcs_video_url" in cols:
        op.drop_column("video_sources", "local_gcs_video_url")
