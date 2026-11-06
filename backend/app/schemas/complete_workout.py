from pydantic import BaseModel, model_validator

from app.schemas.common import IsoDate, NonNegativeInt, WorkoutType
from app.schemas.endurance_activity import EnduranceActivityCreate
from app.schemas.exercise_set import ExerciseSetCreate


class CompleteExerciseCreate(BaseModel):
    exercise_id: int
    exercise_order: int
    sets: list[ExerciseSetCreate] = []


class CompleteWorkoutCreate(BaseModel):
    user_id: int
    date: IsoDate
    duration: NonNegativeInt | None = None
    notes: str | None = None
    type: WorkoutType

    exercises: list[CompleteExerciseCreate] = []
    endurance_activity: EnduranceActivityCreate | None = None


    @model_validator(mode="after")
    def validate_workout_type(self):
        if self.type == "STRENGTH":
            if not self.exercises:
                raise ValueError(
                    "A strength workout must contain at least one exercise"
                )

            if self.endurance_activity is not None:
                raise ValueError(
                    "A strength workout cannot contain an endurance activity"
                )

        elif self.type == "ENDURANCE":
            if self.endurance_activity is None:
                raise ValueError(
                    "An endurance workout must contain an endurance activity"
                )

            if self.exercises:
                raise ValueError(
                    "An endurance workout cannot contain strength exercises"
                )

        return self