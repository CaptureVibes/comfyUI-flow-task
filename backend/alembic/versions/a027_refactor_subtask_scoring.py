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
    # ── video_sub_tasks: drop AI scoring and old NG detection fields ───────────
    for column_name in (
        'ai_score',
        'round1_score',
        'round2_score',
        'round1_reason',
        'round2_reason',
        'scoring_error',
        'elsa_score',
        'manual_score',
        'temporal_consistency',
        'character_integrity',
        'audio_sync',
        'critical_fail',
    ):
        _drop_column_if_exists('video_sub_tasks', column_name)

    # ── video_sub_tasks: add simplified NG detection ───────────────────────────
    _add_column_if_missing('video_sub_tasks', sa.Column('has_ng', sa.Boolean(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('ng_timestamps', sa.JSON(), nullable=True))

    # ── video_task_configs: drop AI scoring round config ──────────────────────
    for column_name in (
        'round1_enabled',
        'round1_prompt',
        'round1_model',
        'round1_threshold',
        'round1_weight',
        'round2_enabled',
        'round2_prompt',
        'round2_model',
        'round2_threshold',
        'round2_weight',
        'final_threshold',
    ):
        _drop_column_if_exists('video_task_configs', column_name)

    # ── video_task_configs: add pool threshold config ─────────────────────────
    _add_column_if_missing('video_task_configs', sa.Column('score_threshold_high', sa.Float(), server_default='60.0', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('score_threshold_low', sa.Float(), server_default='20.0', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('pool_ratio', sa.Float(), server_default='0.75', nullable=False))


def downgrade() -> None:
    # ── video_task_configs: restore AI scoring round config ───────────────────
    for column_name in ('pool_ratio', 'score_threshold_low', 'score_threshold_high'):
        _drop_column_if_exists('video_task_configs', column_name)

    _add_column_if_missing('video_task_configs', sa.Column('final_threshold', sa.Float(), server_default='65.0', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round2_weight', sa.Float(), server_default='0.3', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round2_threshold', sa.Float(), server_default='70.0', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round2_model', sa.String(200), server_default='gemini-3.1-pro-preview', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round2_prompt', sa.Text(), server_default='', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round2_enabled', sa.Boolean(), server_default='true', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round1_weight', sa.Float(), server_default='0.7', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round1_threshold', sa.Float(), server_default='60.0', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round1_model', sa.String(200), server_default='gemini-3.1-pro-preview', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round1_prompt', sa.Text(), server_default='', nullable=False))
    _add_column_if_missing('video_task_configs', sa.Column('round1_enabled', sa.Boolean(), server_default='true', nullable=False))

    # ── video_sub_tasks: drop simplified NG detection ─────────────────────────
    _drop_column_if_exists('video_sub_tasks', 'ng_timestamps')
    _drop_column_if_exists('video_sub_tasks', 'has_ng')

    # ── video_sub_tasks: restore AI scoring and old NG fields ─────────────────
    _add_column_if_missing('video_sub_tasks', sa.Column('critical_fail', sa.Boolean(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('audio_sync', sa.Boolean(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('character_integrity', sa.Boolean(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('temporal_consistency', sa.Boolean(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('manual_score', sa.Integer(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('elsa_score', sa.Integer(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('scoring_error', sa.Text(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('round2_reason', sa.Text(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('round1_reason', sa.Text(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('round2_score', sa.Integer(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('round1_score', sa.Integer(), nullable=True))
    _add_column_if_missing('video_sub_tasks', sa.Column('ai_score', sa.Integer(), nullable=True))
