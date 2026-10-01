from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workout import Workout
from app.schemas.workout import (
    WorkoutCreate,
    WorkoutResponse,
    WorkoutUpdate,
)
from app.models.workout_exercise import WorkoutExercise
from app.schemas.workout_exercise import (
    WorkoutExerciseCreate,
    WorkoutExerciseResponse,
)
from app.models.workout_exercise import WorkoutExercise
from app.models.exercise_set import ExerciseSet
from app.models.endurance_activity import EnduranceActivity

from app.schemas.workout_detail import WorkoutDetailResponse
from app.schemas.complete_workout import CompleteWorkoutCreate


router = APIRouter(
    prefix="/api/workouts",
    tags=["workouts"],
)

# workouts

@router.post("/", response_model=WorkoutResponse)
def create_workout(
    workout: WorkoutCreate,
    db: Session = Depends(get_db),
):
    new_workout = Workout(
        user_id=workout.user_id,
        date=workout.date,
        duration=workout.duration,
        notes=workout.notes,
        type=workout.type,
    )

    db.add(new_workout)
    db.commit()
    db.refresh(new_workout)

    return new_workout

@router.patch("/{workout_id}", response_model=WorkoutResponse)
def update_workout(
    workout_id: int,
    workout_update: WorkoutUpdate,
    db: Session = Depends(get_db),
):
    statement = select(Workout).where(Workout.id == workout_id)
    workout = db.scalar(statement)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    update_data = workout_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(workout, field, value)

    db.commit()
    db.refresh(workout)

    return workout

@router.get("/", response_model=list[WorkoutResponse])
def get_workouts(db: Session = Depends(get_db)):
    statement = select(Workout).order_by(Workout.date.desc())

    workouts = db.scalars(statement).all()

    return workouts

@router.get("/{workout_id}", response_model=WorkoutDetailResponse)
def get_workout(
    workout_id: int,
    db: Session = Depends(get_db),
):
    statement = select(Workout).where(Workout.id == workout_id)

    workout = db.scalar(statement)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    return workout

@router.delete("/{workout_id}")
def delete_workout(
    workout_id: int,
    db: Session = Depends(get_db),
):
    statement = select(Workout).where(Workout.id == workout_id)
    workout = db.scalar(statement)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    db.delete(workout)
    db.commit()

    return {
        "message": "Workout deleted successfully"
    }

# workout_exercises
@router.post(
    "/{workout_id}/exercises",
    response_model=WorkoutExerciseResponse,
)
def add_exercise_to_workout(
    workout_id: int,
    workout_exercise: WorkoutExerciseCreate,
    db: Session = Depends(get_db),
):
    statement = select(Workout).where(Workout.id == workout_id)
    workout = db.scalar(statement)

    if workout is None:
        raise HTTPException(
            status_code=404,
            detail="Workout not found",
        )

    new_workout_exercise = WorkoutExercise(
        workout_id=workout_id,
        exercise_id=workout_exercise.exercise_id,
        exercise_order=workout_exercise.exercise_order,
    )

    db.add(new_workout_exercise)
    db.commit()
    db.refresh(new_workout_exercise)

    return new_workout_exercise

@router.post("/complete", response_model=WorkoutDetailResponse)
def create_complete_workout(
    workout: CompleteWorkoutCreate,
    db: Session = Depends(get_db),
):
    new_workout = Workout(
        user_id=workout.user_id,
        date=workout.date,
        duration=workout.duration,
        notes=workout.notes,
        type=workout.type,
    )

    db.add(new_workout)
    db.flush()

    for exercise in workout.exercises:
        new_workout_exercise = WorkoutExercise(
            workout_id=new_workout.id,
            exercise_id=exercise.exercise_id,
            exercise_order=exercise.exercise_order,
        )

        db.add(new_workout_exercise)
        db.flush()

        for exercise_set in exercise.sets:
            new_set = ExerciseSet(
                workout_exercise_id=new_workout_exercise.id,
                set_number=exercise_set.set_number,
                weight=exercise_set.weight,
                reps=exercise_set.reps,
                notes=exercise_set.notes,
            )

            db.add(new_set)

    if workout.endurance_activity is not None:
        activity = workout.endurance_activity

        new_activity = EnduranceActivity(
            workout_id=new_workout.id,
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
    db.refresh(new_workout)

    return new_workout