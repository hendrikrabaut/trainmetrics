import json
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.services.proposals import parse_model_sessions


TODAY = date.today()
SUNDAY = TODAY + timedelta(days=6 - TODAY.weekday())
ALL_DAYS = [1, 3, 6]


def _answer(*sessions, rationale="Rustig opbouwen."):
    return {"rationale": rationale, "sessions": list(sessions)}


def _session(day=TODAY, sport="RUNNING", title="Rustige loop", km=6, minutes=None):
    return {
        "date": day.isoformat(),
        "sport": sport,
        "title": title,
        "description": "Op je gemak.",
        "distance_km": km,
        "duration_min": minutes,
    }


@pytest.fixture
def model(monkeypatch):
    """A stand-in for Ollama. Set its reply, and read what it was asked."""
    state = {"reply": _answer(_session()), "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(body)

            reply = state["reply"]
            content = reply if isinstance(reply, str) else json.dumps(reply)
            data = json.dumps({"message": {"content": content}}).encode()

            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("OLLAMA_URL", f"http://127.0.0.1:{server.server_port}")

    yield state

    server.shutdown()
    server.server_close()


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")


def _propose(client, **body):
    response = client.post(
        "/api/plans/proposal",
        json={"goal": "10K", "weekdays": ALL_DAYS, "weeks": 4, **body},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, day, distance=10000, duration=3000):
    response = client.post(
        "/api/workouts/complete",
        json={
            "date": day.isoformat(),
            "type": "ENDURANCE",
            "endurance_activity": {"activity_type": "RUNNING", "distance": distance, "duration": duration},
        },
    )
    assert response.status_code == 200, response.text


# Nothing happens without approval


def test_a_proposal_does_not_touch_the_planning(client, model):
    assert client.get("/api/plans/proposal").json() is None

    proposal = _propose(client)

    assert proposal["source"] in ("MODEL", "MIXED")
    assert client.get("/api/plans/active").json() is None
    assert client.get("/api/plans/proposal").json()["goal"] == "10K"


def test_a_proposal_leaves_the_current_plan_alone_until_approved(client, model):
    current = client.post("/api/plans/", json={"goal": "5K", "weeks": 4}).json()

    _propose(client)

    assert client.get("/api/plans/active").json()["id"] == current["id"]

    approved = client.post("/api/plans/proposal/approve").json()

    assert approved["id"] != current["id"]
    assert client.get("/api/plans/active").json()["id"] == approved["id"]
    assert client.get("/api/plans/proposal").json() is None


def test_discarding_changes_nothing(client, model):
    _propose(client)

    assert client.delete("/api/plans/proposal").status_code == 200
    assert client.get("/api/plans/proposal").json() is None
    assert client.get("/api/plans/active").json() is None
    assert client.delete("/api/plans/proposal").status_code == 404


def test_approving_without_a_proposal(client):
    assert client.post("/api/plans/proposal/approve").status_code == 404


# The model


def test_the_model_gets_my_data_and_wishes(client, model):
    _run(client, TODAY - timedelta(days=3), distance=12345)

    _propose(client, notes="Ik wil vandaag en zondag ook lopen", goal="HALF", race_date=(TODAY + timedelta(days=16)).isoformat())

    request = model["requests"][0]
    content = request["messages"][1]["content"]

    assert "12345" in content
    assert "Ik wil vandaag en zondag ook lopen" in content
    assert "halve marathon" in content
    assert (TODAY + timedelta(days=16)).isoformat() in content
    assert request["format"]["required"] == ["rationale", "sessions"]


def test_the_model_proposal_is_shown_as_its_own(client, model):
    model["reply"] = _answer(_session(TODAY, km=6), _session(SUNDAY, title="Duurloop", km=8), rationale="Omdat het kan.")

    proposal = _propose(client, weeks=2)

    assert proposal["rationale"] == "Omdat het kan."
    assert [row["title"] for row in proposal["sessions"]][:2] == ["Rustige loop", "Duurloop"]
    assert proposal["sessions"][0]["distance"] == 6000
    assert proposal["sessions"][0]["source"] == "MODEL"
    assert proposal["model_error"] is None


def test_the_race_day_stays_where_it_is(client, model):
    race = TODAY + timedelta(days=16)
    model["reply"] = _answer(_session(TODAY), _session(race, title="Verzonnen", km=3))

    proposal = _propose(client, goal="HALF", race_date=race.isoformat())
    rows = [row for row in proposal["sessions"] if row["date"] == race.isoformat()]

    assert [row["title"] for row in rows] == ["Wedstrijddag"]
    assert rows[0]["distance"] == 21098


def test_beyond_six_weeks_the_rules_take_over(client, model):
    proposal = _propose(client, goal="MARATHON", weeks=18)

    assert proposal["source"] == "MIXED"

    sources = {row["source"] for row in proposal["sessions"]}

    assert sources == {"MODEL", "RULES"}

    limit = (TODAY + timedelta(weeks=6)).isoformat()
    assert all(row["date"] <= limit for row in proposal["sessions"] if row["source"] == "MODEL")
    assert all(row["date"] >= limit for row in proposal["sessions"] if row["source"] == "RULES")


@pytest.mark.parametrize(
    "reply",
    [
        "dit is geen json",
        {"rationale": "x"},
        {"rationale": "x", "sessions": []},
        {"rationale": "x", "sessions": "geen lijst"},
        {"sessions": [{"date": "morgen", "sport": "RUNNING", "title": "x"}]},
        ["geen", "object"],
    ],
)
def test_an_unusable_answer_falls_back_to_the_rules(client, model, reply):
    model["reply"] = reply

    proposal = _propose(client)

    assert proposal["source"] == "RULES"
    assert proposal["model_error"]
    assert len(proposal["sessions"]) > 3


def test_no_laptop_still_gives_a_proposal(client, no_model):
    proposal = _propose(client)

    assert proposal["source"] == "RULES"
    assert proposal["model_error"]
    assert client.get("/api/plans/active").json() is None


def test_rules_can_be_asked_for_directly(client, model):
    proposal = _propose(client, use_model=False)

    assert proposal["source"] == "RULES"
    assert model["requests"] == []


def test_model_sessions_outside_the_period_or_nonsense_are_dropped():
    good = _session(TODAY)
    rows = parse_model_sessions(
        [
            good,
            _session(TODAY - timedelta(days=1), title="Te vroeg"),
            _session(TODAY + timedelta(days=99), title="Te laat"),
            {**good, "sport": "SCHAKEN"},
            {**good, "title": " "},
            {**good, "distance_km": -5},
            {**good, "distance_km": "ver", "title": "Geen getal"},
            {**good, "distance_km": 9000, "title": "Te ver"},
            "geen object",
        ],
        TODAY,
        TODAY + timedelta(days=7),
    )

    assert {row["title"] for row in rows} == {"Rustige loop", "Geen getal", "Te ver"}
    assert next(row for row in rows if row["title"] == "Te ver")["distance"] is None


# Editing


def test_i_can_change_add_and_remove_trainings(client, model):
    model["reply"] = _answer(_session(TODAY, km=6), _session(SUNDAY, title="Duurloop", km=8))
    rows = _propose(client, weeks=2)["sessions"]

    first = next(row for row in rows if row["title"] == "Rustige loop")
    first["distance"] = 5000
    first["title"] = "Korte loop"
    rows = [row for row in rows if row["title"] != "Duurloop"]
    rows.append({"date": SUNDAY.isoformat(), "sport": "CYCLING", "title": "Rit", "duration": 3600})

    updated = client.put("/api/plans/proposal", json={"sessions": rows})
    assert updated.status_code == 200, updated.text

    titles = [row["title"] for row in client.get("/api/plans/proposal").json()["sessions"]]

    assert "Korte loop" in titles and "Rit" in titles and "Duurloop" not in titles

    plan = client.post("/api/plans/proposal/approve").json()
    by_title = {row["title"]: row for row in plan["sessions"]}

    assert by_title["Korte loop"]["distance"] == 5000
    assert by_title["Rit"]["sport"] == "CYCLING"
    assert by_title["Rit"]["date"] == SUNDAY.isoformat()
    assert "Duurloop" not in by_title


@pytest.mark.parametrize(
    "row",
    [
        {"date": "morgen", "sport": "RUNNING", "title": "x"},
        {"date": "2030-01-01", "sport": "SCHAKEN", "title": "x"},
        {"date": "2030-01-01", "sport": "RUNNING", "title": ""},
        {"date": "2030-01-01", "sport": "RUNNING", "title": "x", "distance": -1},
    ],
)
def test_invalid_edits_are_refused(client, model, row):
    _propose(client)

    assert client.put("/api/plans/proposal", json={"sessions": [row]}).status_code == 422


def test_an_empty_proposal_cannot_be_approved(client, model):
    _propose(client)
    client.put("/api/plans/proposal", json={"sessions": []})

    assert client.post("/api/plans/proposal/approve").status_code == 422
    assert client.get("/api/plans/active").json() is None


# Approved plans are normal plans


def test_an_approved_plan_works_like_any_other(client, model):
    model["reply"] = _answer(_session(TODAY, km=6), _session(SUNDAY, title="Duurloop", km=8))
    plan = (_propose(client, weeks=2), client.post("/api/plans/proposal/approve").json())[1]

    assert plan["start_date"] == (TODAY - timedelta(days=TODAY.weekday())).isoformat()
    assert plan["weeks"][0]["week"] == 1
    assert plan["weeks"][0]["planned_meters"] >= 14000

    _run(client, TODAY, distance=6000)

    row = next(s for s in client.get("/api/plans/active").json()["sessions"] if s["date"] == TODAY.isoformat())
    assert row["completed"] is True

    assert client.get("/api/calendar.ics").status_code == 200


# The checks


def _warnings(client, model, *sessions, **body):
    model["reply"] = _answer(*sessions)
    return _propose(client, weeks=2, **body)["warnings"]


def test_a_big_jump_in_distance_gets_a_warning(client, model):
    _run(client, TODAY - timedelta(days=7), distance=8000)

    warnings = _warnings(client, model, _session(TODAY + timedelta(days=1), km=15))

    assert any("grote sprong" in warning for warning in warnings)


def test_a_sensible_distance_gets_no_warning(client, model):
    _run(client, TODAY - timedelta(days=7), distance=10000)

    warnings = _warnings(client, model, _session(TODAY + timedelta(days=1), km=10))

    assert not any("grote sprong" in warning for warning in warnings)


def test_a_week_without_rest_gets_a_warning(client, model):
    monday = TODAY - timedelta(days=TODAY.weekday()) + timedelta(weeks=1)
    sessions = [_session(monday + timedelta(days=index), km=4) for index in range(7)]

    assert any("geen rustdag" in warning for warning in _warnings(client, model, *sessions))


def test_a_long_run_just_before_the_race_gets_a_warning(client, model):
    race = TODAY + timedelta(days=16)

    warnings = _warnings(
        client,
        model,
        _session(race - timedelta(days=2), km=15),
        goal="HALF",
        race_date=race.isoformat(),
    )

    assert any("kort voor je wedstrijd" in warning for warning in warnings)


def test_warnings_follow_my_edits(client, model):
    _run(client, TODAY - timedelta(days=7), distance=8000)
    model["reply"] = _answer(_session(TODAY + timedelta(days=1), km=15))

    rows = _propose(client, weeks=2)["sessions"]

    for row in rows:
        if row["distance"] == 15000:
            row["distance"] = 9000

    updated = client.put("/api/plans/proposal", json={"sessions": rows}).json()

    assert not any("15,0 km" in warning for warning in updated["warnings"])


def test_warnings_never_stop_approval(client, model):
    _run(client, TODAY - timedelta(days=7), distance=8000)
    model["reply"] = _answer(_session(TODAY + timedelta(days=1), km=30))

    assert _propose(client, weeks=2)["warnings"]
    assert client.post("/api/plans/proposal/approve").status_code == 200


# Yesterday's run and today's extra training


def test_yesterdays_run_does_not_tick_off_todays_extra_training(client):
    monday = TODAY - timedelta(days=TODAY.weekday())

    if TODAY == monday:
        pytest.skip("Needs an earlier day in this week")

    client.post("/api/plans/", json={"goal": "10K", "weeks": 4, "weekdays": [1, 3, 6]})
    _run(client, TODAY - timedelta(days=1), distance=6000)

    plan = client.post(
        "/api/plans/sessions",
        json={"date": TODAY.isoformat(), "sport": "RUNNING", "title": "Extra", "distance": 6000},
    ).json()

    row = next(s for s in plan["sessions"] if s["title"] == "Extra")

    assert row["completed"] is False
    assert row["actual"] is None


def test_an_unreachable_laptop_does_not_keep_me_waiting(client, monkeypatch):
    import time

    # A port that accepts nothing answers at once; what counts is that the
    # check comes first, with its own short limit.
    from app.services import coach

    asked = []
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(coach, "_chat", lambda *args, **kwargs: asked.append(args))

    started = time.monotonic()
    proposal = _propose(client)

    assert proposal["source"] == "RULES"
    assert asked == []
    assert time.monotonic() - started < coach.REACHABLE_SECONDS + 2


def test_a_race_is_no_big_jump(client, model):
    _run(client, TODAY - timedelta(days=7), distance=10000)
    race = TODAY + timedelta(days=16)

    warnings = _warnings(client, model, _session(TODAY + timedelta(days=1), km=8), goal="HALF", race_date=race.isoformat())

    assert not any("21,1" in warning for warning in warnings)


def test_a_b_race_is_no_big_jump_either(client, no_model):
    _run(client, TODAY - timedelta(days=7), distance=8000)
    day = TODAY + timedelta(days=12)
    client.post("/api/races/", json={"name": "Halve", "date": day.isoformat(), "priority": "B", "goal": "HALF"})

    proposal = _propose(client, weeks=6)

    assert any(row["title"] == "Wedstrijd: Halve" for row in proposal["sessions"])
    assert not any("21,1" in warning for warning in proposal["warnings"])


def test_a_normal_week_after_a_light_one_is_no_alarm(client, model):
    monday = TODAY - timedelta(days=TODAY.weekday())

    for weeks_ago in (2, 3):
        _run(client, monday - timedelta(weeks=weeks_ago), distance=20000)

    next_week = monday + timedelta(weeks=1)
    warnings = _warnings(
        client,
        model,
        _session(next_week, km=5),
        _session(next_week + timedelta(weeks=1), km=18),
    )

    assert not any("drukste week" in warning for warning in warnings)


def test_more_than_my_busiest_week_gets_a_warning(client, model):
    _run(client, TODAY - timedelta(days=7), distance=10000)
    next_week = TODAY - timedelta(days=TODAY.weekday()) + timedelta(weeks=1)

    warnings = _warnings(
        client,
        model,
        _session(next_week, km=9),
        _session(next_week + timedelta(days=2), km=9),
    )

    assert any("drukste week" in warning for warning in warnings)


def test_a_run_from_before_approval_is_not_an_execution_of_the_plan(client, model):
    monday = TODAY - timedelta(days=TODAY.weekday())

    if TODAY == monday:
        pytest.skip("Needs an earlier day in this week")

    _run(client, TODAY - timedelta(days=1), distance=6000)
    model["reply"] = _answer(_session(TODAY, km=6))
    _propose(client, weeks=2)

    plan = client.post("/api/plans/proposal/approve").json()
    row = next(s for s in plan["sessions"] if s["date"] == TODAY.isoformat())

    assert row["completed"] is False
    assert row["actual"] is None

    _run(client, TODAY, distance=6000)

    row = next(
        s for s in client.get("/api/plans/active").json()["sessions"]
        if s["date"] == TODAY.isoformat()
    )

    assert row["completed"] is True
