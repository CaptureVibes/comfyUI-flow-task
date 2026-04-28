"""create face_photos table

Revision ID: a018_face_photos
Revises: a017_status_candidate
Create Date: 2026-03-26
"""
from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a018_face_photos"
down_revision = "a017_status_candidate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "face_photos" not in existing_tables:
        op.create_table(
            "face_photos",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column(
                "tag_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tags.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("face_photo_url", sa.Text, nullable=False),
            sa.Column("frame_index", sa.Integer, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    inspector = sa.inspect(conn)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("face_photos")}
    if "ix_face_photos_tag_id" not in existing_indexes:
        op.create_index("ix_face_photos_tag_id", "face_photos", ["tag_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    if "face_photos" not in existing_tables:
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("face_photos")}
    if "ix_face_photos_tag_id" in existing_indexes:
        op.drop_index("ix_face_photos_tag_id", table_name="face_photos")
    op.drop_table("face_photos")
