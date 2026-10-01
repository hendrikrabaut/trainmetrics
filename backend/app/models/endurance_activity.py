from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnduranceActivity(Base):
    __tablename__ = "endurance_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
    )

    activity_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    distance: Mapped[float | None] = mapped_column(Float)
    duration: Mapped[int | None] = mapped_column(Integer)
    average_speed: Mapped[float | None] = mapped_column(Float)
    average_heart_rate: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    elevation_gain: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)

    workout: Mapped["Workout"] = relationship(
        back_populates="endurance_activity",
    )