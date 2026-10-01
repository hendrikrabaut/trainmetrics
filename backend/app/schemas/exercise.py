from pydantic import BaseModel


class ExerciseCreate(BaseModel):
    name: str
    category: str | None = None
    notes: str | None = None


class ExerciseUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    notes: str | None = None    


class ExerciseResponse(BaseModel):
    id: int
    name: str
    category: str | None
    notes: str | None

    model_config = {
        "from_attributes": True
    }