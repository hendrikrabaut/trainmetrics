from datetime import date as Date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.models.race import Race
from app.schemas.common import RaceGoal


Priority = Literal["A", "B", "C"]

router = APIRouter(
    prefix="/api/races",
    tags=["races"],
)


class RaceCreate(BaseModel):
    name: str = Field(min_length=1)
    date: Date
    priority: Priority = "B"
    goal: RaceGoal | None = None


class RaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    date: Date | None = None
    priority: Priority | None = None
    goal: RaceGoal | None = None


def _view(race: Race) -> dict:
    return {
        "id": race.id,
        "name": race.name,
        "date": race.date,
        "priority": race.priority,
        "goal": race.goal,
    }


def _race_or_404(db: Session, race_id: int) -> Race:
    race = db.get(Race, race_id)

    if race is None:
        raise HTTPException(status_code=404, detail="Wedstrijd niet gevonden")

    return race


@router.get("/")
def get_races(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    races = db.scalars(
        select(Race).where(Race.user_id == user_id).order_by(Race.date)
    ).all()

    return [_view(race) for race in races]


@router.post("/")
def create_race(
    body: RaceCreate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    race = Race(
        user_id=user_id,
        name=body.name,
        date=body.date.isoformat(),
        priority=body.priority,
        goal=body.goal,
    )

    db.add(race)
    db.commit()
    db.refresh(race)

    return _view(race)


@router.patch("/{race_id}")
def update_race(
    race_id: int,
    body: RaceUpdate,
    db: Session = Depends(get_db),
):
    race = _race_or_404(db, race_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field != "goal":
            continue

        setattr(race, field, value.isoformat() if isinstance(value, Date) else value)

    db.commit()
    db.refresh(race)

    return _view(race)


@router.delete("/{race_id}")
def delete_race(
    race_id: int,
    db: Session = Depends(get_db),
):
    db.delete(_race_or_404(db, race_id))
    db.commit()

    return {"message": "Race deleted successfully"}
