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


def _write_sleep(folder):
    (folder / "sleep_result_1-a.json").write_text(json.dumps([{
        "night": "2026-05-05",
        "evaluation": {
            "asleepDuration": "PT6H17M30S",
            "analysis": {"continuityIndex": 4.3},
            "interruptions": {"totalDuration": "PT20M30S"},
            "phaseDurations": {"rem": "PT1H23M", "light": "PT3H33M", "deep": "PT1H21M30S"},
        },
        "sleepResult": {"hypnogram": {
            "sleepStart": "2026-05-05T00:23:26.338+02:00",
            "sleepEnd": "2026-05-05T07:01:26.338+02:00",
        }},
    }]), encoding="utf-8")
    (folder / "sleep_score_1-b.json").write_text(json.dumps([
        {"night": "2026-05-05", "sleepScoreResult": {"sleepScore": 72.8}},
    ]), encoding="utf-8")
    (folder / "nightly_recovery_1234-c.json").write_text(json.dumps([{
        "night": "2026-05-05",
        "meanNightlyRecoveryRri": 1000,
        "meanNightlyRecoveryRmssd": 79,
        "meanNightlyRecoveryRespirationInterval": 4000,
    }]), encoding="utf-8")
    # Holds raw samples, not one row per night in this form.
    (folder / "nightly_recovery_blob_1-d.json").write_text(
        json.dumps([{"hrvData": []}]), encoding="utf-8"
    )


def test_sleep_and_recovery_are_combined_per_night(client, tmp_path):
    _write(tmp_path, _session("a", "2026-05-17T10:00:00"))
    _write_sleep(tmp_path)

    assert _import(tmp_path)["nights"] == 1

    night = client.get("/api/analytics/sleep").json()["last_night"]

    assert night["asleep_seconds"] == 22650
    assert night["light_seconds"] == 12780
    assert night["deep_seconds"] == 4890
    assert night["rem_seconds"] == 4980
    assert night["interruption_seconds"] == 1230
    assert night["sleep_score"] == 73
    assert night["hrv_ms"] == 79
    assert night["heart_rate"] == 60
    assert night["breathing_rate"] == 15
    assert night["sleep_start"] == "2026-05-05T00:23:26"


def test_importing_sleep_twice_keeps_one_row(client, tmp_path):
    _write(tmp_path, _session("a", "2026-05-17T10:00:00"))
    _write_sleep(tmp_path)
    _import(tmp_path)
    _import(tmp_path)

    assert len(client.get("/api/analytics/sleep").json()["nights"]) == 1


def _with_route(session, count=50):
    session["exercises"][0]["routes"] = {
        "route": {
            "wayPoints": [
                {"latitude": 51 + index * 0.0005, "longitude": 4 + (index % 7) * 0.0003, "elapsedMillis": index * 1000}
                for index in range(count)
            ]
        }
    }
    return session


def test_routes_come_along_also_for_trainings_already_imported(client, tmp_path):
    _write(tmp_path, _session("a", "2026-05-17T10:00:00"))
    _import(tmp_path)

    assert client.get("/api/workouts/").json()[0]["has_route"] is False

    for file in tmp_path.glob("training-session_*"):
        file.unlink()

    _write(tmp_path, _with_route(_session("a", "2026-05-17T10:00:00")))
    result = _import(tmp_path)

    assert result["imported"] == 0
    assert result["routes"] == 1

    workout = client.get("/api/workouts/").json()[0]
    route = client.get(f"/api/workouts/{workout['id']}/route").json()

    assert workout["has_route"] is True
    assert route["points"][0] == [51.0, 4.0]
    assert len(route["points"]) >= 5

    assert _import(tmp_path)["routes"] == 0


def test_a_handful_of_points_is_no_route(client, tmp_path):
    _write(tmp_path, _with_route(_session("a", "2026-07-09T17:10:57", sport="105"), count=4))

    assert _import(tmp_path)["routes"] == 0
    assert client.get("/api/workouts/").json()[0]["has_route"] is False
