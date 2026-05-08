"""merge ops_alerts migrations

Revision ID: 596f5f4fc529
Revises: 904485e416d8, 9bf88d01179c
Create Date: 2026-05-08 08:40:38.969706

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '596f5f4fc529'
down_revision = ('904485e416d8', '9bf88d01179c')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass