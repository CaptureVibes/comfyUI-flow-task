"""add status ai_reviewed ai_error to candidate_videos

Revision ID: a017_status_candidate
Revises: a016_video_title_text
Create Date: 2026-03-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a017_status_candidate"
down_revision = "a016_video_title_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("candidate_videos")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("candidate_videos")}

    # Create enum type
    candidatevideostatus = sa.Enum(
        "pending", "ai_reviewing", "ai_passed", "ai_failed",
        "importing", "imported", "import_failed",
        name="candidatevideostatus",
    )
    candidatevideostatus.create(conn, checkfirst=True)

    if "status" not in existing_cols:
        op.add_column(
            "candidate_videos",
            sa.Column(
                "status",
                sa.Enum(
                    "pending", "ai_reviewing", "ai_passed", "ai_failed",
                    "importing", "imported", "import_failed",
                    name="candidatevideostatus",
                    create_type=False,
                ),
                nullable=False,
                server_default="pending",
            ),
        )
    if "ai_reviewed" not in existing_cols:
        op.add_column(
            "candidate_videos",
            sa.Column("ai_reviewed", sa.Boolean(), nullable=False, server_default="false"),
        )
    if "ai_error" not in existing_cols:
        op.add_column(
            "candidate_videos",
            sa.Column("ai_error", sa.Text(), nullable=True),
        )
    if "ix_candidate_videos_status" not in existing_indexes:
        op.create_index(
            "ix_candidate_videos_status", "candidate_videos", ["status"]
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("candidate_videos")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("candidate_videos")}

    if "ix_candidate_videos_status" in existing_indexes:
        op.drop_index("ix_candidate_videos_status", table_name="candidate_videos")
    if "ai_error" in existing_cols:
        op.drop_column("candidate_videos", "ai_error")
    if "ai_reviewed" in existing_cols:
        op.drop_column("candidate_videos", "ai_reviewed")
    if "status" in existing_cols:
        op.drop_column("candidate_videos", "status")
    sa.Enum(name="candidatevideostatus").drop(conn, checkfirst=True)
