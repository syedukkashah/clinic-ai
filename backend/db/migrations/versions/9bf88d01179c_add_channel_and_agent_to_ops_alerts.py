"""add channel and agent to ops_alerts

Revision ID: 9bf88d01179c
Revises: f2243da90c2a
Create Date: 2026-05-08 01:04:56.587165

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9bf88d01179c'
down_revision = 'f2243da90c2a'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('ops_alerts', sa.Column('channel', sa.String(50), nullable=False, server_default='admin'))
    op.add_column('ops_alerts', sa.Column('agent', sa.String(50), nullable=False, server_default='ops_monitor'))


def downgrade() -> None:
    op.drop_column('ops_alerts', 'agent')
    op.drop_column('ops_alerts', 'channel')