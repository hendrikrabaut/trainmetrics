from datetime import date, timedelta

import pytest

from app.services.estimates import polar_predictions, riegel_predictions
from app.services.game import level_for_xp, title_for_level, xp_for_level
from app.services.plans import next_monday


TODAY = date.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def _exercise(client):
    return client.post("/api/exercises/", json={"name": "Bench"}).json()["id"]


def _lift(client, exercise_id, day, weight=60, reps=10):
    response = client.post(
        "/api/workouts/complete",
        json={
            "date": day.isoformat(),
            "type": "STRENGTH",
            "duration": 3000,
            "exercises": [
                {
                    "exercise_id": exercise_id,
                    "exercise_order": 1,
                    "sets": [{"set_number": 1, "weight": weight, "reps": reps}],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, day, distance=10000, duration=3000, sport="RUNNING"):
    response = client.post(
        "/api/workouts/complete",
        json={
            "date": day.isoformat(),
            "type": "ENDURANCE",
            "endurance_activity": {
                "activity_type": sport,
                "distance": distance,
                "duration": duration,
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _profile(client):
    return client.get("/api/game/profile").json()


# Levels


@pytest.mark.parametrize(
    "xp, level",
    [(0, 1), (299, 1), (300, 2), (899, 2), (900, 3), (13500, 10), (15241, 10)],
)
def test_levels(xp, level):
    assert level_for_xp(xp) == level


def test_each_level_costs_more_than_the_last():
    costs = [xp_for_level(n + 1) - xp_for_level(n) for n in range(1, 30)]
    assert costs == sorted(costs)


def test_titles_change_at_their_level():
    assert title_for_level(1) == "Groentje"
    assert title_for_level(4) == "Groentje"
    assert title_for_level(5) == "Doorzetter"
    assert title_for_level(99) == "Legende"


# XP


def test_a_new_player_starts_at_zero(client):
    profile = _profile(client)

    assert profile["xp"] == 0
    assert profile["level"] == 1
    assert profile["streak_weeks"] == 0
    assert all(badge["earned_on"] is None for badge in profile["badges"])


def test_deleting_a_workout_takes_its_xp_back(client):
    exercise = _exercise(client)
    workout = _lift(client, exercise, MONDAY)

    assert _profile(client)["xp"] > 0

    client.delete(f"/api/workouts/{workout['id']}")

    assert _profile(client)["xp"] == 0


def test_beating_a_lift_gives_a_record_bonus(client):
    exercise = _exercise(client)
    first = _lift(client, exercise, MONDAY - timedelta(weeks=2))
    second = _lift(client, exercise, MONDAY - timedelta(weeks=1), weight=70)

    xp = _profile(client)["workout_xp"]

    assert xp[str(second["id"])] == xp[str(first["id"])] + 100


def test_quests_give_xp_when_completed(client):
    exercise = _exercise(client)
    _lift(client, exercise, MONDAY)

    quest = {q["id"]: q for q in _profile(client)["quests"]}
    assert quest["three_workouts"]["progress"] == 1
    assert quest["three_workouts"]["completed"] is False
    assert quest["mixed"]["progress"] == 1

    before = _profile(client)["xp"]
    _run(client, MONDAY)

    profile = _profile(client)
    quest = {q["id"]: q for q in profile["quests"]}

    assert quest["mixed"]["completed"] is True
    assert profile["xp"] >= before + 75


# Streaks and badges


def test_streak_counts_weeks_and_survives_an_unfinished_week(client):
    for weeks_ago in (1, 2, 3):
        _run(client, MONDAY - timedelta(weeks=weeks_ago))

    assert _profile(client)["streak_weeks"] == 3


def test_a_gap_breaks_the_streak(client):
    _run(client, MONDAY - timedelta(weeks=1))
    _run(client, MONDAY - timedelta(weeks=3))

    assert _profile(client)["streak_weeks"] == 1


def test_badges_record_when_they_were_earned(client):
    day = MONDAY - timedelta(weeks=1)
    _run(client, day, distance=21100, duration=7200)

    badges = {badge["id"]: badge for badge in _profile(client)["badges"]}

    assert badges["first_workout"]["earned_on"] == day.isoformat()
    assert badges["half_marathon"]["earned_on"] == day.isoformat()
    assert badges["workouts_10"]["earned_on"] is None
    assert badges["workouts_10"]["progress"] == 1
    assert badges["run_100"]["progress"] == 21


def test_triathlete_badge_needs_all_three_sports_in_a_week(client):
    day = MONDAY - timedelta(weeks=1)

    _run(client, day, sport="RUNNING")
    _run(client, day, sport="CYCLING")

    badges = {badge["id"]: badge for badge in _profile(client)["badges"]}
    assert badges["triathlete"]["earned_on"] is None

    _run(client, day, sport="SWIMMING")

    badges = {badge["id"]: badge for badge in _profile(client)["badges"]}
    assert badges["triathlete"]["earned_on"] == day.isoformat()


# Estimates


def test_polar_table_values_and_interpolation():
    assert polar_predictions(36)["5 km"] == 36 * 60 + 20
    assert polar_predictions(78)["Marathon"] == 2 * 3600 + 32 * 60

    between = polar_predictions(37)["5 km"]
    assert 34 * 60 + 20 < between < 36 * 60 + 20

    assert polar_predictions(35) is None
    assert polar_predictions(79) is None


def test_riegel_keeps_the_known_distance_and_slows_down_with_distance():
    predictions = riegel_predictions(10000, 3000)

    assert predictions["10 km"] == 3000
    assert predictions["5 km"] < 1500
    assert predictions["Halve marathon"] > 3000 * 2.1


def test_estimates_use_recent_runs_only(client):
    _run(client, TODAY - timedelta(days=200), distance=10000, duration=2000)
    _run(client, TODAY - timedelta(days=10), distance=10000, duration=3000)
    _run(client, TODAY - timedelta(days=5), distance=1000, duration=200)

    best = client.get("/api/analytics/estimates").json()["best_run"]

    assert best["duration"] == 3000
    assert best["predictions"]["10 km"] == 3000


def test_fitness_rises_with_training_and_form_drops_right_after(client):
    for days_ago in range(14, 0, -2):
        _run(client, TODAY - timedelta(days=days_ago))

    result = client.get("/api/analytics/estimates").json()

    assert result["fitness"]["fitness"] > 0
    assert result["fitness"]["form"] == pytest.approx(
        result["fitness"]["fitness"] - result["fitness"]["fatigue"],
        abs=0.11,
    )
    assert result["fitness_series"][-1]["date"] == TODAY.isoformat()
    assert result["running_index"] is None


def test_estimates_with_no_data(client):
    result = client.get("/api/analytics/estimates").json()

    assert result["fitness"] is None
    assert result["best_run"] is None


# Plans


def _plan(client, **body):
    response = client.post("/api/plans/", json={"goal": "10K", **body})
    assert response.status_code == 200, response.text
    return response.json()


def test_no_plan_yet(client):
    assert client.get("/api/plans/active").json() is None


@pytest.mark.parametrize(
    "goal",
    [
        "5K", "5MI", "10K", "10MI", "HALF", "MARATHON",
        "TRIATHLON", "TRI_QUARTER", "TRI_HALF", "STRENGTH", "FITNESS",
    ],
)
@pytest.mark.parametrize("sessions", [3, 4, 7])
def test_every_goal_gives_a_full_plan(client, goal, sessions):
    plan = _plan(client, goal=goal, sessions_per_week=sessions, weeks=8)

    assert plan["total"] == 8 * sessions
    assert plan["start_date"] == next_monday(TODAY).isoformat()

    per_week = {}
    for session in plan["sessions"]:
        per_week[session["week"]] = per_week.get(session["week"], 0) + 1

    assert set(per_week.values()) == {sessions}


def test_long_run_grows_slowly_with_lighter_weeks_and_a_taper(client):
    plan = _plan(client, goal="HALF", weeks=12, sessions_per_week=3)

    longs = [
        session["distance"]
        for session in plan["sessions"]
        if session["title"] == "Lange duurloop"
    ]

    assert len(longs) == 12

    for week, (previous, current) in enumerate(zip(longs, longs[1:]), start=2):
        if week % 4 == 0 or week == 12:
            assert current < previous
        elif (week - 1) % 4 != 0:
            assert current <= previous * 1.11

    assert longs[-1] < max(longs) * 0.6


def test_too_short_a_plan_warns_instead_of_overloading(client):
    plan = _plan(client, goal="HALF", weeks=4, sessions_per_week=3)

    assert "liever meer tijd" in plan["warning"]
    assert _plan(client, goal="5K", weeks=12)["warning"] is None


def test_plan_uses_recent_long_run_as_its_start(client):
    _run(client, TODAY - timedelta(days=7), distance=12000, duration=4200)

    plan = _plan(client, goal="HALF", weeks=12, sessions_per_week=3)
    first = next(s for s in plan["sessions"] if s["title"] == "Lange duurloop")

    assert first["distance"] == 12000
    assert "/km" in first["description"]


def test_race_date_ends_the_plan_on_race_day(client):
    race = next_monday(TODAY) + timedelta(weeks=9, days=6)
    plan = _plan(client, race_date=race.isoformat(), sessions_per_week=4)

    last = plan["sessions"][-1]

    assert last["title"] == "Wedstrijddag"
    assert last["date"] == race.isoformat()
    assert last["distance"] == 10000
    assert plan["end_date"] == race.isoformat()
    assert sum(s["date"] > race.isoformat() for s in plan["sessions"]) == 0
    assert sum(s["date"] == race.isoformat() for s in plan["sessions"]) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"goal": "TRIATHLON", "sessions_per_week": 2},
        {"goal": "10K", "race_date": (TODAY - timedelta(days=1)).isoformat()},
        {"goal": "10K", "start_date": (TODAY - timedelta(weeks=2)).isoformat()},
        {"goal": "MARS"},
        {"goal": "10K", "sessions_per_week": 9},
    ],
)
def test_impossible_plans_are_refused(client, body):
    assert client.post("/api/plans/", json=body).status_code == 422


def test_a_session_completes_with_any_day_in_that_week_and_gives_xp(client):
    start = MONDAY
    plan = _plan(client, goal="FITNESS", sessions_per_week=3, weeks=4, start_date=start.isoformat())

    session = next(s for s in plan["sessions"] if s["sport"] == "RUNNING")
    week_of_session = date.fromisoformat(session["date"])
    monday_of_session = week_of_session - timedelta(days=week_of_session.weekday())

    xp_before = _profile(client)["xp"]
    _run(client, monday_of_session)

    active = client.get("/api/plans/active").json()
    done = next(s for s in active["sessions"] if s["id"] == session["id"])

    assert done["completed"] is True
    assert active["completed"] == 1

    labels = [event["label"] for event in _profile(client)["recent"]]
    assert any(label.startswith("Plan:") for label in labels)
    assert _profile(client)["xp"] > xp_before


def test_one_workout_completes_only_one_session(client):
    plan = _plan(client, goal="10K", sessions_per_week=4, weeks=4, start_date=MONDAY.isoformat())
    _run(client, MONDAY)

    assert client.get("/api/plans/active").json()["completed"] == 1
    assert plan["completed"] == 0


def test_a_new_plan_replaces_the_active_one(client):
    first = _plan(client, goal="5K", weeks=8)
    second = _plan(client, goal="HALF", weeks=12)

    active = client.get("/api/plans/active").json()

    assert active["id"] == second["id"] != first["id"]
    assert active["goal"] == "HALF"


# Changing a plan


def test_chosen_days_are_used_and_decide_the_amount(client):
    plan = _plan(client, goal="10K", weekdays=[0, 2, 5], weeks=4)

    assert plan["weekdays"] == [0, 2, 5]
    assert plan["total"] == 12
    assert {date.fromisoformat(s["date"]).weekday() for s in plan["sessions"]} == {0, 2, 5}

    longs = [s for s in plan["sessions"] if s["title"] == "Lange duurloop"]
    assert {date.fromisoformat(s["date"]).weekday() for s in longs} == {5}


@pytest.mark.parametrize("weekdays", [[1], [7, 1], [-1, 2]])
def test_invalid_days_are_refused(client, weekdays):
    response = client.post("/api/plans/", json={"goal": "10K", "weekdays": weekdays})
    assert response.status_code == 422


def test_rescheduling_changes_the_days_and_the_amount(client):
    _plan(client, goal="10K", sessions_per_week=4, weeks=8)

    response = client.put("/api/plans/active/schedule", json={"weekdays": [1, 4, 6]})
    assert response.status_code == 200, response.text
    plan = response.json()

    assert plan["weekdays"] == [1, 4, 6]
    assert plan["total"] == 24
    assert {date.fromisoformat(s["date"]).weekday() for s in plan["sessions"]} == {1, 4, 6}


def test_rescheduling_keeps_what_is_past(client):
    start = MONDAY - timedelta(weeks=2)
    response = client.post("/api/plans/", json={"goal": "10K", "weeks": 8})
    plan_id = response.json()["id"]

    from app.database import SessionLocal
    from app.models.training_plan import PlanSession, TrainingPlan

    with SessionLocal() as db:
        plan = db.get(TrainingPlan, plan_id)
        plan.start_date = start.isoformat()
        plan.sessions.append(
            PlanSession(
                date=start.isoformat(),
                week=1,
                sport="RUNNING",
                title="Al gedaan",
                description="",
            )
        )
        db.commit()

    plan = client.put("/api/plans/active/schedule", json={"weekdays": [TODAY.weekday(), (TODAY.weekday() + 2) % 7]}).json()
    titles = [s["title"] for s in plan["sessions"]]

    assert "Al gedaan" in titles
    assert all(
        s["date"] >= TODAY.isoformat() or s["title"] == "Al gedaan"
        for s in plan["sessions"]
    )


def test_rescheduling_without_a_plan(client):
    response = client.put("/api/plans/active/schedule", json={"weekdays": [1, 3]})
    assert response.status_code == 404


def test_rescheduling_keeps_the_race_day(client):
    race = next_monday(TODAY) + timedelta(weeks=9, days=6)
    _plan(client, race_date=race.isoformat(), sessions_per_week=4)

    plan = client.put("/api/plans/active/schedule", json={"weekdays": [0, 3]}).json()

    assert plan["sessions"][-1]["title"] == "Wedstrijddag"
    assert plan["sessions"][-1]["date"] == race.isoformat()


def test_a_session_can_be_moved_and_resized(client):
    plan = _plan(client, goal="10K", weeks=4)
    session = next(s for s in plan["sessions"] if s["distance"])
    new_day = date.fromisoformat(plan["start_date"]) + timedelta(days=9)

    response = client.patch(
        f"/api/plans/sessions/{session['id']}",
        json={"date": new_day.isoformat(), "distance": 7500, "duration": 2400},
    )
    assert response.status_code == 200, response.text

    changed = next(s for s in response.json()["sessions"] if s["id"] == session["id"])

    assert changed["date"] == new_day.isoformat()
    assert changed["week"] == 2
    assert changed["distance"] == 7500
    assert changed["duration"] == 2400


def _future_plan(client, **body):
    """A plan that starts next Monday, with today in the week before it."""
    return _plan(client, goal="10K", weeks=4, weekdays=[1, 3, 6], **body)


def test_a_session_can_move_to_before_the_start_of_the_plan(client):
    plan = _future_plan(client)
    session = plan["sessions"][0]

    response = client.patch(f"/api/plans/sessions/{session['id']}", json={"date": TODAY.isoformat()})
    assert response.status_code == 200, response.text

    moved = response.json()
    row = next(s for s in moved["sessions"] if s["id"] == session["id"])

    assert row["date"] == TODAY.isoformat()
    assert row["week"] == 1
    assert moved["start_date"] == MONDAY.isoformat()


def test_starting_earlier_renumbers_the_other_weeks(client):
    plan = _future_plan(client)
    first, second = plan["sessions"][0], plan["sessions"][1]
    last_week = plan["sessions"][-1]["week"]

    moved = client.patch(f"/api/plans/sessions/{first['id']}", json={"date": TODAY.isoformat()}).json()

    assert next(s for s in moved["sessions"] if s["id"] == second["id"])["week"] == second["week"] + 1
    assert max(s["week"] for s in moved["sessions"]) == last_week + 1
    assert moved["weeks"][0]["week"] == 1


def test_a_session_cannot_move_to_a_week_long_gone(client):
    plan = _future_plan(client)
    session = plan["sessions"][0]
    day = MONDAY - timedelta(days=1)

    response = client.patch(f"/api/plans/sessions/{session['id']}", json={"date": day.isoformat()})

    assert response.status_code == 422
    assert client.get("/api/plans/active").json()["start_date"] == plan["start_date"]


def _extra(client, day=TODAY, sport="RUNNING", title="Extra loop", **body):
    return client.post(
        "/api/plans/sessions",
        json={"date": day.isoformat(), "sport": sport, "title": title, **body},
    )


def test_an_extra_session_today_joins_a_plan_that_starts_later(client):
    plan = _future_plan(client)
    total = plan["total"]

    response = _extra(client, distance=6000)
    assert response.status_code == 200, response.text

    updated = response.json()
    row = next(s for s in updated["sessions"] if s["title"] == "Extra loop")

    assert updated["total"] == total + 1
    assert updated["start_date"] == MONDAY.isoformat()
    assert row["week"] == 1
    assert row["distance"] == 6000
    assert row["completed"] is False
    assert row["description"]
    assert updated["weeks"][0]["planned_meters"] == 6000


def test_doing_an_extra_session_completes_it(client):
    _future_plan(client)
    _extra(client, distance=6000)

    _run(client, TODAY, distance=6100, duration=2200)

    row = next(
        s for s in client.get("/api/plans/active").json()["sessions"]
        if s["title"] == "Extra loop"
    )

    assert row["completed"] is True
    assert row["compliance"] == "ON_TARGET"
    assert row["actual"]["distance"] == 6100

    labels = [event["label"] for event in _profile(client)["recent"]]
    assert "Plan: Extra loop" in labels


def test_extra_sessions_count_for_the_week_and_the_outlook(client):
    plan = _future_plan(client)
    day = date.fromisoformat(plan["start_date"]) + timedelta(days=4)
    before = next(w for w in plan["weeks"] if w["week"] == 1)["planned_meters"]

    updated = _extra(client, day=day, distance=5000).json()

    assert updated["start_date"] == plan["start_date"]
    assert next(w for w in updated["weeks"] if w["week"] == 1)["planned_meters"] == before + 5000


def test_an_extra_session_can_be_moved_and_removed(client):
    _future_plan(client)
    row = next(s for s in _extra(client).json()["sessions"] if s["title"] == "Extra loop")
    tomorrow = TODAY + timedelta(days=1)

    moved = client.patch(f"/api/plans/sessions/{row['id']}", json={"date": tomorrow.isoformat()})
    assert next(s for s in moved.json()["sessions"] if s["id"] == row["id"])["date"] == tomorrow.isoformat()

    assert client.delete(f"/api/plans/sessions/{row['id']}").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"date": (MONDAY - timedelta(days=1)).isoformat(), "sport": "RUNNING", "title": "Te oud"},
        {"date": TODAY.isoformat(), "sport": "CHESS", "title": "Schaken"},
        {"date": TODAY.isoformat(), "sport": "RUNNING", "title": ""},
        {"date": TODAY.isoformat(), "sport": "RUNNING", "title": "Min", "distance": -1},
    ],
)
def test_impossible_extra_sessions_are_refused(client, body):
    _future_plan(client)

    assert client.post("/api/plans/sessions", json=body).status_code == 422


