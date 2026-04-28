"""backfill channel reservations from account social bindings

Revision ID: g006_channel_backfill
Revises: g005_channel_reservations
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g006_channel_backfill"
down_revision = "g005_channel_reservations"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return (
        table_name in inspector.get_table_names()
        and column_name in {column["name"] for column in inspector.get_columns(table_name)}
    )


def upgrade() -> None:
    if not _has_column("accounts", "social_bindings"):
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        INSERT INTO account_channel_reservations (
            id,
            account_id,
            platform,
            status,
            source,
            channel_info,
            reserved_at,
            confirmed_at,
            bound_at,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            accounts.id,
            LOWER(binding.value->>'platform'),
            'bound',
            COALESCE(
                NULLIF(binding.value->>'channel_source', ''),
                NULLIF(binding.value->>'source', ''),
                'openapi'
            ),
            binding.value,
            NOW(),
            NOW(),
            NOW(),
            NOW(),
            NOW()
        FROM accounts
        CROSS JOIN LATERAL json_array_elements(accounts.social_bindings) AS binding(value)
        WHERE accounts.social_bindings IS NOT NULL
          AND json_typeof(accounts.social_bindings) = 'array'
          AND LOWER(binding.value->>'platform') IN ('youtube', 'tiktok', 'instagram')
          AND NOT EXISTS (
              SELECT 1
              FROM account_channel_reservations existing
              WHERE existing.account_id = accounts.id
                AND existing.platform = LOWER(binding.value->>'platform')
          )
        """
    )


def downgrade() -> None:
    pass
