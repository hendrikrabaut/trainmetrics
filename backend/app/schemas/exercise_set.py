from pydantic import BaseModel

from app.schemas.common import NonNegativeFloat, NonNegativeInt


class ExerciseSetCreate(BaseModel):
    set_number: int
    weight: NonNegativeFloat | None = None
    reps: NonNegativeInt | None = None
    notes: str | None = None


class ExerciseSetUpdate(BaseModel):
    set_number: int | None = None
    weight: NonNegativeFloat | None = None
    reps: NonNegativeInt | None = None
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