def test_an_extra_session_needs_a_plan(client):
    assert _extra(client).status_code == 404


def test_two_runs_on_a_day_keep_their_own_calendar_entry(client):
    _future_plan(client)
    _extra(client, title="Ochtend")
    _extra(client, title="Avond")

    text = _unfold(client.get("/api/calendar.ics").text)
    uids = [line for line in text.split("\r\n") if line.startswith("UID:")]

    assert len(uids) == len(set(uids))


def test_a_later_end_date_follows_a_moved_session(client):
    plan = _plan(client, goal="10K", weeks=2, sessions_per_week=2)
    last = plan["sessions"][-1]
    day = date.fromisoformat(last["date"]) + timedelta(days=5)

    updated = client.patch(f"/api/plans/sessions/{last['id']}", json={"date": day.isoformat()}).json()

    assert updated["end_date"] == day.isoformat()


def test_a_session_can_be_deleted_but_not_the_last_one(client):
    plan = _plan(client, goal="10K", weeks=2, sessions_per_week=2)

    for session in plan["sessions"][:-1]:
        assert client.delete(f"/api/plans/sessions/{session['id']}").status_code == 200

    last = plan["sessions"][-1]

    assert client.delete(f"/api/plans/sessions/{last['id']}").status_code == 422
    assert client.delete("/api/plans/sessions/999999").status_code == 404


