from __future__ import annotations

"""add video_ai_templates table

Revision ID: 0015_add_video_ai_templates
Revises: 0014_add_video_sources
Create Date: 2026-03-03 00:00:02.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_add_video_ai_templates"
down_revision = "0014_add_video_sources"
branch_labels = None
depends_on = None

_enum_name = "video_ai_process_status"
_enum_values = ("pending", "understanding", "extracting", "success", "fail", "paused")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Create enum type if not exists (use raw SQL to avoid SQLAlchemy event race)
    values_sql = ", ".join(f"'{v}'" for v in _enum_values)
    bind.execute(sa.text(
        f"DO $$ BEGIN "
        f"CREATE TYPE {_enum_name} AS ENUM ({values_sql}); "
        f"EXCEPTION WHEN duplicate_object THEN NULL; "
        f"END $$"
    ))

    existing_tables = set(inspector.get_table_names())
    if "video_ai_templates" in existing_tables:
        return

    op.create_table(
        "video_ai_templates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_source_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "process_status",
            sa.Enum(*_enum_values, name=_enum_name, create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("process_error", sa.Text(), nullable=True),
        sa.Column("prompt_description", sa.Text(), nullable=True),
        sa.Column("extracted_shots", sa.JSON(), nullable=True),
        sa.Column("process_state", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_ai_templates" in set(inspector.get_table_names()):
        op.drop_table("video_ai_templates")

    existing_enums = {e["name"] for e in inspector.get_enums()} if hasattr(inspector, "get_enums") else set()
    if _enum_name in existing_enums:
        sa.Enum(name=_enum_name).drop(bind)
