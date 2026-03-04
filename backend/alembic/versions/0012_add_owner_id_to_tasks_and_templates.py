from __future__ import annotations

"""add owner_id to tasks and task_templates

Revision ID: 0012_add_owner_id
Revises: 0011_add_users_table
Create Date: 2026-03-02 00:00:01.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_add_owner_id"
down_revision = "0011_add_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("owner_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])

    op.add_column(
        "task_templates",
        sa.Column("owner_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_task_templates_owner_id", "task_templates", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_task_templates_owner_id", table_name="task_templates")
    op.drop_column("task_templates", "owner_id")

    op.drop_index("ix_tasks_owner_id", table_name="tasks")
    op.drop_column("tasks", "owner_id")
