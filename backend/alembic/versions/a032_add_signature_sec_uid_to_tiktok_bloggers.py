"""add signature and sec_uid to tiktok_bloggers

Revision ID: a032_add_signature_sec_uid_to_tiktok_bloggers
Revises: a031_add_gender_to_accounts
Create Date: 2026-04-14
"""
import sqlalchemy as sa
from alembic import op

revision = "a032_blogger_sig_secuid"
down_revision = "a031_add_gender_to_accounts"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("tiktok_bloggers", "signature"):
        op.add_column("tiktok_bloggers", sa.Column("signature", sa.Text, nullable=True))
    if not _has_column("tiktok_bloggers", "sec_uid"):
        op.add_column("tiktok_bloggers", sa.Column("sec_uid", sa.String(200), nullable=True))


def downgrade() -> None:
    if _has_column("tiktok_bloggers", "sec_uid"):
        op.drop_column("tiktok_bloggers", "sec_uid")
    if _has_column("tiktok_bloggers", "signature"):
        op.drop_column("tiktok_bloggers", "signature")
