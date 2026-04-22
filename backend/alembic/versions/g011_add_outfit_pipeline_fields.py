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


def upgrade() -> None:
    # 步骤2：抽帧后用 Gemini 识别 Unique 穿搭
    op.add_column("pipeline_settings", sa.Column(
        "outfit_select_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_select_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_select_temperature", sa.Float, nullable=False,
        server_default="0.3",
    ))

    # 步骤3a：对每个 unique 穿搭图理解单品
    op.add_column("pipeline_settings", sa.Column(
        "outfit_detail_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_detail_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_detail_temperature", sa.Float, nullable=False,
        server_default="0.3",
    ))

    # 步骤3b：单品图生成
    op.add_column("pipeline_settings", sa.Column(
        "product_imagegen_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "product_imagegen_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "product_imagegen_size", sa.String(20), nullable=False,
        server_default="1:1",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "product_imagegen_quality", sa.String(10), nullable=False,
        server_default="2K",
    ))

    # 步骤3c：新造型图生成
    op.add_column("pipeline_settings", sa.Column(
        "outfit_regen_model", sa.String(200), nullable=False,
        server_default="gemini-2.5-flash-preview-05-20",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_regen_prompt", sa.Text, nullable=False,
        server_default="",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_regen_size", sa.String(20), nullable=False,
        server_default="9:16",
    ))
    op.add_column("pipeline_settings", sa.Column(
        "outfit_regen_quality", sa.String(10), nullable=False,
        server_default="2K",
    ))

    # 新增 enum 值（步骤名称）
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'outfit_selecting'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'outfit_detailing'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'product_imagegen'")
    op.execute("ALTER TYPE video_ai_process_status ADD VALUE IF NOT EXISTS 'outfit_regen'")


def downgrade() -> None:
    op.drop_column("pipeline_settings", "outfit_select_model")
    op.drop_column("pipeline_settings", "outfit_select_prompt")
    op.drop_column("pipeline_settings", "outfit_select_temperature")
    op.drop_column("pipeline_settings", "outfit_detail_model")
    op.drop_column("pipeline_settings", "outfit_detail_prompt")
    op.drop_column("pipeline_settings", "outfit_detail_temperature")
    op.drop_column("pipeline_settings", "product_imagegen_model")
    op.drop_column("pipeline_settings", "product_imagegen_prompt")
    op.drop_column("pipeline_settings", "product_imagegen_size")
    op.drop_column("pipeline_settings", "product_imagegen_quality")
    op.drop_column("pipeline_settings", "outfit_regen_model")
    op.drop_column("pipeline_settings", "outfit_regen_prompt")
    op.drop_column("pipeline_settings", "outfit_regen_size")
    op.drop_column("pipeline_settings", "outfit_regen_quality")
