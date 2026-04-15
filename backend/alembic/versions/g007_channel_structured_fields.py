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


def upgrade() -> None:
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

    op.add_column(
        "account_channel_reservations",
        sa.Column("channel_source", sa.String(length=50), nullable=False, server_default="openapi"),
    )
    op.add_column("account_channel_reservations", sa.Column("channel_id", sa.String(length=300), nullable=True))
    op.add_column("account_channel_reservations", sa.Column("channel_name", sa.String(length=300), nullable=True))
    op.add_column("account_channel_reservations", sa.Column("username", sa.String(length=300), nullable=True))
    op.add_column("account_channel_reservations", sa.Column("avatar_url", sa.Text(), nullable=True))

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

    op.create_index(
        op.f("ix_account_channel_reservations_channel_source"),
        "account_channel_reservations",
        ["channel_source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_account_channel_reservations_channel_id"),
        "account_channel_reservations",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_account_channel_reservations_username"),
        "account_channel_reservations",
        ["username"],
        unique=False,
    )
    op.create_index(
        "ix_account_channel_reservations_platform_channel",
        "account_channel_reservations",
        ["platform", "channel_source", "channel_id"],
        unique=False,
    )

    op.drop_column("accounts", "social_bindings")


def downgrade() -> None:
    op.add_column("accounts", sa.Column("social_bindings", sa.JSON(), nullable=True))
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
    op.drop_index("ix_account_channel_reservations_platform_channel", table_name="account_channel_reservations")
    op.drop_index(op.f("ix_account_channel_reservations_username"), table_name="account_channel_reservations")
    op.drop_index(op.f("ix_account_channel_reservations_channel_id"), table_name="account_channel_reservations")
    op.drop_index(op.f("ix_account_channel_reservations_channel_source"), table_name="account_channel_reservations")
    op.drop_column("account_channel_reservations", "avatar_url")
    op.drop_column("account_channel_reservations", "username")
    op.drop_column("account_channel_reservations", "channel_name")
    op.drop_column("account_channel_reservations", "channel_id")
    op.drop_column("account_channel_reservations", "channel_source")
