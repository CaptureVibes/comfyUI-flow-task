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

def upgrade() -> None:
    bind = op.get_bind()

    # Ensure enum type exists (idempotent)
    bind.execute(sa.text(
        "DO $$ BEGIN "
        "  CREATE TYPE video_ai_process_status AS ENUM "
        "    ('pending', 'understanding', 'extracting', 'success', 'fail', 'paused'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    ))

    # Create table using raw SQL to avoid SQLAlchemy enum before_create event
    bind.execute(sa.text(
        """
        CREATE TABLE IF NOT EXISTS video_ai_templates (
            id UUID PRIMARY KEY,
            owner_id UUID,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            video_source_id UUID,
            process_status video_ai_process_status NOT NULL DEFAULT 'pending',
            process_error TEXT,
            prompt_description TEXT,
            extracted_shots JSON,
            process_state TEXT,
            extra JSON,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    ))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "video_ai_templates" in set(inspector.get_table_names()):
        op.drop_table("video_ai_templates")
