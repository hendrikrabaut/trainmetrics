from pydantic import BaseModel


class BodyMeasurementCreate(BaseModel):
    user_id: int
    date: str
    weight: float | None = None
    body_fat: float | None = None
    waist: float | None = None
    chest: float | None = None
    notes: str | None = None


class BodyMeasurementUpdate(BaseModel):
    date: str | None = None
    weight: float | None = None
    body_fat: float | None = None
    waist: float | None = None
    chest: float | None = None
    notes: str | None = None


class BodyMeasurementResponse(BaseModel):
    id: int
    user_id: int
    date: str
    weight: float | None
    body_fat: float | None
    waist: float | None
    chest: float | None
    notes: str | None

    model_config = {
        "from_attributes": True
    }