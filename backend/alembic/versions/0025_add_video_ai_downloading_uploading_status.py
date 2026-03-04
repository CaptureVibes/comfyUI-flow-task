from __future__ import annotations

"""add video ai downloading and uploading status

Revision ID: 0025_add_video_ai_status
Revises: 0024_add_video_desc_field
Create Date: 2026-03-03 19:21:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0025_add_video_ai_status"
down_revision = "0024_add_video_desc_field"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if the enum values already exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_enum_values = None

    # Get existing enum values
    enum_sql = "SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'video_ai_process_status')"
    result = conn.execute(sa.text(enum_sql))
    existing_enum_values = [row[0] for row in result]

    # Add new enum values if they don't exist
    new_values = ['downloading', 'uploading']
    for value in new_values:
        if value not in existing_enum_values:
            op.execute(f"ALTER TYPE video_ai_process_status ADD VALUE '{value}'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL, would need to recreate the type
    pass
