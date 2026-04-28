"""move account social bindings to structured channel table

Revision ID: g007_channel_fields
Revises: g006_channel_backfill
Create Date: 2026-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g007_channel_fields"
down_revision = "g006_channel_backfill"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return (
        table_name in inspector.get_table_names()
        and column_name in {column["name"] for column in inspector.get_columns(table_name)}
    )


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    if _has_column("accounts", "social_bindings"):
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

    _add_column_if_missing(
        "account_channel_reservations",
        sa.Column("channel_source", sa.String(length=50), nullable=False, server_default="openapi"),
    )
    _add_column_if_missing("account_channel_reservations", sa.Column("channel_id", sa.String(length=300), nullable=True))
    _add_column_if_missing("account_channel_reservations", sa.Column("channel_name", sa.String(length=300), nullable=True))
    _add_column_if_missing("account_channel_reservations", sa.Column("username", sa.String(length=300), nullable=True))
    _add_column_if_missing("account_channel_reservations", sa.Column("avatar_url", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE account_channel_reservations
        SET
            channel_source = COALESCE(
                NULLIF(channel_info->>'channel_source', ''),
                NULLIF(channel_info->>'source', ''),
                source,
                'openapi'
            ),
            channel_id = NULLIF(channel_info->>'channel_id', ''),
            channel_name = NULLIF(channel_info->>'channel_name', ''),
            username = NULLIF(channel_info->>'username', ''),
            avatar_url = NULLIF(channel_info->>'avatar_url', '')
        WHERE channel_info IS NOT NULL
        """
    )

    for index_name, columns in (
        (op.f("ix_account_channel_reservations_channel_source"), ["channel_source"]),
        (op.f("ix_account_channel_reservations_channel_id"), ["channel_id"]),
        (op.f("ix_account_channel_reservations_username"), ["username"]),
        ("ix_account_channel_reservations_platform_channel", ["platform", "channel_source", "channel_id"]),
    ):
        if not _has_index("account_channel_reservations", index_name):
            op.create_index(index_name, "account_channel_reservations", columns, unique=False)

    _drop_column_if_exists("accounts", "social_bindings")


def downgrade() -> None:
    _add_column_if_missing("accounts", sa.Column("social_bindings", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE accounts
        SET social_bindings = sub.bindings
        FROM (
            SELECT
                account_id,
                jsonb_agg(
                    COALESCE(channel_info::jsonb, '{}'::jsonb)
                    || jsonb_build_object(
                        'platform', platform,
                        'channel_source', channel_source,
                        'channel_id', COALESCE(channel_id, ''),
                        'channel_name', COALESCE(channel_name, ''),
                        'username', COALESCE(username, ''),
                        'avatar_url', COALESCE(avatar_url, '')
                    )
                    ORDER BY created_at ASC
                )::json AS bindings
            FROM account_channel_reservations
            WHERE status = 'bound'
            GROUP BY account_id
        ) AS sub
        WHERE accounts.id = sub.account_id
        """
    )
    for index_name in (
        "ix_account_channel_reservations_platform_channel",
        op.f("ix_account_channel_reservations_username"),
        op.f("ix_account_channel_reservations_channel_id"),
        op.f("ix_account_channel_reservations_channel_source"),
    ):
        if _has_index("account_channel_reservations", index_name):
            op.drop_index(index_name, table_name="account_channel_reservations")
    _drop_column_if_exists("account_channel_reservations", "avatar_url")
    _drop_column_if_exists("account_channel_reservations", "username")
    _drop_column_if_exists("account_channel_reservations", "channel_name")
    _drop_column_if_exists("account_channel_reservations", "channel_id")
    _drop_column_if_exists("account_channel_reservations", "channel_source")
