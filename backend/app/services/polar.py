"""Polar AccessLink API v3: linking an account and fetching exercises.

Reference: https://www.polar.com/accesslink-api/
The API only returns exercises uploaded in the last 30 days, and only those
uploaded after the account was linked.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.endurance_activity import EnduranceActivity
from app.models.polar_account import PolarAccount
from app.models.workout import Workout
from app.schemas.common import speed_in_meters_per_second
from app.services.importers import activity_type_for_sport


TIMEOUT_SECONDS = 30


class PolarError(Exception):
    """Polar refused the request or could not be reached."""


class PolarAuthorizationError(PolarError):
    """The stored token no longer works, so the account must be linked again."""


def _setting(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _api_url() -> str:
    return _setting("POLAR_API_URL", "https://www.polaraccesslink.com").rstrip("/")


def is_configured() -> bool:
    return bool(_setting("POLAR_CLIENT_ID") and _setting("POLAR_CLIENT_SECRET"))


def authorization_url(state: str) -> str:
    # No redirect_uri: Polar then uses the one registered with the API client.
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": _setting("POLAR_CLIENT_ID"),
            "scope": "accesslink.read_all",
            "state": state,
        }
    )

    base = _setting("POLAR_AUTH_URL", "https://flow.polar.com/oauth2/authorization")

    return f"{base}?{query}"


def _request(request: urllib.request.Request) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except OSError as error:
        raise PolarError(f"Polar is niet bereikbaar: {error}") from error


def exchange_code(code: str) -> tuple[str, str | None]:
    """Trades the one-time code for an access token. Returns (token, user id)."""
    credentials = base64.b64encode(
        f"{_setting('POLAR_CLIENT_ID')}:{_setting('POLAR_CLIENT_SECRET')}".encode()
    ).decode()

    request = urllib.request.Request(
        _setting("POLAR_TOKEN_URL", "https://polarremote.com/v2/oauth2/token"),
        data=urllib.parse.urlencode(
            {"grant_type": "authorization_code", "code": code}
        ).encode(),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )

    status, body = _request(request)

    if status != 200:
        raise PolarError(f"Polar weigerde de koppeling (status {status})")

    try:
        token = json.loads(body)
        return token["access_token"], str(token.get("x_user_id") or "") or None
    except (ValueError, KeyError, TypeError) as error:
        raise PolarError("Polar gaf een onverwacht antwoord") from error


def register_user(access_token: str, member_id: str) -> None:
    """Exercises are only available after registering. 409: already registered."""
    request = urllib.request.Request(
        f"{_api_url()}/v3/users",
        data=json.dumps({"member-id": member_id}).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    status, _ = _request(request)

    if status == 403:
        raise PolarError(
            "Polar vraagt eerst je toestemming. Aanvaard de voorwaarden in "
            "Polar Flow en koppel opnieuw."
        )

    if status not in (200, 201, 409):
        raise PolarError(f"Registreren bij Polar mislukte (status {status})")


def list_exercises(access_token: str) -> list[dict]:
    request = urllib.request.Request(
        f"{_api_url()}/v3/exercises",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    status, body = _request(request)

    if status in (401, 403):
        raise PolarAuthorizationError(
            "Polar accepteert de koppeling niet meer. Koppel je account opnieuw."
        )

    if status == 429:
        raise PolarError("Te veel verzoeken aan Polar. Probeer het later opnieuw.")

    if status == 204:
        return []

    if status != 200:
        raise PolarError(f"Ophalen bij Polar mislukte (status {status})")

    try:
        exercises = json.loads(body)
    except ValueError as error:
        raise PolarError("Polar gaf een onverwacht antwoord") from error

    if not isinstance(exercises, list):
        raise PolarError("Polar gaf een onverwacht antwoord")

    return exercises


def parse_duration(value: str | None) -> int | None:
    """ISO 8601 duration, such as PT1H2M3.5S, in whole seconds."""
    match = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?",
        value or "",
    )

    if not match or value == "PT":
        return None

    hours, minutes, seconds = match.groups()

    return round(
        int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)
    )


def _field(exercise: dict, name: str):
    # Polar's documentation mixes "running-index" with "start_time" style names.
    if name in exercise:
        return exercise[name]

    return exercise.get(name.replace("_", "-"))


def _local_start(exercise: dict) -> str:
    """Polar's start time is already local to where the training happened."""
    start = _field(exercise, "start_time")

    try:
        parsed = datetime.fromisoformat(start)
    except (TypeError, ValueError) as error:
        raise PolarError("Polar gaf een training zonder geldige starttijd") from error

    return parsed.replace(tzinfo=None, microsecond=0).isoformat()


def _heart_rate(exercise: dict, name: str) -> int | None:
    rates = _field(exercise, "heart_rate") or {}
    value = rates.get(name)

    return round(value) if value else None


def _store(db: Session, user_id: int, exercise: dict) -> str:
    """Stores one exercise. Returns 'imported', 'updated' or 'skipped'."""
    source_hash = f"polar:{exercise['id']}"

    if db.scalar(select(Workout.id).where(Workout.source_hash == source_hash)):
        return "skipped"

    start = _local_start(exercise)
    running_index = _field(exercise, "running_index")

    # The same training may already be here from an uploaded TCX file. Polar
    # adds what such a file lacks, without counting the training twice.
    existing = db.scalar(
        select(Workout).where(Workout.user_id == user_id, Workout.date == start)
    )

    if existing is not None:
        if running_index and existing.endurance_activity:
            existing.endurance_activity.running_index = running_index
            return "updated"

        return "skipped"

    sport = " ".join(
        str(_field(exercise, name) or "") for name in ("sport", "detailed_sport_info")
    )
    seconds = parse_duration(_field(exercise, "duration"))

    if "STRENGTH" in sport.upper():
        db.add(
            Workout(
                user_id=user_id,
                date=start,
                duration=seconds,
                type="STRENGTH",
                source_hash=source_hash,
                notes="Geïmporteerd uit Polar",
            )
        )
        return "imported"

    distance = _field(exercise, "distance")

    db.add(
        Workout(
            user_id=user_id,
            date=start,
            duration=seconds,
            type="ENDURANCE",
            source_hash=source_hash,
            endurance_activity=EnduranceActivity(
                activity_type=activity_type_for_sport(sport),
                distance=distance,
                duration=seconds,
                average_speed=speed_in_meters_per_second(distance, seconds),
                average_heart_rate=_heart_rate(exercise, "average"),
                max_heart_rate=_heart_rate(exercise, "maximum"),
                calories=_field(exercise, "calories"),
                running_index=running_index,
            ),
        )
    )

    return "imported"


def sync(db: Session, user_id: int) -> dict:
    account = db.get(PolarAccount, user_id)

    if account is None:
        raise PolarAuthorizationError("Er is nog geen Polar-account gekoppeld")

    counts = {"imported": 0, "updated": 0, "skipped": 0}

    for exercise in list_exercises(account.access_token):
        counts[_store(db, user_id, exercise)] += 1
        db.flush()

    account.last_sync_at = datetime.now().isoformat(timespec="seconds")
    db.commit()

    return counts
