"""Imports the "Download your data" archive from account.polar.com.

Only training sessions and the profile values stored with them are read. The
archive also holds daily activity, sleep and continuous heart rate, which this
app has no place for yet.
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


def _store_exercise(
    db: Session,
    user_id: int,
    session: dict,
    exercise: dict,
    counts: dict,
) -> None:
    source_hash = f"polar-export:{exercise['identifier']['id']}"

    if db.scalar(select(Workout.id).where(Workout.source_hash == source_hash)):
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

    db.add(
        Workout(
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
    )
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


def import_export(db: Session, user_id: int, folder: Path) -> dict:
    """Safe to run again: what is already there is skipped."""
    files = sorted(folder.glob("training-session_*.json"))

    if not files:
        raise ValueError(f"Geen training-session-bestanden gevonden in {folder}")

    sessions = [json.loads(file.read_text(encoding="utf-8")) for file in files]
    sessions.sort(key=lambda session: session["startTime"])

    counts = {"imported": 0, "skipped": 0, "weights": 0, "unknown_sports": set()}

    for session in sessions:
        for exercise in session["exercises"]:
            _store_exercise(db, user_id, session, exercise, counts)
            db.flush()

    _store_weights(db, user_id, sessions, counts)

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
