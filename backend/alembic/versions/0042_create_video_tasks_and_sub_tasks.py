"""create video_tasks and video_sub_tasks, drop daily_generations

Revision ID: 0042
Revises: 52dcecd3eb21
Create Date: 2026-03-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0042"
down_revision = ("52dcecd3eb21", "4a84e2de9864")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("duration", sa.String(50), nullable=False),
        sa.Column("shots", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_video_tasks_owner_id", "video_tasks", ["owner_id"])
    op.create_index("ix_video_tasks_account_id", "video_tasks", ["account_id"])
    op.create_index("ix_video_tasks_template_id", "video_tasks", ["template_id"])
    op.create_index("ix_video_tasks_target_date", "video_tasks", ["target_date"])
    op.create_index("ix_video_tasks_status", "video_tasks", ["status"])

    op.create_table(
        "video_sub_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("video_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sub_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("result_video_url", sa.Text(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "sub_index", name="uq_video_sub_tasks_task_sub_index"),
    )
    op.create_index("ix_video_sub_tasks_task_id", "video_sub_tasks", ["task_id"])
    op.create_index("ix_video_sub_tasks_status", "video_sub_tasks", ["status"])

    op.drop_table("daily_generations")


def downgrade() -> None:
    op.create_table(
        "daily_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image", sa.Text(), nullable=False),
        sa.Column("duration", sa.String(50), nullable=False),
        sa.Column("shots", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("result_videos", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("selected_video_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.drop_index("ix_video_sub_tasks_status", table_name="video_sub_tasks")
    op.drop_index("ix_video_sub_tasks_task_id", table_name="video_sub_tasks")
    op.drop_table("video_sub_tasks")
    op.drop_index("ix_video_tasks_status", table_name="video_tasks")
    op.drop_index("ix_video_tasks_target_date", table_name="video_tasks")
    op.drop_index("ix_video_tasks_template_id", table_name="video_tasks")
    op.drop_index("ix_video_tasks_account_id", table_name="video_tasks")
    op.drop_index("ix_video_tasks_owner_id", table_name="video_tasks")
    op.drop_table("video_tasks")
