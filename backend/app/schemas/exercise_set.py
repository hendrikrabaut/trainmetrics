from pydantic import BaseModel


class ExerciseSetCreate(BaseModel):
    set_number: int
    weight: float | None = None
    reps: int | None = None
    notes: str | None = None


class ExerciseSetUpdate(BaseModel):
    set_number: int | None = None
    weight: float | None = None
    reps: int | None = None
    notes: str | None = None


class ExerciseSetResponse(BaseModel):
    id: int
    workout_exercise_id: int
    set_number: int
    weight: float | None
    reps: int | None
    notes: str | None

    model_config = {
        "from_attributes": True
    }