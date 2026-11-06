from typing import Literal

from pydantic import BaseModel

from app.schemas.common import IsoDate


EquipmentStatus = Literal["ACTIVE", "RETIRED"]


class EquipmentCreate(BaseModel):
    user_id: int
    name: str
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    purchase_date: IsoDate | None = None
    status: EquipmentStatus = "ACTIVE"
    notes: str | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    purchase_date: IsoDate | None = None
    status: EquipmentStatus | None = None
    notes: str | None = None


class EquipmentResponse(BaseModel):
    id: int
    user_id: int
    name: str
    category: str | None
    brand: str | None
    model: str | None
    purchase_date: str | None
    status: str
    notes: str | None

    model_config = {
        "from_attributes": True
    }
