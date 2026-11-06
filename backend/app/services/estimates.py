"""Estimates in the style of Strava and Polar: effort, fitness and race times.

These are models, not measurements. The frontend labels them as estimates.
"""
import json
import math
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.endurance_activity import EnduranceActivity
from app.models.user import User
from app.models.workout import Workout
from app.models.workout_stream import WorkoutStream
from app.models.workout_exercise import WorkoutExercise
from app.services.analytics import parse_day


DEFAULT_MAX_HEART_RATE = 190
RESTING_HEART_RATE = 60
RIEGEL_EXPONENT = 1.06
BEST_RUN_WINDOW_DAYS = 90
BEST_RUN_MINIMUM_METERS = 3000
RUNNING_INDEX_SAMPLE = 10

RACE_DISTANCES = {
    "5 km": 5000,
    "10 km": 10000,
    "Halve marathon": 21098,
    "Marathon": 42195,
}


def _seconds(clock: str) -> int:
    hours, minutes, seconds = clock.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


# Running index -> maximal effort over 5 km, 10 km, half and full marathon.
# Source: "Running Index" chapter of the Polar user manuals.
POLAR_RACE_TABLE = {
    index: tuple(_seconds(clock) for clock in clocks)
    for index, clocks in {
        36: ("0:36:20", "1:15:10", "2:48:00", "5:43:00"),
        38: ("0:34:20", "1:10:50", "2:38:00", "5:24:00"),
        40: ("0:32:20", "1:07:00", "2:29:30", "5:06:00"),
        42: ("0:30:40", "1:03:30", "2:21:30", "4:51:00"),
        44: ("0:29:10", "1:00:20", "2:14:30", "4:37:00"),
        46: ("0:27:50", "0:57:30", "2:08:00", "4:24:00"),
        48: ("0:26:30", "0:55:00", "2:02:00", "4:12:00"),
        50: ("0:25:20", "0:52:40", "1:57:00", "4:02:00"),
        52: ("0:24:20", "0:50:30", "1:52:00", "3:52:00"),
        54: ("0:23:20", "0:48:30", "1:47:30", "3:43:00"),
        56: ("0:22:30", "0:46:40", "1:43:30", "3:35:00"),
        58: ("0:21:40", "0:45:00", "1:39:30", "3:27:00"),
        60: ("0:20:50", "0:43:20", "1:36:00", "3:20:00"),
        62: ("0:20:10", "0:41:50", "1:32:30", "3:13:00"),
        64: ("0:19:30", "0:40:30", "1:29:30", "3:07:00"),
        66: ("0:18:50", "0:39:10", "1:26:30", "3:01:00"),
        68: ("0:18:20", "0:38:00", "1:24:00", "2:55:00"),
        70: ("0:17:50", "0:36:50", "1:21:30", "2:50:00"),
        72: ("0:17:10", "0:35:50", "1:19:00", "2:45:00"),
        74: ("0:16:40", "0:34:50", "1:17:00", "2:40:00"),
        76: ("0:16:20", "0:33:50", "1:14:30", "2:36:00"),
        78: ("0:15:50", "0:33:00", "1:12:30", "2:32:00"),
    }.items()
}


def load_workouts(db: Session, user_id: int) -> list[Workout]:
    """All workouts with their details, oldest first."""
    statement = (
        select(Workout)
        .where(Workout.user_id == user_id)
        .options(
            selectinload(Workout.endurance_activity),
            selectinload(Workout.exercises).options(
                selectinload(WorkoutExercise.sets),
                selectinload(WorkoutExercise.exercise),
            ),
        )
        .order_by(Workout.date)
    )

    return list(db.scalars(statement).all())


def heart_rate_limits(db: Session, user_id: int, workouts: list[Workout]) -> tuple[int, int]:
    """(maximum, resting), from the profile or else the training history."""
    user = db.get(User, user_id)

    return (
        (user.max_heart_rate if user else None) or _highest_heart_rate(workouts),
        (user.resting_heart_rate if user else None) or RESTING_HEART_RATE,
    )


def _highest_heart_rate(workouts: list[Workout]) -> int:
    rates = [
        workout.endurance_activity.max_heart_rate
        for workout in workouts
        if workout.endurance_activity
        and workout.endurance_activity.max_heart_rate
    ]

    return max(rates, default=DEFAULT_MAX_HEART_RATE)


def effort_for(
    seconds: float,
    average_heart_rate: float | None,
    is_endurance: bool,
    limits: tuple[int, int],
) -> int:
    heart_rate_max, heart_rate_rest = limits

    if average_heart_rate:
        reserve = (average_heart_rate - heart_rate_rest) / max(
            heart_rate_max - heart_rate_rest,
            1,
        )
        intensity = min(max(reserve, 0), 1)
    else:
        intensity = 0.55 if is_endurance else 0.45

    return round(seconds / 60 * intensity * 0.64 * math.exp(1.92 * intensity))


def effort_score(
    workout: Workout,
    heart_rate_max: int,
    heart_rate_rest: int = RESTING_HEART_RATE,
) -> int:
    """Training impulse (Banister): more for longer and for harder.

    Workouts without heart rate data get a typical intensity for their type.
    """
    activity = workout.endurance_activity

    return effort_for(
        (activity.duration if activity else None) or workout.duration or 1800,
        activity.average_heart_rate if activity else None,
        activity is not None,
        (heart_rate_max, heart_rate_rest),
    )


