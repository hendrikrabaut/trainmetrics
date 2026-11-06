import math

import pytest

from app.database import SessionLocal
from app.services.importers import parse_activity_file
from app.services.routes import MAXIMUM_POINTS, simplify, store_route
from tests.test_import import GPX, TCX


def _run(client, day="2026-10-01", sport="RUNNING"):
    return client.post(
        "/api/workouts/complete",
        json={
            "date": day,
            "type": "ENDURANCE",
            "endurance_activity": {"activity_type": sport, "distance": 1000},
        },
    ).json()["id"]


LINE = [(51 + index * 0.001, 4.0) for index in range(30)]


def _store(workout_id, points=LINE):
    with SessionLocal() as db:
        stored = store_route(db, workout_id, points)
        db.commit()

    return stored


def test_a_straight_line_needs_only_its_ends():
    assert simplify(LINE) == [LINE[0], LINE[-1]]


def test_a_corner_is_kept():
    corner = [(51.0, 4.0), (51.001, 4.0), (51.002, 4.0), (51.002, 4.001), (51.002, 4.002)]

    assert (51.002, 4.0) in simplify(corner)


def test_a_long_noisy_route_stays_small():
    noisy = [
        (51 + index * 0.0001 + math.sin(index) * 0.001, 4 + math.cos(index * 1.7) * 0.001)
        for index in range(5000)
    ]

    assert len(simplify(noisy)) <= MAXIMUM_POINTS


def test_route_can_be_read_and_marks_the_workout(client):
    workout_id = _run(client)

    assert client.get(f"/api/workouts/{workout_id}/route").status_code == 404
    assert client.get("/api/workouts/").json()[0]["has_route"] is False

    assert _store(workout_id) is True

    assert client.get("/api/workouts/").json()[0]["has_route"] is True
    assert client.get(f"/api/workouts/{workout_id}/route").json()["points"][0] == [51.0, 4.0]


def test_a_second_route_does_not_replace_the_first(client):
    workout_id = _run(client)

    assert _store(workout_id) is True
    assert _store(workout_id, [(52 + i * 0.001, 5.0) for i in range(9)]) is False
    assert client.get(f"/api/workouts/{workout_id}/route").json()["points"][0][0] == 51.0


@pytest.mark.parametrize(
    "points",
    [
        [],
        [(51.0, 4.0)] * 4,
        [(None, None)] * 20,
        [(0, 0)] * 20,
        [(91.0, 4.0)] * 20,
        [(51 + i * 0.00001, 4.0) for i in range(11)],
    ],
)
def test_bad_points_are_no_route(client, points):
    assert _store(_run(client), points) is False


def test_deleting_a_workout_deletes_its_route(client):
    workout_id = _run(client)
    _store(workout_id)

    client.delete(f"/api/workouts/{workout_id}")
    other = _run(client, "2026-10-02")
    _store(other)

    assert [row["workout_id"] for row in client.get("/api/routes").json()] == [other]


def test_all_routes_can_be_filtered_by_sport(client):
    run = _run(client, "2026-10-01", "RUNNING")
    ride = _run(client, "2026-10-02", "CYCLING")
    _store(run)
    _store(ride)

    assert len(client.get("/api/routes").json()) == 2

    rides = client.get("/api/routes", params={"sport": "CYCLING"}).json()

    assert [row["workout_id"] for row in rides] == [ride]
    assert rides[0]["date"] == "2026-10-02"
    assert client.get("/api/routes", params={"sport": "CHESS"}).status_code == 422


def test_gpx_keeps_its_route():
    assert parse_activity_file("run.gpx", GPX)[0].route == [(51.0, 4.0), (51.01, 4.0)]


def test_tcx_without_positions_has_no_route():
    assert parse_activity_file("ride.tcx", TCX)[0].route == []


def test_tcx_keeps_its_route():
    content = TCX.replace(
        b"<Trackpoint><AltitudeMeters>10</AltitudeMeters></Trackpoint>",
        b"<Trackpoint><Position><LatitudeDegrees>51.5</LatitudeDegrees>"
        b"<LongitudeDegrees>4.5</LongitudeDegrees></Position></Trackpoint>",
    )

    assert parse_activity_file("ride.tcx", content)[0].route == [(51.5, 4.5)]


def test_an_uploaded_file_stores_its_route(client):
    points = "".join(
        f'<trkpt lat="{51 + i * 0.002}" lon="{4 + (i % 3) * 0.002}">'
        f"<time>2026-09-29T12:{i:02d}:00Z</time></trkpt>"
        for i in range(10)
    )
    gpx = (
        '<?xml version="1.0"?><gpx version="1.1" creator="t" '
        'xmlns="http://www.topografix.com/GPX/1/1"><trk><type>running</type>'
        f"<trkseg>{points}</trkseg></trk></gpx>"
    ).encode()

    assert client.post("/api/import/", files={"file": ("run.gpx", gpx)}).status_code == 200
    assert client.get("/api/workouts/").json()[0]["has_route"] is True
