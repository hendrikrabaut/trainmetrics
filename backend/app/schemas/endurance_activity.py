from pydantic import BaseModel, Field, model_validator

from app.schemas.common import (
    ActivityType,
    HeartRate,
    NonNegativeFloat,
    NonNegativeInt,
    speed_in_meters_per_second,
)


class EnduranceActivityCreate(BaseModel):
    activity_type: ActivityType
    distance: NonNegativeFloat | None = Field(None, description="Meters")
    duration: NonNegativeInt | None = Field(None, description="Seconds")
    average_speed: NonNegativeFloat | None = Field(
        None,
        description="m/s, calculated from distance and duration when omitted",
    )
    average_heart_rate: HeartRate | None = None
    max_heart_rate: HeartRate | None = None
    elevation_gain: NonNegativeFloat | None = Field(None, description="Meters")
    calories: NonNegativeInt | None = None

    @model_validator(mode="after")
    def fill_average_speed(self):
        if self.average_speed is None:
            self.average_speed = speed_in_meters_per_second(
                self.distance,
                self.duration,
            )

        return self


class EnduranceActivityUpdate(BaseModel):
    activity_type: ActivityType | None = None
    distance: NonNegativeFloat | None = None
    duration: NonNegativeInt | None = None
    average_speed: NonNegativeFloat | None = Field(None, description="m/s")
    average_heart_rate: HeartRate | None = None
    max_heart_rate: HeartRate | None = None
    elevation_gain: NonNegativeFloat | None = None
    calories: NonNegativeInt | None = None


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
    running_index: int | None

    model_config = {
        "from_attributes": True
    }