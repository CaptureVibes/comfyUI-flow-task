"""rename account_type traffic to shared, add exclusive

Revision ID: g001_rename_traffic_to_shared
Revises: f3c8e1a2b905
Create Date: 2026-04-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g001_rename_traffic_to_shared"
down_revision = "a033_drop_blogger_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 将旧值 'traffic' 迁移为 'shared'
    op.execute("UPDATE accounts SET account_type = 'shared' WHERE account_type = 'traffic'")
    # 更新列默认值
    op.alter_column(
        "accounts",
        "account_type",
        server_default="exclusive",
        existing_type=sa.String(20),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("UPDATE accounts SET account_type = 'traffic' WHERE account_type = 'shared'")
    op.alter_column(
        "accounts",
        "account_type",
        server_default="traffic",
        existing_type=sa.String(20),
        existing_nullable=False,
    )
