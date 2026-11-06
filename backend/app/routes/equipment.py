from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.models.equipment import Equipment
from app.models.workout import Workout
from app.services.gear import gear_usage
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


def _keep_one_default(db: Session, equipment: Equipment) -> None:
    """Two defaults for one sport would count the same kilometers twice."""
    if not equipment.is_default:
        return

    others = db.scalars(
        select(Equipment).where(
            Equipment.user_id == equipment.user_id,
            Equipment.sport == equipment.sport,
            Equipment.id != equipment.id,
            Equipment.is_default.is_(True),
        )
    ).all()

    for other in others:
        other.is_default = False


def _get_workout_or_404(workout_id: int, db: Session) -> Workout:
    workout = db.get(Workout, workout_id)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    return workout


@router.get("/equipment/")
def get_all_equipment(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """Everything, with how far it has been used."""
    return gear_usage(db, user_id)


@router.get("/equipment/{equipment_id}", response_model=EquipmentResponse)
def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    return _get_equipment_or_404(equipment_id, db)


@router.post("/equipment/", response_model=EquipmentResponse)
def create_equipment(
    equipment: EquipmentCreate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    new_equipment = Equipment(user_id=user_id, **equipment.model_dump())
    new_equipment.replace_after_km = new_equipment.replace_after_km or None

    db.add(new_equipment)
    db.flush()
    _keep_one_default(db, new_equipment)
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

    required = {"name", "status", "is_default"}

    for field, value in equipment_update.model_dump(exclude_unset=True).items():
        if value is None and field in required:
            raise HTTPException(status_code=422, detail=f"{field} mag niet leeg zijn")

        setattr(equipment, field, value)

    # A limit of zero says nothing, so it means no limit.
    equipment.replace_after_km = equipment.replace_after_km or None

    # Gear without a sport cannot be the default for one.
    if equipment.sport is None:
        equipment.is_default = False

    _keep_one_default(db, equipment)
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
