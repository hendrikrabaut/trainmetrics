"""Add Polar accounts, the running index and training plans.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "endurance_activities",
        sa.Column("running_index", sa.Integer()),
    )

    op.create_table(
        "polar_accounts",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("polar_user_id", sa.String()),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("last_sync_at", sa.String()),
    )

    op.create_table(
        "training_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("start_date", sa.String(), nullable=False),
        sa.Column("end_date", sa.String(), nullable=False),
        sa.Column("race_date", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("warning", sa.String()),
    )

    op.create_table(
        "plan_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("training_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("sport", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("distance", sa.Float()),
        sa.Column("duration", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("plan_sessions")
    op.drop_table("training_plans")
    op.drop_table("polar_accounts")
    op.drop_column("endurance_activities", "running_index")
