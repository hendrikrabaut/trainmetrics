"""Zones, best efforts, the performance chart and the look back on a year."""
import json
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.endurance_activity import EnduranceActivity
from app.models.race import Race
from app.models.workout import Workout
from app.models.workout_stream import WorkoutStream
from app.services.analytics import parse_day
from app.services.estimates import (
    effort_for,
    effort_score,
    fitness_series,
    heart_rate_limits,
    load_workouts,
)
from app.services.plans import active_plan


ZONE_COUNT = 5
TOP_EFFORTS = 3
ACTIVE_SPORT_SPEED = {"RUNNING": 2.8, "CYCLING": 7.0, "SWIMMING": 0.6, "OTHER": 1.3}
HISTORY_DAYS = 180


def _stream_rows(db: Session, user_id: int, column):
    return db.execute(
        select(
            Workout.id,
            Workout.date,
            EnduranceActivity.activity_type,
            column,
        )
        .join(WorkoutStream, WorkoutStream.workout_id == Workout.id)
        .outerjoin(EnduranceActivity, EnduranceActivity.workout_id == Workout.id)
        .where(Workout.user_id == user_id)
        .order_by(Workout.date)
    ).all()


def zone_summary(
    db: Session,
    user_id: int,
    weeks: int = 12,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    this_week = today - timedelta(days=today.weekday())
    first_week = this_week - timedelta(weeks=weeks - 1)

    totals = [0] * ZONE_COUNT
    per_week = {
        first_week + timedelta(weeks=index): [0] * ZONE_COUNT
        for index in range(weeks)
    }

    for _, workout_date, _, zones in _stream_rows(db, user_id, WorkoutStream.zones):
        day = parse_day(workout_date)
        week = per_week.get(day - timedelta(days=day.weekday()))

        if week is None:
            continue

        for index, zone in enumerate(json.loads(zones)[:ZONE_COUNT]):
            seconds = zone.get("seconds") or 0
            week[index] += seconds
            totals[index] += seconds

    total = sum(totals)

    return {
        "weeks": weeks,
        "zones": [
            {
                "zone": index + 1,
                "seconds": seconds,
                "share": round(seconds / total, 3) if total else 0,
            }
            for index, seconds in enumerate(totals)
        ],
        "easy_share": round(sum(totals[:2]) / total, 3) if total else None,
        "per_week": [
            {
                "week_start": week.isoformat(),
                "seconds": sum(values),
                # Zones 1 and 2 are what endurance training calls easy.
                "easy_share": (
                    round(sum(values[:2]) / sum(values), 3) if sum(values) else None
                ),
            }
            for week, values in sorted(per_week.items())
        ],
    }


def best_efforts(db: Session, user_id: int) -> list[dict]:
    """Per sport and distance, the fastest few times with their workout."""
    found: dict[tuple, list] = defaultdict(list)

    rows = _stream_rows(db, user_id, WorkoutStream.best_efforts)

    for workout_id, workout_date, sport, efforts in rows:
        for effort in json.loads(efforts):
            found[(sport, effort["meters"])].append(
                {
                    "seconds": effort["seconds"],
                    "date": parse_day(workout_date).isoformat(),
                    "workout_id": workout_id,
                }
            )

    return [
        {
            "sport": sport,
            "meters": meters,
            "best": sorted(times, key=lambda time: time["seconds"])[:TOP_EFFORTS],
        }
        for (sport, meters), times in sorted(found.items())
    ]


def _planned_load(session, limits) -> int:
    """What a planned session will roughly cost, for looking ahead."""
    seconds = session.duration

    if not seconds and session.distance:
        seconds = session.distance / ACTIVE_SPORT_SPEED.get(session.sport, 2.5)

    return effort_for(seconds or 2700, None, session.sport != "STRENGTH", limits)


def performance_chart(db: Session, user_id: int, today: date | None = None) -> dict:
    """History of fitness, fatigue and form, and where the plan leads them."""
    today = today or date.today()
    workouts = load_workouts(db, user_id)
    limits = heart_rate_limits(db, user_id, workouts)
    history = fitness_series(workouts, limits, today, days=HISTORY_DAYS)

    races = db.scalars(
        select(Race).where(Race.user_id == user_id).order_by(Race.date)
    ).all()

    projection = []
    plan = active_plan(db, user_id)

    if history and plan:
        planned: dict[str, int] = defaultdict(int)

        for session in plan.sessions:
            if session.date > today.isoformat():
                planned[session.date] += _planned_load(session, limits)

        last_day = max(
            [parse_day(day) for day in planned]
            + [parse_day(race.date) for race in races if race.date >= today.isoformat()]
            + [today]
        )

        fitness = history[-1]["fitness"]
        fatigue = history[-1]["fatigue"]
        day = today + timedelta(days=1)

        while day <= last_day:
            load = planned.get(day.isoformat(), 0)
            fitness += (load - fitness) / 42
            fatigue += (load - fatigue) / 7

            projection.append(
                {
                    "date": day.isoformat(),
                    "fitness": round(fitness, 1),
                    "fatigue": round(fatigue, 1),
                    "form": round(fitness - fatigue, 1),
                }
            )

            day += timedelta(days=1)

    return {
        "history": history,
        "projection": projection,
        "races": [
            {
                "name": race.name,
                "date": race.date,
                "priority": race.priority,
                "form": next(
                    (
                        row["form"]
                        for row in history + projection
                        if row["date"] == race.date
                    ),
                    None,
                ),
            }
            for race in races
        ],
    }


def year_review(db: Session, user_id: int, year: int) -> dict:
    workouts = [
        workout
        for workout in load_workouts(db, user_id)
        if parse_day(workout.date).year == year
    ]
    everything = load_workouts(db, user_id)
    years = sorted({parse_day(workout.date).year for workout in everything}, reverse=True)
    limits = heart_rate_limits(db, user_id, everything)

    sports: dict[str, dict] = {}
    per_day: dict[str, int] = defaultdict(int)
    weeks: dict[str, dict] = defaultdict(lambda: {"seconds": 0, "meters": 0.0})
    months = [{"month": number + 1, "seconds": 0, "meters": 0.0} for number in range(12)]
    total_seconds = 0
    total_meters = 0.0
    total_ascent = 0.0
    longest = None
    hardest = None

    for workout in workouts:
        day = parse_day(workout.date)
        activity = workout.endurance_activity
        seconds = (activity.duration if activity else None) or workout.duration or 0
        meters = (activity.distance or 0) if activity else 0
        sport = activity.activity_type if activity else "STRENGTH"
        effort = effort_score(workout, *limits)

        total_seconds += seconds
        total_meters += meters
        total_ascent += (activity.elevation_gain or 0) if activity else 0
        per_day[day.isoformat()] += effort

        week = (day - timedelta(days=day.weekday())).isoformat()
        weeks[week]["seconds"] += seconds
        weeks[week]["meters"] += meters

        months[day.month - 1]["seconds"] += seconds
        months[day.month - 1]["meters"] += meters

        row = sports.setdefault(
            sport,
            {"sport": sport, "sessions": 0, "seconds": 0, "meters": 0.0},
        )
        row["sessions"] += 1
        row["seconds"] += seconds
        row["meters"] += meters

        if meters and (longest is None or meters > longest["meters"]):
            longest = {"sport": sport, "meters": meters, "date": day.isoformat()}

        if hardest is None or effort > hardest["effort"]:
            hardest = {"sport": sport, "effort": effort, "date": day.isoformat()}

    busiest = max(weeks.items(), key=lambda item: item[1]["seconds"], default=None)

    return {
        "year": year,
        "years": years,
        "workouts": len(workouts),
        "active_days": len(per_day),
        "active_weeks": len(weeks),
        "seconds": total_seconds,
        "meters": round(total_meters, 1),
        "ascent": round(total_ascent),
        "sports": sorted(sports.values(), key=lambda row: -row["seconds"]),
        "months": months,
        "days": dict(per_day),
        "longest": longest,
        "hardest": hardest,
        "busiest_week": (
            {"week_start": busiest[0], **busiest[1]} if busiest else None
        ),
        "first_date": min(per_day, default=None),
        "last_date": max(per_day, default=None),
    }
