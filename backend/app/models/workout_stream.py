from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkoutStream(Base):
    """Measurements during a workout, and what was worked out from them."""

    __tablename__ = "workout_streams"

    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    # All JSON. Worked out from one sample a second, of which only every
    # interval_seconds is kept in data.
    data: Mapped[str] = mapped_column(Text, nullable=False)
    splits: Mapped[str] = mapped_column(Text, nullable=False)
    zones: Mapped[str] = mapped_column(Text, nullable=False)
    best_efforts: Mapped[str] = mapped_column(Text, nullable=False)
