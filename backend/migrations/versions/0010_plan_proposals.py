"""Add proposals for a plan, and mark trainings added on top of a plan.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plan_sessions",
        sa.Column("is_extra", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "plan_proposals",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("race_date", sa.String()),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("sessions", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("plan_proposals")
    op.drop_column("plan_sessions", "is_extra")
