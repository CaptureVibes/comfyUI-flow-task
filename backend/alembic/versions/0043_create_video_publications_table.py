"""create video_publications table

Revision ID: 0043
Revises: 26556066c0a2
Create Date: 2026-03-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0043'
down_revision = '26556066c0a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create video_publications table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS video_publications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sub_task_id UUID NOT NULL REFERENCES video_sub_tasks(id) ON DELETE CASCADE,
            open_api_task_id VARCHAR(100),
            external_id VARCHAR(100),
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            request_payload JSONB,
            response_data JSONB,
            channels_status JSONB,
            total_channels INTEGER NOT NULL DEFAULT 0,
            completed_channels INTEGER NOT NULL DEFAULT 0,
            failed_channels INTEGER NOT NULL DEFAULT 0,
            callback_received BOOLEAN NOT NULL DEFAULT FALSE,
            callback_received_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE
        )
    """)

    # Create indexes if not exists
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_video_publications_sub_task_id
        ON video_publications(sub_task_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_video_publications_open_api_task_id
        ON video_publications(open_api_task_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_video_publications_status
        ON video_publications(status)
    """)


def downgrade() -> None:
    op.drop_table('video_publications')
