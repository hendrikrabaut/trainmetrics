from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkoutRoute(Base):
    __tablename__ = "workout_routes"

    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # JSON list of [latitude, longitude], simplified to what a map can show.
    points: Mapped[str] = mapped_column(Text, nullable=False)
