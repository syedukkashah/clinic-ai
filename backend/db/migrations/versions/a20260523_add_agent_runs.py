"""add agent_runs table

Revision ID: a20260523
Revises: 7e664080d74a
Create Date: 2026-05-23 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a20260523"
down_revision = "7e664080d74a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent", sa.String(length=50), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("mode", sa.String(length=30), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("trigger", sa.String(length=80), nullable=True),
        sa.Column("outcome", sa.String(length=80), nullable=True),
        sa.Column("steps_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("providers_used", sa.JSON(), nullable=True),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_id"), "agent_runs", ["id"], unique=False)
    op.create_index(op.f("ix_agent_runs_agent"), "agent_runs", ["agent"], unique=False)
    op.create_index(op.f("ix_agent_runs_session_id"), "agent_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_started_at"), "agent_runs", ["started_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_agent_runs_started_at"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_session_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
