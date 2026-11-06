"""Totals, records and trends per sport."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.workout import Workout
from app.services.analytics import estimated_one_rep_max, parse_day
from app.services.estimates import effort_score, heart_rate_limits, load_workouts


STRENGTH = "STRENGTH"
CHART_WEEKS = 26
TREND_DAYS = 28

# The shortest distance at which a pace says something, in meters.
FASTEST_MINIMUM = {"RUNNING": 3000, "CYCLING": 10000, "SWIMMING": 400}

SPORT_ORDER = ["RUNNING", "CYCLING", "SWIMMING", STRENGTH, "OTHER"]


def _sport(workout: Workout) -> str:
    if workout.endurance_activity:
        return workout.endurance_activity.activity_type

    return STRENGTH


def _seconds(workout: Workout) -> int:
    activity = workout.endurance_activity

    return (activity.duration if activity else None) or workout.duration or 0


def _strength_totals(workouts: list[Workout]) -> dict:
    volume = 0.0
    sets = 0
    reps = 0
    best: dict | None = None

    for workout in workouts:
        for item in workout.exercises:
            for exercise_set in item.sets:
                if not exercise_set.weight or not exercise_set.reps:
                    continue

                sets += 1
                reps += exercise_set.reps
                volume += exercise_set.weight * exercise_set.reps
                estimate = estimated_one_rep_max(exercise_set.weight, exercise_set.reps)

                if best is None or estimate > best["estimated_1rm_kg"]:
                    best = {
                        "exercise": item.exercise.name,
                        "estimated_1rm_kg": round(estimate, 1),
                        "date": parse_day(workout.date).isoformat(),
                    }

    return {"volume_kg": round(volume), "sets": sets, "reps": reps, "best_lift": best}


def _summary(sport: str, workouts: list[Workout], limits: tuple[int, int]) -> dict:
    activities = [w.endurance_activity for w in workouts if w.endurance_activity]

    distance = sum(activity.distance or 0 for activity in activities)
    seconds = sum(_seconds(workout) for workout in workouts)

    # Speed only over activities that have both, or a swim without distance
    # would make every other swim look slow.
    moving = [a for a in activities if a.distance and a.duration]
    moving_distance = sum(a.distance for a in moving)
    moving_seconds = sum(a.duration for a in moving)

    timed_rates = [
        (a.average_heart_rate, a.duration)
        for a in activities
        if a.average_heart_rate and a.duration
    ]
    rate_seconds = sum(seconds for _, seconds in timed_rates)

    longest = None
    fastest = None
    minimum = FASTEST_MINIMUM.get(sport)

    for workout in workouts:
        activity = workout.endurance_activity
        day = parse_day(workout.date).isoformat()

        if activity and activity.distance:
            if longest is None or activity.distance > longest["distance"]:
                longest = {"date": day, "distance": activity.distance}

            if (
                minimum
                and activity.duration
                and activity.distance >= minimum
            ):
                speed = activity.distance / activity.duration

                if fastest is None or speed > fastest["speed"]:
                    fastest = {
                        "date": day,
                        "speed": round(speed, 3),
                        "distance": activity.distance,
                        "duration": activity.duration,
                    }

    indexes = [a.running_index for a in activities if a.running_index]

    return {
        "sport": sport,
        "sessions": len(workouts),
        "duration_seconds": seconds,
        "distance_meters": round(distance, 1),
        "elevation_gain": round(sum(a.elevation_gain or 0 for a in activities)),
        "calories": sum(a.calories or 0 for a in activities),
        "effort": sum(effort_score(workout, *limits) for workout in workouts),
        "average_speed": (
            round(moving_distance / moving_seconds, 3) if moving_seconds else None
        ),
        "average_heart_rate": (
            round(sum(rate * seconds for rate, seconds in timed_rates) / rate_seconds)
            if rate_seconds
            else None
        ),
        "longest": longest,
        "fastest": fastest,
        "best_running_index": max(indexes, default=None),
        "strength": _strength_totals(workouts) if sport == STRENGTH else None,
    }


def _weekly(workouts: list[Workout], today: date) -> list[dict]:
    this_week = today - timedelta(days=today.weekday())
    first = this_week - timedelta(weeks=CHART_WEEKS - 1)

    weeks = {
        first + timedelta(weeks=index): {
            "sessions": 0,
            "distance_meters": 0.0,
            "duration_seconds": 0,
        }
        for index in range(CHART_WEEKS)
    }

    for workout in workouts:
        day = parse_day(workout.date)
        week = weeks.get(day - timedelta(days=day.weekday()))

        if week is not None:
            activity = workout.endurance_activity
            week["sessions"] += 1
            week["duration_seconds"] += _seconds(workout)
            week["distance_meters"] += (activity.distance or 0) if activity else 0

    return [
        {"week_start": week_start.isoformat(), **values}
        for week_start, values in sorted(weeks.items())
    ]


def sport_breakdown(
    db: Session,
    user_id: int,
    days: int | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    workouts = load_workouts(db, user_id)
    limits = heart_rate_limits(db, user_id, workouts)

    cutoff = today - timedelta(days=days) if days else None
    trend_start = today - timedelta(days=TREND_DAYS)
    previous_start = trend_start - timedelta(days=TREND_DAYS)

    by_sport: dict[str, list[Workout]] = {}

    for workout in workouts:
        by_sport.setdefault(_sport(workout), []).append(workout)

    total_seconds = sum(
        _seconds(workout)
        for workout in workouts
        if cutoff is None or parse_day(workout.date) > cutoff
    )

    sports = []

    for sport in SPORT_ORDER:
        everything = by_sport.get(sport)

        if not everything:
            continue

        selected = [
            workout
            for workout in everything
            if cutoff is None or parse_day(workout.date) > cutoff
        ]

        summary = _summary(sport, selected, limits)
        summary["share_of_time"] = (
            round(summary["duration_seconds"] / total_seconds, 3)
            if total_seconds
            else 0
        )

        # Always the same recent windows, so the trend does not change with the filter.
        summary["last_28_days"] = sum(
            trend_start < parse_day(w.date) <= today for w in everything
        )
        summary["previous_28_days"] = sum(
            previous_start < parse_day(w.date) <= trend_start for w in everything
        )
        summary["weekly"] = _weekly(everything, today)

        sports.append(summary)

    return {"days": days, "sports": sports}
