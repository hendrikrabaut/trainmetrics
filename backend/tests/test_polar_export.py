import json

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.user import User
from app.services.polar_export import import_export


def _session(
    identifier,
    start,
    sport="1",
    distance=5000.0,
    weight=94.0,
    max_heart_rate=199,
    running_index=None,
):
    exercise = {
        "identifier": {"id": identifier},
        "startTime": start,
        "durationMillis": 1500000,
        "calories": 300,
        "sport": {"id": sport},
        "ascentMeters": 12.5,
    }

    if distance is not None:
        exercise["distanceMeters"] = distance

    if running_index:
        exercise["runningIndex"] = running_index

    return {
        "startTime": start,
        "hrAvg": 150,
        "hrMax": 175,
        "sport": {"id": sport},
        "physicalInformation": {
            "weightKg": weight,
            "maximumHeartRate": max_heart_rate,
            "restingHeartRate": 55,
        },
        "exercises": [exercise],
    }


def _write(folder, *sessions):
    for index, session in enumerate(sessions):
        name = f"training-session_{index}.json"
        (folder / name).write_text(json.dumps(session), encoding="utf-8")


def _import(folder):
    with SessionLocal() as db:
        return import_export(db, 1, folder)


def test_sessions_are_normalized(client, tmp_path):
    _write(tmp_path, _session("a", "2026-05-17T10:00:00.000", running_index=47))

    assert _import(tmp_path)["imported"] == 1

    workout = client.get("/api/workouts/").json()[0]
    activity = workout["endurance_activity"]

    assert workout["date"] == "2026-05-17T10:00:00"
    assert workout["duration"] == 1500
    assert activity["activity_type"] == "RUNNING"
    assert activity["distance"] == 5000
    assert activity["average_speed"] == 3.33
    assert activity["average_heart_rate"] == 150
    assert activity["max_heart_rate"] == 175
    assert activity["elevation_gain"] == 12.5
    assert activity["calories"] == 300
    assert activity["running_index"] == 47


@pytest.mark.parametrize(
    "sport, expected",
    [
        ("1", "RUNNING"),
        ("2", "CYCLING"),
        ("38", "CYCLING"),
        ("23", "SWIMMING"),
        ("105", "SWIMMING"),
        ("3", "OTHER"),
    ],
)
def test_sports_are_mapped(client, tmp_path, sport, expected):
    _write(tmp_path, _session("a", "2026-05-17T10:00:00", sport=sport))
    _import(tmp_path)

    activity = client.get("/api/workouts/").json()[0]["endurance_activity"]

    assert activity["activity_type"] == expected


def test_strength_becomes_a_strength_workout(client, tmp_path):
    _write(tmp_path, _session("a", "2026-06-03T14:35:00", sport="15", distance=None))
    _import(tmp_path)

    workout = client.get("/api/workouts/").json()[0]

    assert workout["type"] == "STRENGTH"
    assert workout["endurance_activity"] is None
    assert workout["duration"] == 1500


def test_an_unknown_sport_is_kept_and_reported(client, tmp_path):
    _write(tmp_path, _session("a", "2026-05-17T10:00:00", sport="999"))

    assert _import(tmp_path)["unknown_sports"] == ["999"]
    assert client.get("/api/workouts/").json()[0]["endurance_activity"]["activity_type"] == "OTHER"


def test_gps_noise_is_not_a_distance(client, tmp_path):
    _write(tmp_path, _session("a", "2026-07-09T17:10:57", sport="105", distance=2.1))
    _import(tmp_path)

    activity = client.get("/api/workouts/").json()[0]["endurance_activity"]

    assert activity["distance"] is None
    assert activity["average_speed"] is None


def test_running_it_twice_changes_nothing(client, tmp_path):
    _write(
        tmp_path,
        _session("a", "2026-05-17T10:00:00"),
        _session("b", "2026-05-18T10:00:00", weight=93.0),
    )

    first = _import(tmp_path)
    second = _import(tmp_path)

    assert first["imported"] == 2
    assert first["weights"] == 2
    assert second["imported"] == 0
    assert second["skipped"] == 2
    assert second["weights"] == 0
    assert len(client.get("/api/workouts/").json()) == 2
    assert len(client.get("/api/body-measurements/").json()) == 2


def test_the_same_training_from_the_api_is_enriched_not_doubled(client, tmp_path):
    client.post(
        "/api/workouts/complete",
        json={
            "user_id": 1,
            "date": "2026-05-17T10:00:00",
            "type": "ENDURANCE",
            "endurance_activity": {"activity_type": "RUNNING", "distance": 5000},
        },
    )
    _write(tmp_path, _session("a", "2026-05-17T10:00:00", running_index=47))

    assert _import(tmp_path)["imported"] == 0

    workouts = client.get("/api/workouts/").json()

    assert len(workouts) == 1
    assert workouts[0]["endurance_activity"]["running_index"] == 47


def test_weight_is_only_measured_when_it_changes(client, tmp_path):
    _write(
        tmp_path,
        _session("a", "2026-05-01T10:00:00", weight=97.0),
        _session("b", "2026-05-02T10:00:00", weight=97.0),
        _session("c", "2026-05-03T10:00:00", weight=96.0),
    )
    _import(tmp_path)

    weights = client.get("/api/analytics/body-weight").json()

    assert weights == [
        {"date": "2026-05-01", "weight_kg": 97.0},
        {"date": "2026-05-03", "weight_kg": 96.0},
    ]


def test_the_latest_heart_rates_are_used_for_effort(client, tmp_path):
    _write(
        tmp_path,
        _session("a", "2026-05-01T10:00:00", max_heart_rate=198),
        _session("b", "2026-05-02T10:00:00", max_heart_rate=199),
    )
    _import(tmp_path)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == 1))
        assert user.max_heart_rate == 199
        assert user.resting_heart_rate == 55

    assert client.get("/api/analytics/estimates").json()["max_heart_rate"] == 199


def test_a_folder_without_sessions_is_refused(tmp_path):
    with pytest.raises(ValueError):
        _import(tmp_path)
