from pydantic import BaseModel

from app.schemas.common import IsoDate, NonNegativeFloat


class BodyMeasurementCreate(BaseModel):
    date: IsoDate
    weight: NonNegativeFloat | None = None
    body_fat: NonNegativeFloat | None = None
    waist: NonNegativeFloat | None = None
    chest: NonNegativeFloat | None = None
    notes: str | None = None


class BodyMeasurementUpdate(BaseModel):
    date: IsoDate | None = None
    weight: NonNegativeFloat | None = None
    body_fat: NonNegativeFloat | None = None
    waist: NonNegativeFloat | None = None
    chest: NonNegativeFloat | None = None
    notes: str | None = None


class BodyMeasurementResponse(BaseModel):
    id: int
    date: str
    weight: float | None
    body_fat: float | None
    waist: float | None
    chest: float | None
    notes: str | None

    model_config = {
        "from_attributes": True
    }