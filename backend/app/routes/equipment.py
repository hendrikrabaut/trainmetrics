from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.equipment import Equipment
from app.models.workout import Workout
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentResponse,
    EquipmentUpdate,
)


router = APIRouter(
    prefix="/api",
    tags=["equipment"],
)


def _get_equipment_or_404(equipment_id: int, db: Session) -> Equipment:
    equipment = db.get(Equipment, equipment_id)

    if equipment is None:
        raise HTTPException(
            status_code=404,
            detail="Equipment not found",
        )

    return equipment


def _get_workout_or_404(workout_id: int, db: Session) -> Workout:
    workout = db.get(Workout, workout_id)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    return workout


@router.get("/equipment/", response_model=list[EquipmentResponse])
def get_all_equipment(db: Session = Depends(get_db)):
    return db.scalars(select(Equipment).order_by(Equipment.name)).all()


@router.get("/equipment/{equipment_id}", response_model=EquipmentResponse)
def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    return _get_equipment_or_404(equipment_id, db)


@router.post("/equipment/", response_model=EquipmentResponse)
def create_equipment(
    equipment: EquipmentCreate,
    db: Session = Depends(get_db),
):
    new_equipment = Equipment(**equipment.model_dump())

    db.add(new_equipment)
    db.commit()
    db.refresh(new_equipment)

    return new_equipment


@router.patch("/equipment/{equipment_id}", response_model=EquipmentResponse)
def update_equipment(
    equipment_id: int,
    equipment_update: EquipmentUpdate,
    db: Session = Depends(get_db),
):
    equipment = _get_equipment_or_404(equipment_id, db)

    for field, value in equipment_update.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)

    db.commit()
    db.refresh(equipment)

    return equipment


@router.delete("/equipment/{equipment_id}")
def delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    db.delete(_get_equipment_or_404(equipment_id, db))
    db.commit()

    return {
        "message": "Equipment deleted successfully"
    }


@router.get(
    "/workouts/{workout_id}/equipment",
    response_model=list[EquipmentResponse],
)
def get_workout_equipment(
    workout_id: int,
    db: Session = Depends(get_db),
):
    return _get_workout_or_404(workout_id, db).equipment


@router.put(
    "/workouts/{workout_id}/equipment/{equipment_id}",
    response_model=list[EquipmentResponse],
)
def link_equipment(
    workout_id: int,
    equipment_id: int,
    db: Session = Depends(get_db),
):
    workout = _get_workout_or_404(workout_id, db)
    equipment = _get_equipment_or_404(equipment_id, db)

    if equipment not in workout.equipment:
        workout.equipment.append(equipment)
        db.commit()

    return workout.equipment


@router.delete(
    "/workouts/{workout_id}/equipment/{equipment_id}",
    response_model=list[EquipmentResponse],
)
def unlink_equipment(
    workout_id: int,
    equipment_id: int,
    db: Session = Depends(get_db),
):
    workout = _get_workout_or_404(workout_id, db)
    equipment = _get_equipment_or_404(equipment_id, db)

    if equipment in workout.equipment:
        workout.equipment.remove(equipment)
        db.commit()

    return workout.equipment
