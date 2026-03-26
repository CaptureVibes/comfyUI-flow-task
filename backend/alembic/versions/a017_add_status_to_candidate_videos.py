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
    # Create enum type
    candidatevideostatus = sa.Enum(
        "pending", "ai_reviewing", "ai_passed", "ai_failed",
        "importing", "imported", "import_failed",
        name="candidatevideostatus",
    )
    candidatevideostatus.create(op.get_bind(), checkfirst=True)

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
    op.add_column(
        "candidate_videos",
        sa.Column("ai_reviewed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "candidate_videos",
        sa.Column("ai_error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_candidate_videos_status", "candidate_videos", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_videos_status", table_name="candidate_videos")
    op.drop_column("candidate_videos", "ai_error")
    op.drop_column("candidate_videos", "ai_reviewed")
    op.drop_column("candidate_videos", "status")
    sa.Enum(name="candidatevideostatus").drop(op.get_bind(), checkfirst=True)
