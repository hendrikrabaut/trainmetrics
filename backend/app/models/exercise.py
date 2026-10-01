from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)

    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        back_populates="exercise",
    )