# iCal


def _unfold(text):
    return text.replace("\r\n ", "")


def test_calendar_export_is_valid_ical(client):
    plan = _plan(client, goal="10K", weeks=2, sessions_per_week=2)

    response = client.get("/api/calendar.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "attachment" not in response.headers.get("content-disposition", "")

    raw = response.text
    text = _unfold(raw)

    assert raw.startswith("BEGIN:VCALENDAR\r\n")
    assert raw.endswith("END:VCALENDAR\r\n")
    assert text.count("BEGIN:VEVENT") == plan["total"]
    assert "\n" not in raw.replace("\r\n", "")
    assert all(len(line.encode()) <= 75 for line in raw.split("\r\n"))

    first = plan["sessions"][0]
    compact = first["date"].replace("-", "")
    next_day = (date.fromisoformat(first["date"]) + timedelta(days=1)).isoformat().replace("-", "")

    assert f"DTSTART;VALUE=DATE:{compact}" in text
    assert f"DTEND;VALUE=DATE:{next_day}" in text


def test_calendar_escapes_text_and_folds_long_accents(client):
    plan = _plan(client, goal="10K", weeks=2, sessions_per_week=2)
    session = plan["sessions"][0]

    client.patch(
        f"/api/plans/sessions/{session['id']}",
        json={"title": "Kracht; been, rug", "description": "é" * 200},
    )

    raw = client.get("/api/calendar.ics").content
    assert all(len(line) <= 75 for line in raw.split(b"\r\n"))

    text = _unfold(raw.decode("utf-8"))

    assert r"SUMMARY:Kracht\; been\, rug" in text
    assert "é" * 200 in text


def test_a_subscription_stays_valid_without_a_plan(client):
    response = client.get("/api/calendar.ics")
    text = _unfold(response.text)

    assert response.status_code == 200
    assert text.startswith("BEGIN:VCALENDAR")
    assert text.endswith("END:VCALENDAR\r\n")
    assert "BEGIN:VEVENT" not in text


def test_a_subscription_asks_to_be_refreshed_and_is_not_a_download(client):
    response = client.get("/api/calendar.ics")

    assert "REFRESH-INTERVAL;VALUE=DURATION:PT1H" in response.text
    assert "X-PUBLISHED-TTL:PT1H" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_the_same_address_follows_a_new_plan(client):
    _plan(client, goal="10K", weeks=2, sessions_per_week=2)
    first = client.get("/api/calendar.ics").text

    plan = _plan(client, goal="5K", weeks=3, sessions_per_week=3)
    second = _unfold(client.get("/api/calendar.ics").text)

    assert second != first
    assert second.count("BEGIN:VEVENT") == plan["total"]
    assert "X-WR-CALNAME:TrainMetrics" in second


def test_calendar_uids_survive_rescheduling_on_the_same_day(client):
    _plan(client, goal="10K", weeks=2, weekdays=[1, 6])
    before = _unfold(client.get("/api/calendar.ics").text)

    client.put("/api/plans/active/schedule", json={"weekdays": [1, 6]})
    after = _unfold(client.get("/api/calendar.ics").text)

    uids = lambda text: sorted(l for l in text.split("\r\n") if l.startswith("UID:"))

    assert uids(before) == uids(after)
    assert len(set(uids(after))) == len(uids(after))


# Per sport


def test_breakdown_per_sport(client):
    day = MONDAY - timedelta(weeks=1)

    _run(client, day, distance=10000, duration=3000)
    _run(client, day - timedelta(days=1), distance=5000, duration=1800)
    _run(client, day, distance=40000, duration=6000, sport="CYCLING")
    _run(client, day, distance=1500, duration=2400, sport="SWIMMING")
    _lift(client, _exercise(client), day, weight=60, reps=10)

    result = client.get("/api/analytics/sports").json()
    sports = {row["sport"]: row for row in result["sports"]}

    assert [row["sport"] for row in result["sports"]] == [
        "RUNNING", "CYCLING", "SWIMMING", "STRENGTH",
    ]

    run = sports["RUNNING"]
    assert run["sessions"] == 2
    assert run["distance_meters"] == 15000
    assert run["duration_seconds"] == 4800
    assert run["average_speed"] == 3.125
    assert run["longest"]["distance"] == 10000
    assert run["fastest"]["duration"] == 3000
    assert run["strength"] is None
    assert len(run["weekly"]) == 26
    assert run["last_28_days"] == 2

    lift = sports["STRENGTH"]
    assert lift["strength"]["volume_kg"] == 600
    assert lift["strength"]["sets"] == 1
    assert lift["strength"]["reps"] == 10
    assert lift["strength"]["best_lift"]["exercise"] == "Bench"
    assert lift["average_speed"] is None

    shares = sum(row["share_of_time"] for row in result["sports"])
    assert shares == pytest.approx(1, abs=0.01)


def test_breakdown_period_filters_totals_but_not_the_trend_chart(client):
    _run(client, TODAY - timedelta(days=100))
    _run(client, TODAY - timedelta(days=10))

    recent = client.get("/api/analytics/sports", params={"days": 30}).json()["sports"][0]
    everything = client.get("/api/analytics/sports").json()["sports"][0]

    assert recent["sessions"] == 1
    assert everything["sessions"] == 2
    assert recent["weekly"] == everything["weekly"]


def test_breakdown_does_not_count_a_swim_without_distance_in_its_speed(client):
    day = TODAY - timedelta(days=3)

    _run(client, day, distance=1000, duration=1000, sport="SWIMMING")
    _run(client, day - timedelta(days=1), distance=None, duration=5000, sport="SWIMMING")

    swim = client.get("/api/analytics/sports").json()["sports"][0]

    assert swim["average_speed"] == 1
    assert swim["fastest"]["speed"] == 1


def test_short_efforts_are_not_a_fastest_pace(client):
    _run(client, TODAY - timedelta(days=3), distance=500, duration=60)

    assert client.get("/api/analytics/sports").json()["sports"][0]["fastest"] is None


def test_breakdown_without_data(client):
    assert client.get("/api/analytics/sports").json()["sports"] == []


# Sleep and recovery


def _night(db, day, hrv, score=80):
    from app.models.sleep_night import SleepNight

    db.add(SleepNight(user_id=1, night=day.isoformat(), hrv_ms=hrv, sleep_score=score, asleep_seconds=27000))


def _nights(values, last_score=80, last_day=TODAY):
    from app.database import SessionLocal

    with SessionLocal() as db:
        count = len(values)

        for index, hrv in enumerate(values):
            day = last_day - timedelta(days=count - 1 - index)
            _night(db, day, hrv, last_score if index == count - 1 else 80)

        db.commit()


@pytest.mark.parametrize(
    "last, status",
    [(90, "GOOD"), (80, "OK"), (78.5, "OK"), (70, "LOW")],
)
def test_estimated_recovery_compares_with_your_own_normal(client, last, status):
    _nights([78, 82] * 7 + [last])

    recovery = client.get("/api/analytics/sleep").json()["recovery"]

    assert recovery["source"] == "ESTIMATE"
    assert recovery["status"] == status
    assert recovery["baseline_ms"] == 80
    assert recovery["baseline_nights"] == 14


@pytest.mark.parametrize(
    "polar, status",
    [(1, "LOW"), (2, "LOW"), (3, "OK"), (4, "OK"), (5, "GOOD"), (6, "GOOD")],
)
def test_polars_own_verdict_goes_first(client, polar, status):
    from app.database import SessionLocal
    from app.models.sleep_night import SleepNight

    _nights([78, 82] * 7 + [60])

    with SessionLocal() as db:
        db.get(SleepNight, (1, TODAY.isoformat())).recharge_status = polar
        db.commit()

    recovery = client.get("/api/analytics/sleep").json()["recovery"]

    assert recovery["source"] == "POLAR"
    assert recovery["recharge_status"] == polar
    assert recovery["status"] == status


def test_recovery_needs_enough_nights(client):
    _nights([80, 80, 80])

    result = client.get("/api/analytics/sleep").json()

    assert result["recovery"] is None
    assert result["last_night"]["hrv_ms"] == 80


def test_old_sleep_data_is_not_called_recent(client):
    _nights([80] * 8, last_day=TODAY - timedelta(days=10))

    assert client.get("/api/analytics/sleep").json()["is_recent"] is False


def test_sleep_without_data(client):
    result = client.get("/api/analytics/sleep").json()

    assert result["last_night"] is None
    assert result["nights"] == []


# Correcting a distance


def test_a_corrected_distance_updates_the_speed(client):
    workout = _run(client, TODAY - timedelta(days=2), distance=None, duration=1500, sport="SWIMMING")

    response = client.patch(f"/api/workouts/{workout['id']}/endurance", json={"distance": 1000})

    assert response.status_code == 200, response.text
    assert response.json()["distance"] == 1000
    assert response.json()["average_speed"] == 0.67

    breakdown = client.get("/api/analytics/sports").json()["sports"][0]
    assert breakdown["distance_meters"] == 1000
