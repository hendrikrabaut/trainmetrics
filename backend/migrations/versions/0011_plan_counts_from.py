"""Remember from which day workouts count for an approved plan.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("training_plans", sa.Column("counts_from", sa.String()))


def downgrade() -> None:
    op.drop_column("training_plans", "counts_from")
