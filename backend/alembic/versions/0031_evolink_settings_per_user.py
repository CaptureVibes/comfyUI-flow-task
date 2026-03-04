"""evolink_settings per-user isolation (owner_id as primary key)

Revision ID: 0031
Revises: 0030
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # 删除旧表（key 版本），重建为 owner_id 版本
    bind.execute(sa.text("DROP TABLE IF EXISTS evolink_settings"))
    bind.execute(sa.text("""
        CREATE TABLE evolink_settings (
            owner_id UUID PRIMARY KEY,
            api_key TEXT NOT NULL DEFAULT '',
            api_base_url TEXT NOT NULL DEFAULT 'https://api.evolink.ai',
            understand_model VARCHAR(200) NOT NULL DEFAULT '',
            understand_prompt TEXT NOT NULL DEFAULT '',
            understand_temperature FLOAT NOT NULL DEFAULT 0.3,
            understand_output_format VARCHAR(20) NOT NULL DEFAULT 'text',
            understand_json_schema TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS evolink_settings"))
    bind.execute(sa.text("""
        CREATE TABLE evolink_settings (
            key VARCHAR(32) PRIMARY KEY,
            api_key TEXT NOT NULL DEFAULT '',
            api_base_url TEXT NOT NULL DEFAULT 'https://api.evolink.ai',
            understand_model VARCHAR(200) NOT NULL DEFAULT '',
            understand_prompt TEXT NOT NULL DEFAULT '',
            understand_temperature FLOAT NOT NULL DEFAULT 0.3,
            understand_output_format VARCHAR(20) NOT NULL DEFAULT 'text',
            understand_json_schema TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
