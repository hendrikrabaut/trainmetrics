from typing import Literal

from pydantic import BaseModel

from app.schemas.common import IsoDate, NonNegativeFloat


EquipmentStatus = Literal["ACTIVE", "RETIRED"]
GearSport = Literal["RUNNING", "CYCLING", "SWIMMING", "OTHER"]


class EquipmentCreate(BaseModel):
    name: str
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    purchase_date: IsoDate | None = None
    status: EquipmentStatus = "ACTIVE"
    notes: str | None = None
    sport: GearSport | None = None
    is_default: bool = False
    replace_after_km: NonNegativeFloat | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    purchase_date: IsoDate | None = None
    status: EquipmentStatus | None = None
    notes: str | None = None
    sport: GearSport | None = None
    is_default: bool | None = None
    replace_after_km: NonNegativeFloat | None = None


class EquipmentResponse(BaseModel):
    id: int
    name: str
    category: str | None
    brand: str | None
    model: str | None
    purchase_date: str | None
    status: str
    notes: str | None
    sport: str | None
    is_default: bool
    replace_after_km: float | None

    model_config = {
        "from_attributes": True
    }
