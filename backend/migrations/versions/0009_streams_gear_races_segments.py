"""Add measurements per workout, gear wear, races, plan phases and segments.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_streams",
        sa.Column(
            "workout_id",
            sa.Integer(),
            sa.ForeignKey("workouts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("splits", sa.Text(), nullable=False),
        sa.Column("zones", sa.Text(), nullable=False),
        sa.Column("best_efforts", sa.Text(), nullable=False),
    )

    op.add_column("equipment", sa.Column("sport", sa.String()))
    op.add_column(
        "equipment",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("equipment", sa.Column("replace_after_km", sa.Float()))

    op.add_column("plan_sessions", sa.Column("phase", sa.String()))

    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("goal", sa.String()),
    )

    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sport", sa.String(), nullable=False),
        sa.Column("points", sa.Text(), nullable=False),
        sa.Column("length_meters", sa.Float(), nullable=False),
    )

    op.create_table(
        "segment_efforts",
        sa.Column(
            "segment_id",
            sa.Integer(),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "workout_id",
            sa.Integer(),
            sa.ForeignKey("workouts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seconds", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("segment_efforts")
    op.drop_table("segments")
    op.drop_table("races")
    op.drop_column("plan_sessions", "phase")
    op.drop_column("equipment", "replace_after_km")
    op.drop_column("equipment", "is_default")
    op.drop_column("equipment", "sport")
    op.drop_table("workout_streams")
