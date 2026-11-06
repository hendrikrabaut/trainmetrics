"""Add the user's maximum and resting heart rate.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("max_heart_rate", sa.Integer()))
    op.add_column("users", sa.Column("resting_heart_rate", sa.Integer()))


def downgrade() -> None:
    op.drop_column("users", "resting_heart_rate")
    op.drop_column("users", "max_heart_rate")
