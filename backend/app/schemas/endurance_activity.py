from pydantic import BaseModel


class EnduranceActivityCreate(BaseModel):
    activity_type: str
    distance: float | None = None
    duration: int | None = None
    average_speed: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    elevation_gain: float | None = None
    calories: int | None = None


class EnduranceActivityUpdate(BaseModel):
    activity_type: str | None = None
    distance: float | None = None
    duration: int | None = None
    average_speed: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    elevation_gain: float | None = None
    calories: int | None = None


class EnduranceActivityResponse(BaseModel):
    id: int
    workout_id: int
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