"""Drop tasks/subtasks/task_templates/comfyui_settings tables and related columns

Revision ID: a024
Revises: a023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a024'
down_revision = "a023_add_is_prompt_updated"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop tables with foreign keys first (child → parent order)
    op.drop_table('subtask_generated_videos')
    op.drop_table('subtask_generated_images')
    op.drop_table('subtask_photos')
    op.drop_table('subtasks')
    op.drop_table('tasks')
    op.drop_table('task_templates')
    op.drop_table('comfyui_settings')

    # Drop ComfyUI columns from system_settings
    op.drop_column('system_settings', 'comfyui_server_ip')
    op.drop_column('system_settings', 'comfyui_ports')


def downgrade() -> None:
    # Re-add ComfyUI columns to system_settings
    op.add_column('system_settings', sa.Column('comfyui_server_ip', sa.String(255), server_default='', nullable=False))
    op.add_column('system_settings', sa.Column('comfyui_ports', sa.JSON(), server_default='[]', nullable=False))

    # Re-create tables (reverse order)
    op.create_table(
        'comfyui_settings',
        sa.Column('key', sa.String(32), primary_key=True),
        sa.Column('server_ip', sa.String(255), nullable=False),
        sa.Column('ports', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'task_templates',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('extra', sa.JSON(), server_default='{}'),
        sa.Column('subtasks', sa.JSON(), server_default='[]'),
        sa.Column('workflow_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'tasks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'success', 'fail', 'cancelled', name='task_status'), nullable=False),
        sa.Column('comfy_message', sa.Text(), nullable=True),
        sa.Column('extra', sa.JSON(), server_default='{}'),
        sa.Column('execution_state', sa.Text(), nullable=True),
        sa.Column('workflow_json', sa.JSON(), nullable=True),
        sa.Column('workflow_filename', sa.Text(), nullable=True),
        sa.Column('schedule_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('schedule_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('schedule_time', sa.String(5), nullable=True),
        sa.Column('schedule_port', sa.Integer(), nullable=True),
        sa.Column('schedule_auto_dispatch', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('schedule_last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'subtasks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('task_id', sa.Uuid(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('account_name', sa.String(100), nullable=False),
        sa.Column('account_no', sa.String(100), nullable=False),
        sa.Column('publish_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'success', 'fail', 'cancelled', name='task_status'), nullable=False),
        sa.Column('result', sa.JSON(), server_default='{}'),
        sa.Column('extra', sa.JSON(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'subtask_photos',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('subtask_id', sa.Uuid(), sa.ForeignKey('subtasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'subtask_generated_images',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('subtask_id', sa.Uuid(), sa.ForeignKey('subtasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'subtask_generated_videos',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('subtask_id', sa.Uuid(), sa.ForeignKey('subtasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
