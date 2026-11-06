"""Remember a plan's training days and the size of its first long run.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("training_plans", sa.Column("weekdays", sa.String()))
    op.add_column("training_plans", sa.Column("first_long_run", sa.Float()))


def downgrade() -> None:
    op.drop_column("training_plans", "first_long_run")
    op.drop_column("training_plans", "weekdays")
