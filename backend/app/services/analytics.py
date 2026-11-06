from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.body_measurement import BodyMeasurement
from app.models.endurance_activity import EnduranceActivity
from app.models.exercise import Exercise
from app.models.exercise_set import ExerciseSet
from app.models.workout import Workout
from app.models.workout_exercise import WorkoutExercise


def estimated_one_rep_max(weight: float, reps: int) -> float:
    """Epley formula. A single rep is the one-rep max itself."""
    if reps <= 1:
        return weight

    return weight * (1 + reps / 30)


def _day(value: str) -> date:
    # Stored dates are ISO strings, with or without a time part.
    return date.fromisoformat(value[:10])


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _strength_sets(db: Session, user_id: int):
    """Sets that count towards progress: a weight and at least one rep."""
    statement = (
        select(
            Workout.date,
            Exercise.id,
            Exercise.name,
            ExerciseSet.weight,
            ExerciseSet.reps,
        )
        .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
        .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
        .join(ExerciseSet, ExerciseSet.workout_exercise_id == WorkoutExercise.id)
        .where(
            Workout.user_id == user_id,
            ExerciseSet.weight > 0,
            ExerciseSet.reps > 0,
        )
    )

    return db.execute(statement).all()


def weekly_summary(
    db: Session,
    user_id: int,
    weeks: int = 12,
    today: date | None = None,
) -> list[dict]:
    """One row per week, oldest first. Weeks without training are included."""
    current_week = _week_start(today or date.today())
    first_week = current_week - timedelta(weeks=weeks - 1)

    summary = {
        first_week + timedelta(weeks=index): {
            "workouts": 0,
            "duration_seconds": 0,
            "strength_volume_kg": 0.0,
            "running_meters": 0.0,
            "cycling_meters": 0.0,
            "swimming_meters": 0.0,
        }
        for index in range(weeks)
    }

    workouts = db.execute(
        select(Workout.date, Workout.duration).where(Workout.user_id == user_id)
    ).all()

    for workout_date, duration in workouts:
        week = summary.get(_week_start(_day(workout_date)))

        if week is not None:
            week["workouts"] += 1
            week["duration_seconds"] += duration or 0

    for workout_date, _, _, weight, reps in _strength_sets(db, user_id):
        week = summary.get(_week_start(_day(workout_date)))

        if week is not None:
            week["strength_volume_kg"] += weight * reps

    activities = db.execute(
        select(
            Workout.date,
            EnduranceActivity.activity_type,
            EnduranceActivity.distance,
        )
        .join(EnduranceActivity, EnduranceActivity.workout_id == Workout.id)
        .where(Workout.user_id == user_id)
    ).all()

    for workout_date, activity_type, distance in activities:
        week = summary.get(_week_start(_day(workout_date)))
        key = f"{activity_type.lower()}_meters"

        if week is not None and key in week:
            week[key] += distance or 0

    return [
        {"week_start": week_start.isoformat(), **values}
        for week_start, values in sorted(summary.items())
    ]


def exercise_progress(db: Session, user_id: int, exercise_id: int) -> list[dict]:
    """Per training day: heaviest set, volume and best estimated one-rep max."""
    days: dict[date, dict] = defaultdict(
        lambda: {"top_weight_kg": 0.0, "volume_kg": 0.0, "estimated_1rm_kg": 0.0}
    )

    for workout_date, set_exercise_id, _, weight, reps in _strength_sets(db, user_id):
        if set_exercise_id != exercise_id:
            continue

        row = days[_day(workout_date)]
        row["top_weight_kg"] = max(row["top_weight_kg"], weight)
        row["volume_kg"] += weight * reps
        row["estimated_1rm_kg"] = max(
            row["estimated_1rm_kg"],
            round(estimated_one_rep_max(weight, reps), 1),
        )

    return [
        {"date": day.isoformat(), **values}
        for day, values in sorted(days.items())
    ]


def personal_records(db: Session, user_id: int) -> list[dict]:
    """Per exercise: heaviest weight and best estimated one-rep max, with dates."""
    records: dict[int, dict] = {}

    for workout_date, exercise_id, name, weight, reps in _strength_sets(db, user_id):
        day = _day(workout_date).isoformat()
        estimate = round(estimated_one_rep_max(weight, reps), 1)

        record = records.setdefault(
            exercise_id,
            {
                "exercise_id": exercise_id,
                "exercise": name,
                "top_weight_kg": 0.0,
                "top_weight_date": day,
                "estimated_1rm_kg": 0.0,
                "estimated_1rm_date": day,
            },
        )

        if weight > record["top_weight_kg"]:
            record["top_weight_kg"] = weight
            record["top_weight_date"] = day

        if estimate > record["estimated_1rm_kg"]:
            record["estimated_1rm_kg"] = estimate
            record["estimated_1rm_date"] = day

    return sorted(records.values(), key=lambda record: record["exercise"])


def body_weight_history(db: Session, user_id: int) -> list[dict]:
    measurements = db.execute(
        select(BodyMeasurement.date, BodyMeasurement.weight)
        .where(
            BodyMeasurement.user_id == user_id,
            BodyMeasurement.weight.is_not(None),
        )
        .order_by(BodyMeasurement.date)
    ).all()

    return [
        {"date": _day(day).isoformat(), "weight_kg": weight}
        for day, weight in measurements
    ]
