from sqlalchemy import ForeignKey, Integer, String, exists
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.database import Base
from app.models.equipment import Equipment, workout_equipment
from app.models.workout_route import WorkoutRoute


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, nullable=False)

    # Identifies the imported file and session, so re-importing skips it.
    source_hash: Mapped[str | None] = mapped_column(
        String,
        unique=True,
        index=True,
    )

    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="WorkoutExercise.exercise_order",
    )

    endurance_activity: Mapped["EnduranceActivity | None"] = relationship(
        back_populates="workout",
        uselist=False,
        cascade="all, delete-orphan",
    )

    equipment: Mapped[list[Equipment]] = relationship(
        secondary=workout_equipment,
    )


# Lets a list of workouts say which have a route, without loading the routes.
Workout.has_route = column_property(
    exists().where(WorkoutRoute.workout_id == Workout.id)
)
