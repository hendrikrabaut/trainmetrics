from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlanProposal(Base):
    """A proposal waiting for the user. Nothing here is in the planning yet."""

    __tablename__ = "plan_proposals"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    goal: Mapped[str] = mapped_column(String, nullable=False)
    race_date: Mapped[str | None] = mapped_column(String)

    # MODEL, RULES when the model could not help, or MIXED for both.
    source: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    # JSON list of sessions, with distance in meters and duration in seconds.
    sessions: Mapped[str] = mapped_column(Text, nullable=False)
