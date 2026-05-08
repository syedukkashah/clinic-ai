"""add ml_predictions (no-op: already in initial schema)

Revision ID: 1024
Revises: f2243da90c2a
Create Date: 2026-05-03 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '1024'
down_revision = 'f2243da90c2a'
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass  # ml_predictions already created in initial schema migration

def downgrade() -> None:
    pass
