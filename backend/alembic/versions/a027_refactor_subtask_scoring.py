"""Refactor subtask scoring: remove AI scoring fields, replace critical checks with has_ng/ng_timestamps,
split pending_publish into stashed/decision_rejected statuses, add pool threshold config.

Revision ID: a027
Revises: a026
"""
from alembic import op
import sqlalchemy as sa

revision = 'a027'
down_revision = 'a026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── video_sub_tasks: drop AI scoring and old NG detection fields ───────────
    op.drop_column('video_sub_tasks', 'ai_score')
    op.drop_column('video_sub_tasks', 'round1_score')
    op.drop_column('video_sub_tasks', 'round2_score')
    op.drop_column('video_sub_tasks', 'round1_reason')
    op.drop_column('video_sub_tasks', 'round2_reason')
    op.drop_column('video_sub_tasks', 'scoring_error')
    op.drop_column('video_sub_tasks', 'elsa_score')
    op.drop_column('video_sub_tasks', 'manual_score')
    op.drop_column('video_sub_tasks', 'temporal_consistency')
    op.drop_column('video_sub_tasks', 'character_integrity')
    op.drop_column('video_sub_tasks', 'audio_sync')
    op.drop_column('video_sub_tasks', 'critical_fail')

    # ── video_sub_tasks: add simplified NG detection ───────────────────────────
    op.add_column('video_sub_tasks', sa.Column('has_ng', sa.Boolean(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('ng_timestamps', sa.JSON(), nullable=True))

    # ── video_task_configs: drop AI scoring round config ──────────────────────
    op.drop_column('video_task_configs', 'round1_enabled')
    op.drop_column('video_task_configs', 'round1_prompt')
    op.drop_column('video_task_configs', 'round1_model')
    op.drop_column('video_task_configs', 'round1_threshold')
    op.drop_column('video_task_configs', 'round1_weight')
    op.drop_column('video_task_configs', 'round2_enabled')
    op.drop_column('video_task_configs', 'round2_prompt')
    op.drop_column('video_task_configs', 'round2_model')
    op.drop_column('video_task_configs', 'round2_threshold')
    op.drop_column('video_task_configs', 'round2_weight')
    op.drop_column('video_task_configs', 'final_threshold')

    # ── video_task_configs: add pool threshold config ─────────────────────────
    op.add_column('video_task_configs', sa.Column('score_threshold_high', sa.Float(), server_default='60.0', nullable=False))
    op.add_column('video_task_configs', sa.Column('score_threshold_low', sa.Float(), server_default='20.0', nullable=False))
    op.add_column('video_task_configs', sa.Column('pool_ratio', sa.Float(), server_default='0.75', nullable=False))


def downgrade() -> None:
    # ── video_task_configs: restore AI scoring round config ───────────────────
    op.drop_column('video_task_configs', 'pool_ratio')
    op.drop_column('video_task_configs', 'score_threshold_low')
    op.drop_column('video_task_configs', 'score_threshold_high')

    op.add_column('video_task_configs', sa.Column('final_threshold', sa.Float(), server_default='65.0', nullable=False))
    op.add_column('video_task_configs', sa.Column('round2_weight', sa.Float(), server_default='0.3', nullable=False))
    op.add_column('video_task_configs', sa.Column('round2_threshold', sa.Float(), server_default='70.0', nullable=False))
    op.add_column('video_task_configs', sa.Column('round2_model', sa.String(200), server_default='gemini-3.1-pro-preview', nullable=False))
    op.add_column('video_task_configs', sa.Column('round2_prompt', sa.Text(), server_default='', nullable=False))
    op.add_column('video_task_configs', sa.Column('round2_enabled', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('video_task_configs', sa.Column('round1_weight', sa.Float(), server_default='0.7', nullable=False))
    op.add_column('video_task_configs', sa.Column('round1_threshold', sa.Float(), server_default='60.0', nullable=False))
    op.add_column('video_task_configs', sa.Column('round1_model', sa.String(200), server_default='gemini-3.1-pro-preview', nullable=False))
    op.add_column('video_task_configs', sa.Column('round1_prompt', sa.Text(), server_default='', nullable=False))
    op.add_column('video_task_configs', sa.Column('round1_enabled', sa.Boolean(), server_default='true', nullable=False))

    # ── video_sub_tasks: drop simplified NG detection ─────────────────────────
    op.drop_column('video_sub_tasks', 'ng_timestamps')
    op.drop_column('video_sub_tasks', 'has_ng')

    # ── video_sub_tasks: restore AI scoring and old NG fields ─────────────────
    op.add_column('video_sub_tasks', sa.Column('critical_fail', sa.Boolean(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('audio_sync', sa.Boolean(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('character_integrity', sa.Boolean(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('temporal_consistency', sa.Boolean(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('manual_score', sa.Integer(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('elsa_score', sa.Integer(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('scoring_error', sa.Text(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('round2_reason', sa.Text(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('round1_reason', sa.Text(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('round2_score', sa.Integer(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('round1_score', sa.Integer(), nullable=True))
    op.add_column('video_sub_tasks', sa.Column('ai_score', sa.Integer(), nullable=True))
