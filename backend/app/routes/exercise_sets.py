from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exercise_set import ExerciseSet
from app.models.workout_exercise import WorkoutExercise
from app.schemas.exercise_set import (
    ExerciseSetCreate,
    ExerciseSetResponse,
    ExerciseSetUpdate,
)


router = APIRouter(
    prefix="/api/workout-exercises",
    tags=["exercise sets"],
)


@router.get(
    "/{workout_exercise_id}/sets",
    response_model=list[ExerciseSetResponse],
)
def get_sets(
    workout_exercise_id: int,
    db: Session = Depends(get_db),
):
    statement = (
        select(ExerciseSet)
        .where(
            ExerciseSet.workout_exercise_id == workout_exercise_id
        )
        .order_by(ExerciseSet.set_number)
    )

    sets = db.scalars(statement).all()

    return sets


@router.get(
    "/{workout_exercise_id}/sets/{set_id}",
    response_model=ExerciseSetResponse,
)
def get_set(
    workout_exercise_id: int,
    set_id: int,
    db: Session = Depends(get_db),
):
    statement = select(ExerciseSet).where(
        ExerciseSet.id == set_id,
        ExerciseSet.workout_exercise_id == workout_exercise_id,
    )

    exercise_set = db.scalar(statement)

    if exercise_set is None:
        raise HTTPException(
            status_code=404,
            detail="Exercise set not found",
        )

    return exercise_set


@router.post(
    "/{workout_exercise_id}/sets",
    response_model=ExerciseSetResponse,
)
def create_set(
    workout_exercise_id: int,
    exercise_set: ExerciseSetCreate,
    db: Session = Depends(get_db),
):
    statement = select(WorkoutExercise).where(
        WorkoutExercise.id == workout_exercise_id
    )

    workout_exercise = db.scalar(statement)

    if workout_exercise is None:
        raise HTTPException(
            status_code=404,
            detail="Workout exercise not found",
        )

    new_set = ExerciseSet(
        workout_exercise_id=workout_exercise_id,
        set_number=exercise_set.set_number,
        weight=exercise_set.weight,
        reps=exercise_set.reps,
        notes=exercise_set.notes,
    )

    db.add(new_set)
    db.commit()
    db.refresh(new_set)

    return new_set


@router.patch(
    "/{workout_exercise_id}/sets/{set_id}",
    response_model=ExerciseSetResponse,
)
def update_set(
    workout_exercise_id: int,
    set_id: int,
    exercise_set_update: ExerciseSetUpdate,
    db: Session = Depends(get_db),
):
    statement = select(ExerciseSet).where(
        ExerciseSet.id == set_id,
        ExerciseSet.workout_exercise_id == workout_exercise_id,
    )

    exercise_set = db.scalar(statement)

    if exercise_set is None:
        raise HTTPException(
            status_code=404,
            detail="Exercise set not found",
        )

    update_data = exercise_set_update.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(exercise_set, field, value)

    db.commit()
    db.refresh(exercise_set)

    return exercise_set


@router.delete(
    "/{workout_exercise_id}/sets/{set_id}",
)
def delete_set(
    workout_exercise_id: int,
    set_id: int,
    db: Session = Depends(get_db),
):
    statement = select(ExerciseSet).where(
        ExerciseSet.id == set_id,
        ExerciseSet.workout_exercise_id == workout_exercise_id,
    )

    exercise_set = db.scalar(statement)

    if exercise_set is None:
        raise HTTPException(
            status_code=404,
            detail="Exercise set not found",
        )

    db.delete(exercise_set)
    db.commit()

    return {
        "message": "Exercise set deleted successfully"
    }