"""add ai account generation fields

Revision ID: 0053
Revises: 64b9a8ffd74b
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0053_ai_account'
down_revision = '0052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    accounts_cols = {col['name'] for col in inspector.get_columns('accounts')}
    pipeline_cols = {col['name'] for col in inspector.get_columns('pipeline_settings')}
    account_tags_indexes = {idx['name'] for idx in inspector.get_indexes('account_tags')} if 'account_tags' in existing_tables else set()

    # 1. accounts 表新增字段
    for col_name, col_def in [
        ('photo_url', sa.Column('photo_url', sa.Text(), nullable=True)),
        ('ai_generation_status', sa.Column('ai_generation_status', sa.String(20), nullable=False, server_default='idle')),
        ('ai_generation_state', sa.Column('ai_generation_state', postgresql.JSON(astext_type=sa.Text()), nullable=True)),
        ('ai_generation_error', sa.Column('ai_generation_error', sa.Text(), nullable=True)),
    ]:
        if col_name not in accounts_cols:
            op.add_column('accounts', col_def)

    # 2. 创建 account_tags 关联表
    if 'account_tags' not in existing_tables:
        op.create_table(
            'account_tags',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tag_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('account_id', 'tag_id', name='uq_account_tags'),
        )
    if 'ix_account_tags_account_id' not in account_tags_indexes:
        op.create_index('ix_account_tags_account_id', 'account_tags', ['account_id'])
    if 'ix_account_tags_tag_id' not in account_tags_indexes:
        op.create_index('ix_account_tags_tag_id', 'account_tags', ['tag_id'])

    # 3. pipeline_settings 表新增 AI 账号生成配置字段
    for col_name, col_def in [
        ('ai_account_video_prompt', sa.Column('ai_account_video_prompt', sa.Text(), nullable=False, server_default='')),
        ('ai_account_name_prompt', sa.Column('ai_account_name_prompt', sa.Text(), nullable=False, server_default='')),
        ('ai_account_avatar_prompt', sa.Column('ai_account_avatar_prompt', sa.Text(), nullable=False, server_default='')),
        ('ai_account_photo_video_prompt', sa.Column('ai_account_photo_video_prompt', sa.Text(), nullable=False, server_default='')),
        ('ai_account_photo_image_prompt', sa.Column('ai_account_photo_image_prompt', sa.Text(), nullable=False, server_default='')),
        ('ai_account_name_model', sa.Column('ai_account_name_model', sa.String(200), nullable=False, server_default='gemini-3.1-pro-preview')),
        ('ai_account_avatar_model', sa.Column('ai_account_avatar_model', sa.String(200), nullable=False, server_default='nano2')),
        ('ai_account_avatar_size', sa.Column('ai_account_avatar_size', sa.String(20), nullable=False, server_default='1:1')),
        ('ai_account_avatar_quality', sa.Column('ai_account_avatar_quality', sa.String(10), nullable=False, server_default='1K')),
    ]:
        if col_name not in pipeline_cols:
            op.add_column('pipeline_settings', col_def)


def downgrade() -> None:
    # 3. 删除 pipeline_settings 新增字段
    op.drop_column('pipeline_settings', 'ai_account_avatar_quality')
    op.drop_column('pipeline_settings', 'ai_account_avatar_size')
    op.drop_column('pipeline_settings', 'ai_account_avatar_model')
    op.drop_column('pipeline_settings', 'ai_account_name_model')
    op.drop_column('pipeline_settings', 'ai_account_photo_image_prompt')
    op.drop_column('pipeline_settings', 'ai_account_photo_video_prompt')
    op.drop_column('pipeline_settings', 'ai_account_avatar_prompt')
    op.drop_column('pipeline_settings', 'ai_account_name_prompt')
    op.drop_column('pipeline_settings', 'ai_account_video_prompt')

    # 2. 删除 account_tags 表
    op.drop_index('ix_account_tags_tag_id', table_name='account_tags')
    op.drop_index('ix_account_tags_account_id', table_name='account_tags')
    op.drop_table('account_tags')

    # 1. 删除 accounts 表新增字段
    op.drop_column('accounts', 'ai_generation_error')
    op.drop_column('accounts', 'ai_generation_state')
    op.drop_column('accounts', 'ai_generation_status')
    op.drop_column('accounts', 'photo_url')
