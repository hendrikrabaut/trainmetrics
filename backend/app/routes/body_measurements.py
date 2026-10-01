from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.body_measurement import BodyMeasurement
from app.schemas.body_measurement import (
    BodyMeasurementCreate,
    BodyMeasurementResponse,
    BodyMeasurementUpdate,
)


router = APIRouter(
    prefix="/api/body-measurements",
    tags=["body measurements"],
)


@router.get(
    "/",
    response_model=list[BodyMeasurementResponse],
)
def get_body_measurements(
    db: Session = Depends(get_db),
):
    statement = select(BodyMeasurement).order_by(
        BodyMeasurement.date.desc()
    )

    measurements = db.scalars(statement).all()

    return measurements


@router.get(
    "/{measurement_id}",
    response_model=BodyMeasurementResponse,
)
def get_body_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
):
    statement = select(BodyMeasurement).where(
        BodyMeasurement.id == measurement_id
    )

    measurement = db.scalar(statement)

    if measurement is None:
        raise HTTPException(
            status_code=404,
            detail="Body measurement not found",
        )

    return measurement


@router.post(
    "/",
    response_model=BodyMeasurementResponse,
)
def create_body_measurement(
    measurement: BodyMeasurementCreate,
    db: Session = Depends(get_db),
):
    new_measurement = BodyMeasurement(
        user_id=measurement.user_id,
        date=measurement.date,
        weight=measurement.weight,
        body_fat=measurement.body_fat,
        waist=measurement.waist,
        chest=measurement.chest,
        notes=measurement.notes,
    )

    db.add(new_measurement)
    db.commit()
    db.refresh(new_measurement)

    return new_measurement


@router.patch(
    "/{measurement_id}",
    response_model=BodyMeasurementResponse,
)
def update_body_measurement(
    measurement_id: int,
    measurement_update: BodyMeasurementUpdate,
    db: Session = Depends(get_db),
):
    statement = select(BodyMeasurement).where(
        BodyMeasurement.id == measurement_id
    )

    measurement = db.scalar(statement)

    if measurement is None:
        raise HTTPException(
            status_code=404,
            detail="Body measurement not found",
        )

    update_data = measurement_update.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(measurement, field, value)

    db.commit()
    db.refresh(measurement)

    return measurement


@router.delete(
    "/{measurement_id}",
)
def delete_body_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
):
    statement = select(BodyMeasurement).where(
        BodyMeasurement.id == measurement_id
    )

    measurement = db.scalar(statement)

    if measurement is None:
        raise HTTPException(
            status_code=404,
            detail="Body measurement not found",
        )

    db.delete(measurement)
    db.commit()

    return {
        "message": "Body measurement deleted successfully"
    }