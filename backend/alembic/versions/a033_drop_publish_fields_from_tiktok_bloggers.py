"""drop publish fields from tiktok_bloggers

Revision ID: a033_drop_blogger_publish
Revises: a032_blogger_sig_secuid
Create Date: 2026-04-14
"""
import sqlalchemy as sa
from alembic import op

revision = "a033_drop_blogger_publish"
down_revision = "a032_blogger_sig_secuid"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='tiktok_bloggers'")
    )}
    for col in ("publish_enabled", "publish_cron", "publish_window_minutes", "publish_count"):
        if col in existing_cols:
            op.drop_column("tiktok_bloggers", col)


def downgrade() -> None:
    if not _has_column("tiktok_bloggers", "publish_enabled"):
        op.add_column("tiktok_bloggers", sa.Column("publish_enabled", sa.Boolean(), nullable=False, server_default="false"))
    if not _has_column("tiktok_bloggers", "publish_cron"):
        op.add_column("tiktok_bloggers", sa.Column("publish_cron", sa.String(100), nullable=True))
    if not _has_column("tiktok_bloggers", "publish_window_minutes"):
        op.add_column("tiktok_bloggers", sa.Column("publish_window_minutes", sa.Integer(), nullable=False, server_default="0"))
    if not _has_column("tiktok_bloggers", "publish_count"):
        op.add_column("tiktok_bloggers", sa.Column("publish_count", sa.Integer(), nullable=False, server_default="1"))
