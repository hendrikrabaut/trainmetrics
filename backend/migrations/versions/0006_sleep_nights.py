"""Add one row per night of sleep and recovery data.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sleep_nights",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("night", sa.String(), primary_key=True),
        sa.Column("sleep_start", sa.String()),
        sa.Column("sleep_end", sa.String()),
        sa.Column("asleep_seconds", sa.Integer()),
        sa.Column("light_seconds", sa.Integer()),
        sa.Column("deep_seconds", sa.Integer()),
        sa.Column("rem_seconds", sa.Integer()),
        sa.Column("interruption_seconds", sa.Integer()),
        sa.Column("continuity", sa.Float()),
        sa.Column("sleep_score", sa.Float()),
        sa.Column("hrv_ms", sa.Float()),
        sa.Column("heart_rate", sa.Float()),
        sa.Column("breathing_rate", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("sleep_nights")
