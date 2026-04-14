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


def upgrade() -> None:
    op.add_column("tiktok_bloggers", sa.Column("signature", sa.Text, nullable=True))
    op.add_column("tiktok_bloggers", sa.Column("sec_uid", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("tiktok_bloggers", "sec_uid")
    op.drop_column("tiktok_bloggers", "signature")
