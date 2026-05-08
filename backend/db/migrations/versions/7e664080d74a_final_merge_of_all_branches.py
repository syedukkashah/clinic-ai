"""final merge of all branches

Revision ID: 7e664080d74a
Revises: 1024, 596f5f4fc529
Create Date: 2026-05-08 10:42:26.853174

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e664080d74a'
down_revision = ('1024', '596f5f4fc529')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass