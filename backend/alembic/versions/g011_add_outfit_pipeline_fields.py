"""add outfit pipeline fields to pipeline_settings

Revision ID: g011_add_outfit_pipeline_fields
Revises: g010_publish_scheduled_at
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "g011_add_outfit_pipeline_fields"
down_revision = "g010_publish_scheduled_at"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    # 步骤2：抽帧后用 Gemini 识别 Unique 穿搭
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_select_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_select_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_select_temperature", sa.Float, nullable=False,
        server_default="0.3",
    ))

    # 步骤3a：对每个 unique 穿搭图理解单品
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_detail_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_detail_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_detail_temperature", sa.Float, nullable=False,
        server_default="0.3",
    ))

    # 步骤3b：单品图生成
    _add_column_if_missing("pipeline_settings", sa.Column(
        "product_imagegen_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "product_imagegen_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "product_imagegen_size", sa.String(20), nullable=False,
        server_default="1:1",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "product_imagegen_quality", sa.String(10), nullable=False,
        server_default="2K",
    ))

    # 步骤3c：新造型图生成
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_regen_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_regen_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_regen_size", sa.String(20), nullable=False,
        server_default="9:16",
    ))
    _add_column_if_missing("pipeline_settings", sa.Column(
        "outfit_regen_quality", sa.String(10), nullable=False,
        server_default="2K",
    ))

    # 新增 enum 值（步骤名称）
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'outfit_selecting'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'outfit_detailing'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'product_imagegen'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'outfit_regen'")


def downgrade() -> None:
    _drop_column_if_exists("pipeline_settings", "outfit_select_model")
    _drop_column_if_exists("pipeline_settings", "outfit_select_prompt")
    _drop_column_if_exists("pipeline_settings", "outfit_select_temperature")
    _drop_column_if_exists("pipeline_settings", "outfit_detail_model")
    _drop_column_if_exists("pipeline_settings", "outfit_detail_prompt")
    _drop_column_if_exists("pipeline_settings", "outfit_detail_temperature")
    _drop_column_if_exists("pipeline_settings", "product_imagegen_model")
    _drop_column_if_exists("pipeline_settings", "product_imagegen_prompt")
    _drop_column_if_exists("pipeline_settings", "product_imagegen_size")
    _drop_column_if_exists("pipeline_settings", "product_imagegen_quality")
    _drop_column_if_exists("pipeline_settings", "outfit_regen_model")
    _drop_column_if_exists("pipeline_settings", "outfit_regen_prompt")
    _drop_column_if_exists("pipeline_settings", "outfit_regen_size")
    _drop_column_if_exists("pipeline_settings", "outfit_regen_quality")
