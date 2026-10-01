from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.endurance_activity import EnduranceActivity
from app.models.workout import Workout
from app.schemas.endurance_activity import (
    EnduranceActivityCreate,
    EnduranceActivityResponse,
    EnduranceActivityUpdate,
)


router = APIRouter(
    prefix="/api/workouts",
    tags=["endurance activities"],
)


@router.get(
    "/{workout_id}/endurance",
    response_model=EnduranceActivityResponse,
)
def get_endurance_activity(
    workout_id: int,
    db: Session = Depends(get_db),
):
    statement = select(EnduranceActivity).where(
        EnduranceActivity.workout_id == workout_id
    )

    activity = db.scalar(statement)

    if activity is None:
        raise HTTPException(
            status_code=404,
            detail="Endurance activity not found",
        )

    return activity


@router.post(
    "/{workout_id}/endurance",
    response_model=EnduranceActivityResponse,
)
def create_endurance_activity(
    workout_id: int,
    activity: EnduranceActivityCreate,
    db: Session = Depends(get_db),
):
    statement = select(Workout).where(Workout.id == workout_id)
    workout = db.scalar(statement)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    existing_statement = select(EnduranceActivity).where(
        EnduranceActivity.workout_id == workout_id
    )

    existing_activity = db.scalar(existing_statement)

    if existing_activity is not None:
        raise HTTPException(
            status_code=409,
            detail="Workout already has an endurance activity",
        )

    new_activity = EnduranceActivity(
        workout_id=workout_id,
        activity_type=activity.activity_type,
        distance=activity.distance,
        duration=activity.duration,
        average_speed=activity.average_speed,
        average_heart_rate=activity.average_heart_rate,
        max_heart_rate=activity.max_heart_rate,
        elevation_gain=activity.elevation_gain,
        calories=activity.calories,
    )

    db.add(new_activity)
    db.commit()
    db.refresh(new_activity)

    return new_activity


@router.patch(
    "/{workout_id}/endurance",
    response_model=EnduranceActivityResponse,
)
def update_endurance_activity(
    workout_id: int,
    activity_update: EnduranceActivityUpdate,
    db: Session = Depends(get_db),
):
    statement = select(EnduranceActivity).where(
        EnduranceActivity.workout_id == workout_id
    )

    activity = db.scalar(statement)

    if activity is None:
        raise HTTPException(
            status_code=404,
            detail="Endurance activity not found",
        )

    update_data = activity_update.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(activity, field, value)

    db.commit()
    db.refresh(activity)

    return activity


@router.delete(
    "/{workout_id}/endurance",
)
def delete_endurance_activity(
    workout_id: int,
    db: Session = Depends(get_db),
):
    statement = select(EnduranceActivity).where(
        EnduranceActivity.workout_id == workout_id
    )

    activity = db.scalar(statement)

    if activity is None:
        raise HTTPException(
            status_code=404,
            detail="Endurance activity not found",
        )

    db.delete(activity)
    db.commit()

    return {
        "message": "Endurance activity deleted successfully"
    }