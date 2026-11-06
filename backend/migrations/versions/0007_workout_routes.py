"""Add the GPS route of a workout.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_routes",
        sa.Column(
            "workout_id",
            sa.Integer(),
            sa.ForeignKey("workouts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("points", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workout_routes")
