from pydantic import BaseModel

# workouts

class WorkoutCreate(BaseModel):
    user_id: int
    date: str
    duration: int | None = None
    notes: str | None = None
    type: str

class WorkoutUpdate(BaseModel):
    date: str | None = None
    duration: int | None = None
    notes: str | None = None
    type: str | None = None

class WorkoutResponse(BaseModel):
    id: int
    user_id: int
    date: str
    duration: int | None
    notes: str | None
    type: str