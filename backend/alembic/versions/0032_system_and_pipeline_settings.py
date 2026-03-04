"""migrate to system_settings and pipeline_settings tables

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 创建 system_settings 表，迁移 comfyui_settings 数据
    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key VARCHAR(32) PRIMARY KEY,
            comfyui_server_ip VARCHAR(255) NOT NULL DEFAULT '',
            comfyui_ports JSON NOT NULL DEFAULT '[]',
            evolink_api_key TEXT NOT NULL DEFAULT '',
            evolink_api_base_url TEXT NOT NULL DEFAULT 'https://api.evolink.ai',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    # 迁移 comfyui_settings 数据到 system_settings（evolink 字段填空字符串默认值）
    bind.execute(sa.text("""
        INSERT INTO system_settings (key, comfyui_server_ip, comfyui_ports, evolink_api_key, evolink_api_base_url, created_at, updated_at)
        SELECT key, server_ip, ports, '', 'https://api.evolink.ai', created_at, updated_at
        FROM comfyui_settings
        ON CONFLICT (key) DO NOTHING
    """))

    # 删除旧的 comfyui_settings 表
    bind.execute(sa.text("DROP TABLE IF EXISTS comfyui_settings"))

    # 创建 pipeline_settings 表（用户流程配置）
    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS pipeline_settings (
            owner_id UUID PRIMARY KEY,
            understand_model VARCHAR(200) NOT NULL DEFAULT '',
            understand_prompt TEXT NOT NULL DEFAULT '',
            understand_temperature FLOAT NOT NULL DEFAULT 0.3,
            understand_output_format VARCHAR(20) NOT NULL DEFAULT 'text',
            understand_json_schema TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    # 删除旧的 evolink_settings 表（数据丢弃，需重新配置）
    bind.execute(sa.text("DROP TABLE IF EXISTS evolink_settings"))


def downgrade() -> None:
    bind = op.get_bind()

    # 重建 comfyui_settings
    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS comfyui_settings (
            key VARCHAR(32) PRIMARY KEY,
            server_ip VARCHAR(255) NOT NULL,
            ports JSON NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    # 迁移回 comfyui_settings
    bind.execute(sa.text("""
        INSERT INTO comfyui_settings (key, server_ip, ports, created_at, updated_at)
        SELECT key, comfyui_server_ip, comfyui_ports, created_at, updated_at
        FROM system_settings
        ON CONFLICT (key) DO NOTHING
    """))

    # 删除新表
    bind.execute(sa.text("DROP TABLE IF EXISTS system_settings"))
    bind.execute(sa.text("DROP TABLE IF EXISTS pipeline_settings"))

    # 重建 evolink_settings（空表）
    bind.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS evolink_settings (
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
