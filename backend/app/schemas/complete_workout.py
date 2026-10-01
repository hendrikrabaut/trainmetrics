from pydantic import BaseModel, model_validator

class CompleteSetCreate(BaseModel):
    set_number: int
    weight: float | None = None
    reps: int | None = None
    notes: str | None = None


class CompleteExerciseCreate(BaseModel):
    exercise_id: int
    exercise_order: int
    sets: list[CompleteSetCreate] = []


class CompleteEnduranceCreate(BaseModel):
    activity_type: str
    distance: float | None = None
    duration: int | None = None
    average_speed: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    elevation_gain: float | None = None
    calories: int | None = None


class CompleteWorkoutCreate(BaseModel):
    user_id: int
    date: str
    duration: int | None = None
    notes: str | None = None
    type: str

    exercises: list[CompleteExerciseCreate] = []
    endurance_activity: CompleteEnduranceCreate | None = None


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