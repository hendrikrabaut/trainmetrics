from pydantic import BaseModel


class WorkoutExerciseCreate(BaseModel):
    exercise_id: int
    exercise_order: int


class WorkoutExerciseResponse(BaseModel):
    id: int
    workout_id: int
    exercise_id: int
    exercise_order: int

    model_config = {
        "from_attributes": True
    }