def fitness_series(
    workouts: list[Workout],
    limits: tuple[int, int],
    today: date | None = None,
    days: int = 90,
) -> list[dict]:
    """Fitness (42-day average of effort), fatigue (7-day) and their difference."""
    today = today or date.today()

    if not workouts:
        return []

    daily: dict[date, int] = {}

    for workout in workouts:
        day = parse_day(workout.date)
        daily[day] = daily.get(day, 0) + effort_score(workout, *limits)

    fitness = 0.0
    fatigue = 0.0
    series = []
    day = min(daily)

    while day <= today:
        load = daily.get(day, 0)
        fitness += (load - fitness) / 42
        fatigue += (load - fatigue) / 7

        series.append(
            {
                "date": day.isoformat(),
                "fitness": round(fitness, 1),
                "fatigue": round(fatigue, 1),
                "form": round(fitness - fatigue, 1),
            }
        )

        day += timedelta(days=1)

    return series[-days:]


def polar_predictions(running_index: float) -> dict[str, int] | None:
    """Reads Polar's table, interpolating between its rows. None outside it."""
    if not 36 <= running_index <= 78:
        return None

    lower = 36 + 2 * int((running_index - 36) // 2)
    upper = min(lower + 2, 78)
    share = (running_index - lower) / 2

    return {
        name: round(
            POLAR_RACE_TABLE[lower][column]
            + (POLAR_RACE_TABLE[upper][column] - POLAR_RACE_TABLE[lower][column])
            * share
        )
        for column, name in enumerate(RACE_DISTANCES)
    }


def riegel_predictions(distance: float, seconds: int) -> dict[str, int]:
    return {
        name: round(seconds * (target / distance) ** RIEGEL_EXPONENT)
        for name, target in RACE_DISTANCES.items()
    }


def running_index_summary(workouts: list[Workout]) -> dict | None:
    trend = [
        {
            "date": parse_day(workout.date).isoformat(),
            "running_index": workout.endurance_activity.running_index,
        }
        for workout in workouts
        if workout.endurance_activity
        and workout.endurance_activity.running_index
    ]

    if not trend:
        return None

    # Polar advises its long-term average over any single value.
    recent = [row["running_index"] for row in trend[-RUNNING_INDEX_SAMPLE:]]
    average = round(sum(recent) / len(recent), 1)

    return {
        "average": average,
        "sample_size": len(recent),
        "trend": trend,
        "predictions": polar_predictions(average),
    }


def best_recent_run(
    workouts: list[Workout],
    today: date | None = None,
    efforts: list[dict] | None = None,
) -> dict | None:
    """What projects to the fastest 10 km: a whole run or a stretch within one."""
    cutoff = (today or date.today()) - timedelta(days=BEST_RUN_WINDOW_DAYS)
    best = None

    candidates = [
        (
            parse_day(workout.date).isoformat(),
            workout.endurance_activity.distance,
            workout.endurance_activity.duration,
            False,
        )
        for workout in workouts
        if workout.endurance_activity is not None
        and workout.endurance_activity.activity_type == "RUNNING"
        and workout.endurance_activity.duration
        and (workout.endurance_activity.distance or 0) >= BEST_RUN_MINIMUM_METERS
        and parse_day(workout.date) >= cutoff
    ]

    candidates += [
        (effort["date"], effort["meters"], effort["seconds"], True)
        for effort in efforts or []
    ]

    for day, distance, seconds, is_stretch in candidates:
        predictions = riegel_predictions(distance, seconds)

        if best is None or predictions["10 km"] < best["predictions"]["10 km"]:
            best = {
                "date": day,
                "distance": distance,
                "duration": round(seconds),
                "is_stretch": is_stretch,
                "predictions": predictions,
            }

    return best


def _recent_run_efforts(db: Session, user_id: int, since: date) -> list[dict]:
    rows = db.execute(
        select(Workout.date, WorkoutStream.best_efforts)
        .join(WorkoutStream, WorkoutStream.workout_id == Workout.id)
        .join(EnduranceActivity, EnduranceActivity.workout_id == Workout.id)
        .where(
            Workout.user_id == user_id,
            EnduranceActivity.activity_type == "RUNNING",
        )
    ).all()

    return [
        {
            "date": parse_day(workout_date).isoformat(),
            "meters": effort["meters"],
            "seconds": effort["seconds"],
        }
        for workout_date, efforts in rows
        if parse_day(workout_date) >= since
        for effort in json.loads(efforts)
        if effort["meters"] >= BEST_RUN_MINIMUM_METERS
    ]


def estimates(db: Session, user_id: int, today: date | None = None) -> dict:
    workouts = load_workouts(db, user_id)
    limits = heart_rate_limits(db, user_id, workouts)
    series = fitness_series(workouts, limits, today)
    cutoff = (today or date.today()) - timedelta(days=BEST_RUN_WINDOW_DAYS)

    return {
        "max_heart_rate": limits[0],
        "running_index": running_index_summary(workouts),
        "best_run": best_recent_run(
            workouts,
            today,
            _recent_run_efforts(db, user_id, cutoff),
        ),
        "fitness": series[-1] if series else None,
        "fitness_series": series,
    }
