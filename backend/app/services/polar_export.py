"""Imports the "Download your data" archive from account.polar.com.

Training sessions, the profile values stored with them, sleep and nightly
recovery are read. The archive also holds daily activity and continuous heart
rate, which this app has no place for yet.
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.body_measurement import BodyMeasurement
from app.models.endurance_activity import EnduranceActivity
from app.models.user import User
from app.models.workout import Workout
from app.schemas.common import speed_in_meters_per_second
from app.services.polar import parse_duration
from app.services.routes import store_route
from app.services.sleep import store_night


STRENGTH = "STRENGTH"

# The archive only has numeric sport ids, and Polar publishes no list of them.
# These come from a real export and were confirmed by its owner: 23 is pool
# swimming, 105 is open water swimming and 3 is walking, for which this app has
# no sport of its own.
SPORTS = {
    "1": "RUNNING",
    "2": "CYCLING",
    "3": "OTHER",
    "15": STRENGTH,
    "23": "SWIMMING",
    "38": "CYCLING",
    "105": "SWIMMING",
}

# GPS noise, not a distance: a workout without movement can report a few meters.
MINIMUM_DISTANCE_METERS = 10


def _whole(value) -> int | None:
    return None if value is None else round(value)


def _store_exercise_route(
    db: Session,
    workout_id: int,
    exercise: dict,
    counts: dict,
) -> None:
    route = (exercise.get("routes") or {}).get("route") or {}
    points = [
        (point.get("latitude"), point.get("longitude"))
        for point in route.get("wayPoints") or []
    ]

    if store_route(db, workout_id, points):
        counts["routes"] += 1


def _store_exercise(
    db: Session,
    user_id: int,
    session: dict,
    exercise: dict,
    counts: dict,
) -> None:
    source_hash = f"polar-export:{exercise['identifier']['id']}"
    known_id = db.scalar(select(Workout.id).where(Workout.source_hash == source_hash))

    if known_id:
        _store_exercise_route(db, known_id, exercise, counts)
        counts["skipped"] += 1
        return

    start = exercise["startTime"][:19]
    running_index = exercise.get("runningIndex")

    # The same training can already be here through the Polar API or a file.
    existing = db.scalar(
        select(Workout).where(Workout.user_id == user_id, Workout.date == start)
    )

    if existing is not None:
        if running_index and existing.endurance_activity:
            existing.endurance_activity.running_index = running_index

        _store_exercise_route(db, existing.id, exercise, counts)
        counts["skipped"] += 1
        return

    sport_id = exercise.get("sport", {}).get("id") or session["sport"]["id"]
    sport = SPORTS.get(str(sport_id))

    if sport is None:
        counts["unknown_sports"].add(str(sport_id))
        sport = "OTHER"

    seconds = round(exercise["durationMillis"] / 1000)

    if sport == STRENGTH:
        db.add(
            Workout(
                user_id=user_id,
                date=start,
                duration=seconds,
                type=STRENGTH,
                source_hash=source_hash,
                notes="Geïmporteerd uit Polar, zonder oefeningen en sets",
            )
        )
        counts["imported"] += 1
        return

    distance = exercise.get("distanceMeters")

    if distance is not None and distance < MINIMUM_DISTANCE_METERS:
        distance = None

    # Heart rate is stored per session, so it only fits a one-sport session.
    single_sport = len(session["exercises"]) == 1

    workout = Workout(
            user_id=user_id,
            date=start,
            duration=seconds,
            type="ENDURANCE",
            source_hash=source_hash,
            endurance_activity=EnduranceActivity(
                activity_type=sport,
                distance=round(distance, 1) if distance is not None else None,
                duration=seconds,
                average_speed=speed_in_meters_per_second(distance, seconds),
                average_heart_rate=(
                    _whole(session.get("hrAvg")) if single_sport else None
                ),
                max_heart_rate=(
                    _whole(session.get("hrMax")) if single_sport else None
                ),
                elevation_gain=exercise.get("ascentMeters"),
                calories=_whole(exercise.get("calories")),
                running_index=running_index,
            ),
    )
    db.add(workout)
    db.flush()
    _store_exercise_route(db, workout.id, exercise, counts)
    counts["imported"] += 1


def _store_weights(db: Session, user_id: int, sessions: list[dict], counts: dict) -> None:
    """One measurement per change of the weight in the Polar profile."""
    existing_days = {
        day[:10]
        for day in db.scalars(
            select(BodyMeasurement.date).where(BodyMeasurement.user_id == user_id)
        )
    }
    previous = None

    for session in sessions:
        weight = session.get("physicalInformation", {}).get("weightKg")

        if weight is None or weight == previous:
            continue

        previous = weight
        day = session["startTime"][:10]

        if day not in existing_days:
            db.add(
                BodyMeasurement(
                    user_id=user_id,
                    date=day,
                    weight=weight,
                    notes="Uit je Polar-profiel",
                )
            )
            counts["weights"] += 1


def _read_list(folder: Path, pattern: str) -> list[dict]:
    rows = []

    for file in sorted(folder.glob(pattern)):
        data = json.loads(file.read_text(encoding="utf-8"))

        if isinstance(data, list):
            rows += data

    return rows


def _per_minute(milliseconds) -> float | None:
    """Beats or breaths a minute, from the average time between two of them."""
    return 60000 / milliseconds if milliseconds else None


def _store_sleep(db: Session, user_id: int, folder: Path, counts: dict) -> None:
    nights = set()

    for row in _read_list(folder, "sleep_result_*.json"):
        evaluation = row.get("evaluation", {})
        phases = evaluation.get("phaseDurations", {})
        hypnogram = row.get("sleepResult", {}).get("hypnogram", {})
        nights.add(row["night"])

        store_night(
            db,
            user_id,
            row["night"],
            {
                "sleep_start": (hypnogram.get("sleepStart") or "")[:19] or None,
                "sleep_end": (hypnogram.get("sleepEnd") or "")[:19] or None,
                "asleep_seconds": parse_duration(evaluation.get("asleepDuration")),
                "light_seconds": parse_duration(phases.get("light")),
                "deep_seconds": parse_duration(phases.get("deep")),
                "rem_seconds": parse_duration(phases.get("rem")),
                "interruption_seconds": parse_duration(
                    evaluation.get("interruptions", {}).get("totalDuration")
                ),
                "continuity": evaluation.get("analysis", {}).get("continuityIndex"),
            },
        )
        db.flush()

    for row in _read_list(folder, "sleep_score_*.json"):
        nights.add(row["night"])
        store_night(
            db,
            user_id,
            row["night"],
            {"sleep_score": row.get("sleepScoreResult", {}).get("sleepScore")},
        )
        db.flush()

    for row in _read_list(folder, "nightly_recovery_6*.json"):
        nights.add(row["night"])
        store_night(
            db,
            user_id,
            row["night"],
            {
                "hrv_ms": row.get("meanNightlyRecoveryRmssd") or None,
                "heart_rate": _per_minute(row.get("meanNightlyRecoveryRri")),
                "breathing_rate": _per_minute(
                    row.get("meanNightlyRecoveryRespirationInterval")
                ),
            },
        )
        db.flush()

    counts["nights"] = len(nights)


def import_export(db: Session, user_id: int, folder: Path) -> dict:
    """Safe to run again: what is already there is skipped."""
    files = sorted(folder.glob("training-session_*.json"))

    if not files:
        raise ValueError(f"Geen training-session-bestanden gevonden in {folder}")

    sessions = [json.loads(file.read_text(encoding="utf-8")) for file in files]
    sessions.sort(key=lambda session: session["startTime"])

    counts = {
        "imported": 0,
        "skipped": 0,
        "weights": 0,
        "nights": 0,
        "routes": 0,
        "unknown_sports": set(),
    }

    for session in sessions:
        for exercise in session["exercises"]:
            _store_exercise(db, user_id, session, exercise, counts)
            db.flush()

    _store_weights(db, user_id, sessions, counts)
    _store_sleep(db, user_id, folder, counts)

    # The latest session holds the current values from the user's profile.
    physical = sessions[-1].get("physicalInformation", {})
    user = db.get(User, user_id)

    if user is None:
        raise ValueError(f"Gebruiker {user_id} bestaat niet")

    user.max_heart_rate = physical.get("maximumHeartRate") or user.max_heart_rate
    user.resting_heart_rate = physical.get("restingHeartRate") or user.resting_heart_rate

    db.commit()

    counts["unknown_sports"] = sorted(counts["unknown_sports"])

    return counts
