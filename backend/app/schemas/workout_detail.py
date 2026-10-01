from pydantic import BaseModel


class ExerciseSetDetail(BaseModel):
    id: int
    set_number: int
    weight: float | None
    reps: int | None
    notes: str | None

    model_config = {
        "from_attributes": True
    }


class ExerciseDetail(BaseModel):
    id: int
    name: str
    category: str | None
    notes: str | None

    model_config = {
        "from_attributes": True
    }


class WorkoutExerciseDetail(BaseModel):
    id: int
    exercise_order: int
    exercise: ExerciseDetail
    sets: list[ExerciseSetDetail]

    model_config = {
        "from_attributes": True
    }


class EnduranceActivityDetail(BaseModel):
    id: int
    activity_type: str
    distance: float | None
    duration: int | None
    average_speed: float | None
    average_heart_rate: int | None
    max_heart_rate: int | None
    elevation_gain: float | None
    calories: int | None

    model_config = {
        "from_attributes": True
    }


class WorkoutDetailResponse(BaseModel):
    id: int
    user_id: int
    date: str
    duration: int | None
    notes: str | None
    type: str

    exercises: list[WorkoutExerciseDetail] = []
    endurance_activity: EnduranceActivityDetail | None = None

    model_config = {
        "from_attributes": True
    }