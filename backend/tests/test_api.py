from datetime import date, timedelta


def _exercise(client, name="Bench Press"):
    return client.post("/api/exercises/", json={"name": name}).json()["id"]


def _strength(client, exercise_id, day, sets):
    response = client.post(
        "/api/workouts/complete",
        json={
            "date": day,
            "type": "STRENGTH",
            "exercises": [
                {
                    "exercise_id": exercise_id,
                    "exercise_order": 1,
                    "sets": [
                        {"set_number": index, "weight": weight, "reps": reps}
                        for index, (weight, reps) in enumerate(sets, start=1)
                    ],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "TrainMetrics" in response.text


def test_foreign_keys_are_enforced(client):
    response = client.post(
        "/api/workouts/999/exercises",
        json={"exercise_id": 1, "exercise_order": 1},
    )
    assert response.status_code == 404

    workout = client.post(
        "/api/workouts/",
        json={"date": "2026-10-01", "type": "STRENGTH"},
    ).json()
    response = client.post(
        f"/api/workouts/{workout['id']}/exercises",
        json={"exercise_id": 999, "exercise_order": 1},
    )
    assert response.status_code == 409


def test_exercise_in_use_cannot_be_deleted(client):
    exercise_id = _exercise(client)
    _strength(client, exercise_id, "2026-10-01", [(60, 10)])

    assert client.delete(f"/api/exercises/{exercise_id}").status_code == 409


def test_deleting_a_workout_removes_its_children(client):
    exercise_id = _exercise(client)
    workout = _strength(client, exercise_id, "2026-10-01", [(60, 10)])

    assert client.delete(f"/api/workouts/{workout['id']}").status_code == 200
    assert client.get("/api/analytics/records").json() == []


def test_invalid_values_are_rejected(client):
    invalid = [
        {"date": "gisteren", "type": "STRENGTH"},
        {"date": "2026-10-01", "type": "YOGA"},
        {"date": "2026-10-01", "type": "STRENGTH", "duration": -5},
    ]

    for body in invalid:
        assert client.post("/api/workouts/", json=body).status_code == 422


def test_average_speed_is_calculated_in_meters_per_second(client):
    response = client.post(
        "/api/workouts/complete",
        json={
            "date": "2026-10-01",
            "type": "ENDURANCE",
            "endurance_activity": {
                "activity_type": "RUNNING",
                "distance": 10000,
                "duration": 3000,
            },
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["endurance_activity"]["average_speed"] == 3.33


def test_workout_list_includes_details(client):
    exercise_id = _exercise(client)
    _strength(client, exercise_id, "2026-10-01", [(60, 10)])

    workout = client.get("/api/workouts/").json()[0]

    assert workout["exercises"][0]["sets"][0]["weight"] == 60


def test_body_measurement_can_be_created(client):
    response = client.post(
        "/api/body-measurements/",
        json={"date": "2026-10-01", "weight": 90.4},
    )
    assert response.status_code == 200, response.text


def test_there_is_one_profile(client):
    assert client.get("/api/profile/").json()["name"] == "Test"

    response = client.patch("/api/profile/", json={"name": "Nieuw"})
    assert response.json()["name"] == "Nieuw"

    second = client.post("/api/profile/", json={"name": "Twee", "email": "b@example.com"})
    assert second.status_code == 409


def test_no_response_exposes_or_accepts_a_user(client):
    workout = client.post(
        "/api/workouts/",
        json={"user_id": 999, "date": "2026-10-01", "type": "STRENGTH"},
    )

    assert workout.status_code == 200
    assert "user_id" not in workout.json()
    assert client.get("/api/workouts/").json()[0]["id"] == workout.json()["id"]


def test_without_a_profile_the_app_asks_for_one(client):
    from sqlalchemy import text

    from app.database import engine

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))

    assert client.get("/api/profile/").json() is None
    assert client.get("/api/game/profile").status_code == 409

    created = client.post("/api/profile/", json={"name": "Nieuw", "email": "n@example.com"})

    assert created.status_code == 200
    assert client.get("/api/game/profile").status_code == 200


def test_equipment_crud_and_workout_link(client):
    created = client.post(
        "/api/equipment/",
        json={"name": "Polar Ignite 2", "category": "WEARABLE"},
    )
    assert created.status_code == 200, created.text
    equipment_id = created.json()["id"]
    assert created.json()["status"] == "ACTIVE"

    updated = client.patch(f"/api/equipment/{equipment_id}", json={"status": "RETIRED"})
    assert updated.json()["status"] == "RETIRED"

    workout_id = client.post(
        "/api/workouts/",
        json={"date": "2026-10-01", "type": "ENDURANCE"},
    ).json()["id"]

    url = f"/api/workouts/{workout_id}/equipment"
    assert len(client.put(f"{url}/{equipment_id}").json()) == 1
    assert len(client.put(f"{url}/{equipment_id}").json()) == 1
    assert len(client.delete(f"{url}/{equipment_id}").json()) == 0

    assert client.delete(f"/api/equipment/{equipment_id}").status_code == 200
    assert client.get(f"/api/equipment/{equipment_id}").status_code == 404


def test_exercise_progress_and_records(client):
    exercise_id = _exercise(client)
    _strength(client, exercise_id, "2026-09-01", [(60, 10), (65, 8)])
    _strength(client, exercise_id, "2026-09-08 18:00:00", [(70, 1), (0, 10)])

    progress = client.get(f"/api/analytics/exercises/{exercise_id}/progress").json()

    assert progress == [
        {
            "date": "2026-09-01",
            "top_weight_kg": 65,
            "volume_kg": 1120,
            "estimated_1rm_kg": 82.3,
        },
        {
            "date": "2026-09-08",
            "top_weight_kg": 70,
            "volume_kg": 70,
            "estimated_1rm_kg": 70,
        },
    ]

    record = client.get("/api/analytics/records").json()[0]

    assert record["top_weight_kg"] == 70
    assert record["top_weight_date"] == "2026-09-08"
    assert record["estimated_1rm_kg"] == 82.3
    assert record["estimated_1rm_date"] == "2026-09-01"


def test_weekly_summary_covers_every_week(client):
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    exercise_id = _exercise(client)
    _strength(client, exercise_id, monday.isoformat(), [(50, 10)])

    client.post(
        "/api/workouts/complete",
        json={
            "date": (monday - timedelta(days=1)).isoformat(),
            "type": "ENDURANCE",
            "endurance_activity": {"activity_type": "CYCLING", "distance": 40000},
        },
    )

    weeks = client.get("/api/analytics/weekly", params={"weeks": 4}).json()

    assert [week["week_start"] for week in weeks][-1] == monday.isoformat()
    assert len(weeks) == 4
    assert weeks[-1]["strength_volume_kg"] == 500
    assert weeks[-1]["cycling_meters"] == 0
    assert weeks[-2]["cycling_meters"] == 40000
    assert weeks[0]["workouts"] == 0
