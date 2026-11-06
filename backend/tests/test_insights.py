import json
import struct
from datetime import date, datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models.equipment import Equipment
from app.services import segments
from app.services.importers import parse_activity_file
from app.services.polar_export import import_export
from app.services.streams import (
    compute_best_efforts,
    compute_splits,
    compute_zones,
    default_zone_limits,
    samples_from_points,
    store_stream,
    thin_samples,
)
from tests.test_import import FIT_EPOCH, START, _fit_crc

TODAY = date.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def _steady(speed, seconds, heart_rate=150):
    return {
        "distance": [speed * second for second in range(seconds)],
        "heart_rate": [heart_rate] * seconds,
    }


def _workout(client, day=None, sport="RUNNING", distance=10000, duration=3000):
    response = client.post(
        "/api/workouts/complete",
        json={
            "date": (day or MONDAY - timedelta(days=1)).isoformat(),
            "type": "ENDURANCE",
            "endurance_activity": {
                "activity_type": sport,
                "distance": distance,
                "duration": duration,
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _store(workout_id, samples, sport="RUNNING", zones=None):
    with SessionLocal() as db:
        stored = store_stream(db, workout_id, 1, sport, samples, zones)
        db.commit()

    return stored


# Splits


def test_splits_per_kilometer_with_a_last_partial_one():
    splits = compute_splits("RUNNING", _steady(4, 626))

    assert [split["number"] for split in splits] == [1, 2, 3]
    assert splits[0]["meters"] == 1000
    assert splits[0]["seconds"] == pytest.approx(250, abs=0.5)
    assert splits[1]["seconds"] == pytest.approx(250, abs=0.5)
    assert splits[2]["meters"] == pytest.approx(500, abs=1)
    assert splits[0]["heart_rate"] == 150


def test_a_tiny_last_piece_is_no_split():
    assert len(compute_splits("RUNNING", _steady(4, 255))) == 1


def test_splits_count_only_the_climbing():
    samples = _steady(4, 251)
    samples["altitude"] = [10 + second * 0.1 for second in range(100)] + [20] * 151

    assert compute_splits("RUNNING", samples)[0]["ascent"] == pytest.approx(9.9, abs=0.2)


def test_a_workout_without_distance_has_no_splits():
    assert compute_splits("STRENGTH", {"heart_rate": [100] * 100}) == []
    assert compute_splits("RUNNING", {"heart_rate": [100] * 100}) == []


# Best efforts


def test_best_effort_finds_the_fast_part_inside_a_long_run():
    slow = [3.0 * second for second in range(1000)]
    fast = [slow[-1] + 5.0 * second for second in range(1, 401)]
    slow_again = [fast[-1] + 3.0 * second for second in range(1, 1000)]

    efforts = compute_best_efforts(
        "RUNNING",
        {"distance": slow + fast + slow_again},
    )
    one_km = next(effort for effort in efforts if effort["meters"] == 1000)

    assert one_km["seconds"] == pytest.approx(200, abs=1)
    assert [effort["meters"] for effort in efforts] == [1000, 5000]


def test_a_gps_spike_is_not_a_record():
    distance = [3.0 * second for second in range(500)]
    jumped = [distance[-1] + 2000 + 3.0 * second for second in range(500)]

    efforts = compute_best_efforts("RUNNING", {"distance": distance + jumped})
    one_km = next(effort for effort in efforts if effort["meters"] == 1000)

    # Over the jump, a kilometer would take almost no time at all.
    assert one_km["seconds"] == pytest.approx(333, abs=2)


def test_efforts_only_for_distances_really_covered():
    assert compute_best_efforts("RUNNING", _steady(3, 200)) == []
    assert compute_best_efforts("STRENGTH", _steady(3, 2000)) == []


# Zones


def test_zones_follow_polar_percentages():
    assert default_zone_limits(199) == [100, 119, 139, 159, 179, 199]


def test_time_in_zones():
    samples = {"heart_rate": [90] * 5 + [110] * 10 + [150] * 20 + [199] * 3 + [None] * 9}
    zones = compute_zones(samples, [100, 119, 139, 159, 179, 199])

    assert [zone["seconds"] for zone in zones] == [10, 0, 20, 0, 3]


def test_polars_own_zones_go_first_and_summary_totals_them(client):
    workout = _workout(client)
    zones = [
        {"lower": 100, "upper": 119, "seconds": 600},
        {"lower": 119, "upper": 139, "seconds": 600},
        {"lower": 139, "upper": 159, "seconds": 400},
        {"lower": 159, "upper": 179, "seconds": 300},
        {"lower": 179, "upper": 199, "seconds": 100},
    ]
    _store(workout, _steady(3, 2000), zones=zones)

    assert client.get(f"/api/workouts/{workout}/detail").json()["zones"][0]["seconds"] == 600

    summary = client.get("/api/analytics/zones").json()

    assert [zone["seconds"] for zone in summary["zones"]] == [600, 600, 400, 300, 100]
    assert summary["easy_share"] == 0.6
    assert len(summary["per_week"]) == 12
    assert summary["per_week"][-2]["easy_share"] == 0.6
    assert summary["per_week"][0]["easy_share"] is None


# Keeping them small


def test_thinning_keeps_every_fifth_and_averages_spikes():
    samples = {"speed": [3.0] * 4 + [13.0] + [3.0] * 5, "heart_rate": [100] * 10}

    data = thin_samples(samples)

    assert data["speed"] == [5.0, 3.0]
    assert data["heart_rate"] == [100, 100]


def test_detail_of_a_workout_with_no_measurements(client):
    detail = client.get(f"/api/workouts/{_workout(client)}/detail").json()

    assert detail["series"] == {}
    assert detail["splits"] == []


def test_a_stream_is_kept_once(client):
    workout = _workout(client)

    assert _store(workout, _steady(3, 100)) is True
    assert _store(workout, _steady(4, 100)) is False


def test_deleting_a_workout_deletes_its_stream(client):
    workout = _workout(client)
    _store(workout, _steady(3, 2000))

    assert client.delete(f"/api/workouts/{workout}").status_code == 200
    assert client.get("/api/analytics/best-efforts").json() == []


# Irregular files


def test_points_become_one_sample_a_second():
    start = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    points = [
        {"time": start, "heart_rate": 100, "distance": 0},
        {"time": start + timedelta(seconds=3), "heart_rate": 130, "distance": 12},
        {"time": start + timedelta(seconds=4), "heart_rate": float("nan"), "distance": 16},
    ]

    samples = samples_from_points(points)

    assert samples["heart_rate"] == [100, 100, 100, 130, 130]
    assert samples["distance"] == [0, 0, 0, 12, 16]


def test_distance_comes_from_gps_if_a_file_has_none():
    start = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    samples = samples_from_points(
        [
            {"time": start + timedelta(seconds=index), "latitude": 51 + index * 0.0001, "longitude": 4.0}
            for index in range(11)
        ]
    )

    assert samples["distance"][-1] == pytest.approx(111, abs=2)


def _fit_with_records(count=600):
    """A FIT file with GPS and heart rate records, followed by its session."""
    start = int(START.timestamp() - FIT_EPOCH)
    record_fields = [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85), (3, 1, 0x02), (5, 4, 0x86)]
    session_fields = [(2, 4, 0x86), (5, 1, 0x00), (8, 4, 0x86), (9, 4, 0x86)]

    body = struct.pack("<BBBHB", 0x40, 0, 0, 20, len(record_fields))
    body += b"".join(struct.pack("<BBB", *field) for field in record_fields)

    for second in range(count):
        latitude = int((51 + second * 0.00003) * 2**31 / 180)
        longitude = int(4 * 2**31 / 180)
        body += struct.pack(
            "<BIiiBI", 0x00, start + second, latitude, longitude, 150, second * 300
        )

    body += struct.pack("<BBBHB", 0x41, 0, 0, 18, len(session_fields))
    body += b"".join(struct.pack("<BBB", *field) for field in session_fields)
    body += struct.pack("<BIBII", 0x01, start, 1, count * 1000, count * 300)

    header = struct.pack("<BBHI4s", 14, 0x20, 2100, len(body), b".FIT")
    header += struct.pack("<H", _fit_crc(header))
    file = header + body

    return file + struct.pack("<H", _fit_crc(file))


def test_a_fit_file_brings_its_measurements_and_route(client):
    response = client.post("/api/import/", files={"file": ("run.fit", _fit_with_records())})

    assert response.status_code == 200, response.text

    workout = client.get("/api/workouts/").json()[0]
    detail = client.get(f"/api/workouts/{workout['id']}/detail").json()

    assert workout["has_route"] is True
    assert detail["series"]["heart_rate"][0] == 150
    assert detail["splits"][0]["meters"] == 1000
    assert detail["best_efforts"][0]["meters"] == 1000
    assert sum(zone["seconds"] for zone in detail["zones"]) == 600


# Race predictions use the fast part


def test_a_fast_stretch_improves_the_race_estimate(client):
    day = TODAY - timedelta(days=5)
    workout = _workout(client, day, distance=12000, duration=4000)

    before = client.get("/api/analytics/estimates").json()["best_run"]
    assert before["is_stretch"] is False

    _store(workout, {"distance": [3.0 * s for s in range(1500)] + [4500 + 4.0 * s for s in range(1, 1400)]})

    after = client.get("/api/analytics/estimates").json()["best_run"]

    assert after["is_stretch"] is True
    assert after["distance"] == 5000
    assert after["predictions"]["10 km"] < before["predictions"]["10 km"]


# Performance chart


def test_performance_chart_looks_ahead_along_the_plan(client):
    _workout(client, TODAY - timedelta(days=10), duration=3600)
    race_day = TODAY + timedelta(days=30)
    client.post("/api/races/", json={"name": "Stadsloop", "date": race_day.isoformat(), "priority": "A"})
    client.post("/api/plans/", json={"goal": "10K", "weeks": 4, "start_date": MONDAY.isoformat()})

    chart = client.get("/api/analytics/performance").json()

    assert chart["history"][-1]["date"] == TODAY.isoformat()
    assert chart["projection"][0]["date"] == (TODAY + timedelta(days=1)).isoformat()
    assert chart["projection"][-1]["date"] == race_day.isoformat()
    assert chart["races"][0]["name"] == "Stadsloop"
    assert chart["races"][0]["form"] == chart["projection"][-1]["form"]


def test_performance_chart_without_data(client):
    chart = client.get("/api/analytics/performance").json()

    assert chart["history"] == []
    assert chart["projection"] == []


# Plan against reality


def _plan(client, **body):
    response = client.post("/api/plans/", json={"goal": "10K", **body})
    assert response.status_code == 200, response.text
    return response.json()


def _long_run_this_week(client, sessions=4):
    plan = _plan(client, weeks=4, start_date=MONDAY.isoformat(), sessions_per_week=sessions)
    return next(s for s in plan["sessions"] if s["title"] == "Lange duurloop" and s["week"] == 1)


@pytest.mark.parametrize(
    "share, completed, partial, compliance",
    [
        (1.0, True, False, "ON_TARGET"),
        (0.85, True, False, "ON_TARGET"),
        (0.7, True, False, "SHORT"),
        (1.4, True, False, "LONG"),
        (0.3, False, True, "SHORT"),
    ],
)
def test_a_session_compares_plan_and_reality(client, share, completed, partial, compliance):
    session = _long_run_this_week(client, sessions=2)
    # Two sessions a week: this is the only run with a planned distance.
    _workout(client, date.fromisoformat(session["date"]), distance=session["distance"] * share, duration=3000)

    plan = client.get("/api/plans/active").json()
    row = next(s for s in plan["sessions"] if s["id"] == session["id"])

    assert row["completed"] is completed
    assert row["partial"] is partial
    assert row["compliance"] == compliance
    assert row["actual"]["ratio"] == pytest.approx(share, abs=0.01)
    assert plan["weeks"][0]["done_meters"] == pytest.approx(session["distance"] * share, abs=1)
    assert plan["weeks"][0]["planned_meters"] >= session["distance"]


def test_a_workout_goes_to_the_session_of_that_day(client):
    plan = _plan(client, weeks=4, start_date=MONDAY.isoformat(), sessions_per_week=4)
    week = [s for s in plan["sessions"] if s["week"] == 1 and s["sport"] == "RUNNING"]
    last = week[-1]

    _workout(client, date.fromisoformat(last["date"]), distance=last["distance"] or 5000)

    rows = client.get("/api/plans/active").json()["sessions"]

    assert next(s for s in rows if s["id"] == last["id"])["actual"] is not None
    assert next(s for s in rows if s["id"] == week[0]["id"])["actual"] is None


def test_too_short_a_session_earns_no_plan_xp(client):
    session = _long_run_this_week(client, sessions=2)
    _workout(client, date.fromisoformat(session["date"]), distance=session["distance"] * 0.3)

    labels = [event["label"] for event in client.get("/api/game/profile").json()["recent"]]

    assert not any(label.startswith("Plan:") for label in labels)


# Seasons


def test_a_plan_has_phases_in_order(client):
    plan = _plan(client, goal="HALF", weeks=12, sessions_per_week=4)

    phases = [week["phase"] for week in plan["weeks"]]

    assert phases[0] == "BASE"
    assert phases[-1] == "TAPER"
    assert phases[-2] == "TAPER"
    assert "BUILD" in phases and "PEAK" in phases
    assert phases == sorted(phases, key=["BASE", "BUILD", "PEAK", "TAPER"].index)

    titles = {s["phase"]: [] for s in plan["sessions"]}
    for session in plan["sessions"]:
        titles[session["phase"]].append(session["title"])

    assert "Rustige loop met versnellingen" in titles["BASE"]
    assert "Wedstrijdtempo" in titles["PEAK"]
    assert "Intervallen" not in titles["BASE"]


def test_a_short_plan_can_do_without_a_taper(client):
    plan = _plan(client, goal="5K", weeks=2, sessions_per_week=2)

    assert "TAPER" not in [week["phase"] for week in plan["weeks"]]


def test_races_can_be_managed(client):
    day = (TODAY + timedelta(days=50)).isoformat()
    race = client.post("/api/races/", json={"name": "Triatlon", "date": day, "priority": "A", "goal": "TRIATHLON"}).json()

    assert client.get("/api/races/").json()[0]["name"] == "Triatlon"

    changed = client.patch(f"/api/races/{race['id']}", json={"priority": "B"}).json()
    assert changed["priority"] == "B"
    assert changed["date"] == day

    assert client.delete(f"/api/races/{race['id']}").status_code == 200
    assert client.get("/api/races/").json() == []
    assert client.delete(f"/api/races/{race['id']}").status_code == 404
    assert client.post("/api/races/", json={"name": "X", "date": day, "priority": "Z"}).status_code == 422


def test_a_b_race_makes_its_week_lighter_and_joins_the_plan(client):
    start = MONDAY + timedelta(weeks=1)
    plain = _plan(client, goal="10K", weeks=8, start_date=start.isoformat(), weekdays=[1, 3, 6])

    race_day = start + timedelta(weeks=4, days=5)
    client.post(
        "/api/races/",
        json={"name": "Dorpsloop", "date": race_day.isoformat(), "priority": "B", "goal": "5K"},
    )

    plan = _plan(client, goal="10K", weeks=8, start_date=start.isoformat(), weekdays=[1, 3, 6])
    race = next(s for s in plan["sessions"] if s["title"] == "Wedstrijd: Dorpsloop")

    assert race["date"] == race_day.isoformat()
    assert race["distance"] == 5000
    assert race["week"] == 5

    def long_of(rows, week):
        return next(s["distance"] for s in rows if s["week"] == week and s["title"] == "Lange duurloop")

    assert long_of(plan["sessions"], 5) < long_of(plain["sessions"], 5)
    assert long_of(plan["sessions"], 6) == long_of(plain["sessions"], 6)


def test_a_race_replaces_the_training_on_that_day(client):
    start = MONDAY + timedelta(weeks=1)
    race_day = start + timedelta(days=6)
    client.post("/api/races/", json={"name": "Loop", "date": race_day.isoformat(), "priority": "C"})

    plan = _plan(client, goal="10K", weeks=4, start_date=start.isoformat(), weekdays=[1, 6])

    assert [s["title"] for s in plan["sessions"] if s["date"] == race_day.isoformat()] == ["Wedstrijd: Loop"]


# Gear


def _gear(client, **body):
    response = client.post("/api/equipment/", json={"name": "Schoenen", **body})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _usage(client, gear_id):
    return next(row for row in client.get("/api/equipment/").json() if row["id"] == gear_id)


def test_default_gear_counts_its_sport_from_its_purchase_date(client):
    gear = _gear(client, sport="RUNNING", is_default=True, purchase_date="2026-06-01")

    _workout(client, date(2026, 5, 1), distance=5000)
    _workout(client, date(2026, 7, 1), distance=7000)
    _workout(client, date(2026, 7, 2), sport="CYCLING", distance=30000)

    usage = _usage(client, gear)

    assert usage["kilometers"] == 7
    assert usage["sessions"] == 1


def test_linked_gear_replaces_the_default_for_that_workout(client):
    usual = _gear(client, sport="RUNNING", is_default=True)
    racers = _gear(client, sport="RUNNING")

    first = _workout(client, date(2026, 7, 1), distance=7000)
    _workout(client, date(2026, 7, 2), distance=9000)

    client.put(f"/api/workouts/{first}/equipment/{racers}")

    assert _usage(client, usual)["kilometers"] == 9
    assert _usage(client, racers)["kilometers"] == 7
    assert _usage(client, racers)["linked_workout_ids"] == [first]


def test_gear_warns_when_it_should_be_replaced(client):
    gear = _gear(client, sport="RUNNING", is_default=True, replace_after_km=10)

    _workout(client, date(2026, 7, 1), distance=9000)
    assert _usage(client, gear)["needs_replacing"] is False

    _workout(client, date(2026, 7, 2), distance=2000)
    assert _usage(client, gear)["needs_replacing"] is True

    client.patch(f"/api/equipment/{gear}", json={"status": "RETIRED"})
    assert _usage(client, gear)["needs_replacing"] is False


# Segments


def _track_samples(start_seconds=0, speed_factor=1.0, reverse=False, count=600):
    """Going north at about 4 m/s, optionally slower, later or the other way."""
    latitude = [None] * start_seconds + [
        51 + (count - second if reverse else second) * 0.00004 * speed_factor
        for second in range(count)
    ]

    return {
        "latitude": latitude,
        "longitude": [None] * start_seconds + [4.0] * count,
        "distance": [0.0] * start_seconds + [second * 4.45 * speed_factor for second in range(count)],
    }


def _segment(client, workout, name="Klim", start=(51.002, 4.0), end=(51.012, 4.0)):
    return client.post(
        "/api/segments/",
        json={"name": name, "workout_id": workout, "start": start, "end": end},
    )


def test_a_segment_finds_every_workout_over_it(client):
    first = _workout(client, date(2026, 7, 1))
    _store(first, _track_samples())

    slower = _workout(client, date(2026, 7, 2))
    _store(slower, _track_samples(speed_factor=0.5, count=1200))

    elsewhere = _workout(client, date(2026, 7, 3))
    _store(elsewhere, {**_track_samples(), "longitude": [5.0] * 600})

    response = _segment(client, first)
    assert response.status_code == 200, response.text
    segment = response.json()

    assert segment["sport"] == "RUNNING"
    assert segment["length_meters"] == pytest.approx(1113, abs=25)
    assert segment["count"] == 2
    assert segment["efforts"][0]["workout_id"] == first
    assert segment["best_seconds"] == pytest.approx(250, abs=10)
    assert segment["efforts"][1]["seconds"] == pytest.approx(500, abs=15)

    detail = client.get(f"/api/workouts/{first}/detail").json()
    assert detail["segments"][0]["name"] == "Klim"


def test_a_segment_ignores_the_other_direction(client):
    first = _workout(client, date(2026, 7, 1))
    _store(first, _track_samples())

    back = _workout(client, date(2026, 7, 2))
    _store(back, _track_samples(reverse=True))

    assert _segment(client, first).json()["count"] == 1


def test_a_shortcut_does_not_count(client):
    first = _workout(client, date(2026, 7, 1))
    _store(first, _track_samples())

    # Starts and ends at the right places, but goes far around in between.
    samples = _track_samples()
    samples["longitude"] = [4.0 + 0.01 * (second > 100 and second < 400) for second in range(600)]
    other = _workout(client, date(2026, 7, 2))
    _store(other, samples)

    assert _segment(client, first).json()["count"] == 1


def test_a_new_workout_is_checked_against_segments(client):
    first = _workout(client, date(2026, 7, 1))
    _store(first, _track_samples())
    segment = _segment(client, first).json()

    with SessionLocal() as db:
        second = _workout(client, date(2026, 7, 2))
        store_stream(db, second, 1, "RUNNING", _track_samples(speed_factor=0.8, count=800))
        segments.match_workout(db, 1, second, "RUNNING")
        db.commit()

    row = next(s for s in client.get("/api/segments/").json() if s["id"] == segment["id"])
    assert row["count"] == 2


@pytest.mark.parametrize(
    "start, end",
    [((51.0, 4.0), (51.0, 4.0)), ((51.0, 4.0), (51.0005, 4.0))],
)
def test_too_short_a_segment_is_refused(client, start, end):
    first = _workout(client, date(2026, 7, 1))
    _store(first, _track_samples())

    assert _segment(client, first, start=start, end=end).status_code == 422


def test_a_workout_without_gps_cannot_become_a_segment(client):
    first = _workout(client, date(2026, 7, 1))
    assert _segment(client, first).status_code == 422

    _store(first, _steady(3, 200))
    assert _segment(client, first).status_code == 422


def test_deleting_a_segment_and_its_workouts(client):
    first = _workout(client, date(2026, 7, 1))
    _store(first, _track_samples())
    segment = _segment(client, first).json()

    assert client.delete(f"/api/workouts/{first}").status_code == 200
    assert client.get("/api/segments/").json()[0]["count"] == 0
    assert client.delete(f"/api/segments/{segment['id']}").status_code == 200
    assert client.get("/api/segments/").json() == []


# A year


def test_year_review_counts_that_year_only(client):
    _workout(client, date(2025, 12, 31), distance=99000)
    _workout(client, date(2026, 3, 2), distance=10000, duration=3000)
    _workout(client, date(2026, 3, 3), sport="CYCLING", distance=40000, duration=6000)
    _workout(client, date(2026, 3, 3), sport="SWIMMING", distance=1500, duration=2400)
    client.post(
        "/api/workouts/",
        json={"date": "2026-05-01", "type": "STRENGTH", "duration": 3000},
    )

    review = client.get("/api/analytics/year/2026").json()

    assert review["workouts"] == 4
    assert review["active_days"] == 3
    assert review["meters"] == 51500
    assert review["years"] == [2026, 2025]
    assert review["longest"]["meters"] == 40000
    assert review["busiest_week"]["week_start"] == "2026-03-02"
    assert review["months"][2]["meters"] == 51500
    assert review["sports"][0]["sport"] == "CYCLING"
    assert {row["sport"] for row in review["sports"]} == {"RUNNING", "CYCLING", "SWIMMING", "STRENGTH"}
    assert "2026-03-03" in review["days"]


def test_a_year_without_training(client):
    review = client.get("/api/analytics/year/2020").json()

    assert review["workouts"] == 0
    assert review["longest"] is None
    assert review["busiest_week"] is None


# Race distances


@pytest.mark.parametrize(
    "goal, name, distance",
    [
        ("5MI", "5 mijl", 8047),
        ("10MI", "10 mijl", 16093),
        ("MARATHON", "marathon", 42195),
        ("TRI_QUARTER", "1/4 triatlon", None),
        ("TRI_HALF", "1/2 triatlon", None),
    ],
)
def test_a_plan_can_aim_at_every_race(client, goal, name, distance):
    race_day = MONDAY + timedelta(weeks=20, days=6)

    created = client.post(
        "/api/races/",
        json={"name": "Doel", "date": race_day.isoformat(), "priority": "A", "goal": goal},
    )
    assert created.status_code == 200, created.text

    plan = _plan(client, goal=goal, race_date=race_day.isoformat(), weekdays=[1, 3, 5, 6])
    last = plan["sessions"][-1]

    assert plan["goal_name"] == name
    assert last["title"] == "Wedstrijddag"
    assert last["date"] == race_day.isoformat()
    assert last["distance"] == distance
    assert last["sport"] == ("SWIMMING" if goal.startswith("TRI") else "RUNNING")


def test_an_unknown_race_distance_is_refused(client):
    response = client.post(
        "/api/races/",
        json={"name": "X", "date": "2027-01-01", "priority": "A", "goal": "100K"},
    )
    assert response.status_code == 422


def test_each_goal_gets_its_own_length_by_default(client):
    assert _plan(client, goal="MARATHON")["weeks"][-1]["week"] == 18
    assert _plan(client, goal="TRI_HALF")["weeks"][-1]["week"] == 20
    assert _plan(client, goal="5MI")["weeks"][-1]["week"] == 9


def test_a_half_triathlon_trains_more_than_a_quarter(client):
    def longest(goal, sport, field):
        plan = _plan(client, goal=goal, weeks=16, weekdays=[0, 1, 3, 5, 6])
        return max(s[field] or 0 for s in plan["sessions"] if s["sport"] == sport)

    assert longest("TRI_HALF", "CYCLING", "duration") > longest("TRI_QUARTER", "CYCLING", "duration")
    assert longest("TRI_HALF", "SWIMMING", "distance") > longest("TRI_QUARTER", "SWIMMING", "distance")
    assert longest("TRI_HALF", "RUNNING", "distance") > longest("TRI_QUARTER", "RUNNING", "distance")


@pytest.mark.parametrize("goal", ["TRIATHLON", "TRI_QUARTER", "TRI_HALF"])
def test_a_triathlon_tapers_on_the_bike_and_in_the_water(client, goal):
    plan = _plan(client, goal=goal, weeks=16, weekdays=[0, 1, 3, 5, 6])

    def per_week(sport, field):
        return {
            s["week"]: s[field]
            for s in plan["sessions"]
            if s["sport"] == sport and s[field] and s["title"] in ("Lange rit", "Duurzwemmen")
        }

    ride = per_week("CYCLING", "duration")
    swim = per_week("SWIMMING", "distance")

    assert ride[16] < max(ride.values())
    assert swim[16] < max(swim.values())
    # A lighter week is lighter for everything.
    assert ride[8] < ride[7]


def test_a_triathlon_needs_three_sessions_a_week(client):
    for goal in ("TRI_QUARTER", "TRI_HALF"):
        response = client.post("/api/plans/", json={"goal": goal, "weekdays": [1, 6]})
        assert response.status_code == 422


def test_a_triathlon_on_the_way_counts_as_a_triathlon(client):
    start = MONDAY + timedelta(weeks=1)
    race_day = start + timedelta(weeks=4, days=6)
    client.post(
        "/api/races/",
        json={"name": "Kwart", "date": race_day.isoformat(), "priority": "B", "goal": "TRI_QUARTER"},
    )

    plan = _plan(client, goal="TRI_HALF", weeks=16, start_date=start.isoformat(), weekdays=[1, 3, 5, 6])
    race = next(s for s in plan["sessions"] if s["title"] == "Wedstrijd: Kwart")

    assert race["sport"] == "SWIMMING"
    assert race["distance"] is None


# Editing gear


def test_gear_can_be_edited_and_then_counts(client):
    gear = _gear(client, name="Fiets", category="BIKE")
    client.patch(f"/api/equipment/{gear}", json={"status": "RETIRED"})
    _workout(client, date(2026, 7, 1), sport="CYCLING", distance=40000)

    assert _usage(client, gear)["kilometers"] == 0

    response = client.patch(
        f"/api/equipment/{gear}",
        json={
            "name": "Racefiets",
            "sport": "CYCLING",
            "is_default": True,
            "replace_after_km": 5000,
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 200, response.text

    usage = _usage(client, gear)

    assert usage["name"] == "Racefiets"
    assert usage["category"] == "BIKE"
    assert usage["kilometers"] == 40
    assert usage["replace_after_km"] == 5000
    assert usage["status"] == "ACTIVE"


def test_a_limit_can_be_removed(client):
    gear = _gear(client, sport="RUNNING", replace_after_km=700)

    client.patch(f"/api/equipment/{gear}", json={"replace_after_km": None})

    assert _usage(client, gear)["replace_after_km"] is None


def test_one_sport_has_one_default(client):
    first = _gear(client, name="Oud", sport="RUNNING", is_default=True)
    second = _gear(client, name="Nieuw", sport="RUNNING", is_default=True)
    other = _gear(client, name="Fiets", sport="CYCLING", is_default=True)

    assert _usage(client, first)["is_default"] is False
    assert _usage(client, second)["is_default"] is True
    assert _usage(client, other)["is_default"] is True

    client.patch(f"/api/equipment/{first}", json={"is_default": True})

    assert _usage(client, first)["is_default"] is True
    assert _usage(client, second)["is_default"] is False

    _workout(client, date(2026, 7, 1), distance=5000)

    assert _usage(client, first)["kilometers"] == 5
    assert _usage(client, second)["kilometers"] == 0


def test_gear_without_a_sport_cannot_be_default(client):
    gear = _gear(client, sport="RUNNING", is_default=True)

    client.patch(f"/api/equipment/{gear}", json={"sport": None})

    assert _usage(client, gear)["is_default"] is False


@pytest.mark.parametrize("field", ["name", "status", "is_default"])
def test_required_gear_fields_cannot_be_emptied(client, field):
    gear = _gear(client)

    assert client.patch(f"/api/equipment/{gear}", json={field: None}).status_code == 422


def test_a_limit_of_zero_means_no_limit(client):
    gear = _gear(client, sport="RUNNING", replace_after_km=0)

    assert _usage(client, gear)["replace_after_km"] is None

    client.patch(f"/api/equipment/{gear}", json={"replace_after_km": 500})
    client.patch(f"/api/equipment/{gear}", json={"replace_after_km": 0})

    assert _usage(client, gear)["replace_after_km"] is None
