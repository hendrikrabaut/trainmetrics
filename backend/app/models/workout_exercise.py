from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
    )

    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id"),
        nullable=False,
    )

    exercise_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    workout: Mapped["Workout"] = relationship(
        back_populates="exercises",
    )

    exercise: Mapped["Exercise"] = relationship(
        back_populates="workout_exercises",
    )

    sets: Mapped[list["ExerciseSet"]] = relationship(
        back_populates="workout_exercise",
        cascade="all, delete-orphan",
    )