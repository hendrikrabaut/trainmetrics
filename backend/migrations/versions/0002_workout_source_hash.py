"""Add workouts.source_hash, so importing the same file twice skips it.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workouts", sa.Column("source_hash", sa.String()))
    op.create_index(
        "ix_workouts_source_hash",
        "workouts",
        ["source_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_workouts_source_hash", table_name="workouts")
    op.drop_column("workouts", "source_hash")
