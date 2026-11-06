"""Keep Polar's own Nightly Recharge verdict per night.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sleep_nights", sa.Column("recharge_status", sa.Integer()))
    op.add_column("sleep_nights", sa.Column("ans_charge", sa.Float()))


def downgrade() -> None:
    op.drop_column("sleep_nights", "ans_charge")
    op.drop_column("sleep_nights", "recharge_status")
