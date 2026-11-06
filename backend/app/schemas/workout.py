from pydantic import BaseModel

from app.schemas.common import IsoDate, NonNegativeInt, WorkoutType

# workouts

class WorkoutCreate(BaseModel):
    date: IsoDate
    duration: NonNegativeInt | None = None
    notes: str | None = None
    type: WorkoutType

class WorkoutUpdate(BaseModel):
    date: IsoDate | None = None
    duration: NonNegativeInt | None = None
    notes: str | None = None
    type: WorkoutType | None = None

class WorkoutResponse(BaseModel):
    id: int
    date: str
    duration: int | None
    notes: str | None
    type: str
