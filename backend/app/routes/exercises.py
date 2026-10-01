from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exercise import Exercise
from app.schemas.exercise import (
    ExerciseCreate,
    ExerciseResponse,
    ExerciseUpdate,
)


router = APIRouter(
    prefix="/api/exercises",
    tags=["exercises"],
)


@router.get("/", response_model=list[ExerciseResponse])
def get_exercises(db: Session = Depends(get_db)):
    statement = select(Exercise).order_by(Exercise.name)

    exercises = db.scalars(statement).all()

    return exercises


@router.get("/{exercise_id}", response_model=ExerciseResponse)
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
):
    statement = select(Exercise).where(Exercise.id == exercise_id)

    exercise = db.scalar(statement)

    if exercise is None:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found",
        )

    return exercise


@router.post("/", response_model=ExerciseResponse)
def create_exercise(
    exercise: ExerciseCreate,
    db: Session = Depends(get_db),
):
    new_exercise = Exercise(
        name=exercise.name,
        category=exercise.category,
        notes=exercise.notes,
    )

    db.add(new_exercise)
    db.commit()
    db.refresh(new_exercise)

    return new_exercise


@router.patch("/{exercise_id}", response_model=ExerciseResponse)
def update_exercise(
    exercise_id: int,
    exercise_update: ExerciseUpdate,
    db: Session = Depends(get_db),
):
    statement = select(Exercise).where(Exercise.id == exercise_id)

    exercise = db.scalar(statement)

    if exercise is None:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found",
        )

    update_data = exercise_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(exercise, field, value)

    db.commit()
    db.refresh(exercise)

    return exercise


@router.delete("/{exercise_id}")
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
):
    statement = select(Exercise).where(Exercise.id == exercise_id)

    exercise = db.scalar(statement)

    if exercise is None:
        raise HTTPException(
            status_code=404,
            detail="Exercise not found",
        )

    db.delete(exercise)
    db.commit()

    return {
        "message": "Exercise deleted successfully"
    }