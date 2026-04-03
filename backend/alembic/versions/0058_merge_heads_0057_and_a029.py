"""merge heads 0057 and a029

Revision ID: 0058
Revises: 0057, a029
Create Date: 2026-04-03 11:23:05.395416

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0058'
down_revision = ('0057', 'a029')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
