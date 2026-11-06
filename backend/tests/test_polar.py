import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app.services.polar import parse_duration


RUN = {
    "id": "abc",
    "start_time": "2026-10-13T10:40:02",
    "start_time_utc_offset": 120,
    "duration": "PT50M",
    "calories": 600,
    "distance": 10000.0,
    "heart_rate": {"average": 150, "maximum": 175},
    "sport": "RUNNING",
    "detailed_sport_info": "RUNNING",
    "running-index": 51,
}

RIDE = {
    "id": "def",
    "start_time": "2026-10-14T10:00:00",
    "duration": "PT1H",
    "distance": 30000,
    "sport": "OTHER",
    "detailed_sport_info": "ROAD_BIKING",
}

LIFT = {
    "id": "ghi",
    "start_time": "2026-10-15T18:00:00",
    "duration": "PT45M",
    "sport": "STRENGTH_TRAINING",
}


@pytest.fixture
def fake_polar(monkeypatch):
    """A local server that answers like Polar's token and exercise endpoints."""
    state = {"exercises": [RUN, RIDE, LIFT], "status": 200, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status, body=None):
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode()
            state["requests"].append(("POST", self.path, self.headers, body))

            if self.path == "/token":
                self._reply(200, {"access_token": "secret-token", "x_user_id": 42})
            else:
                self._reply(200, {})

        def do_GET(self):
            state["requests"].append(("GET", self.path, self.headers, ""))
            self._reply(state["status"], state["exercises"])

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"

    monkeypatch.setenv("POLAR_CLIENT_ID", "client")
    monkeypatch.setenv("POLAR_CLIENT_SECRET", "secret")
    monkeypatch.setenv("POLAR_API_URL", url)
    monkeypatch.setenv("POLAR_TOKEN_URL", f"{url}/token")
    monkeypatch.setenv("POLAR_AUTH_URL", f"{url}/authorize")

    yield state

    server.shutdown()
    server.server_close()


def _link(client):
    response = client.get("/api/polar/connect", follow_redirects=False)
    query = parse_qs(urlparse(response.headers["location"]).query)

    assert query["scope"] == ["accesslink.read_all"]
    assert "redirect_uri" not in query

    return client.get(
        "/api/polar/callback",
        params={"code": "one-time", "state": query["state"][0]},
        follow_redirects=False,
    )


@pytest.mark.parametrize(
    "value, seconds",
    [
        ("PT2H44M", 9840),
        ("PT50M", 3000),
        ("PT1H2M3.6S", 3724),
        ("PT45S", 45),
        ("nonsense", None),
        ("PT", None),
        (None, None),
    ],
)
def test_parse_duration(value, seconds):
    assert parse_duration(value) == seconds


def test_linking_registers_the_user_and_never_exposes_the_token(client, fake_polar):
    assert client.get("/api/polar/status").json()["linked"] is False

    response = _link(client)
    assert response.headers["location"] == "/#profiel?polar=gekoppeld"

    method, path, headers, body = fake_polar["requests"][0]
    assert path == "/token"
    assert headers["Authorization"].startswith("Basic ")
    assert "code=one-time" in body

    assert fake_polar["requests"][1][1] == "/v3/users"
    assert fake_polar["requests"][1][2]["Authorization"] == "Bearer secret-token"

    status = client.get("/api/polar/status")
    assert status.json()["linked"] is True
    assert "secret-token" not in status.text


def test_callback_refuses_an_unknown_state(client, fake_polar):
    response = client.get(
        "/api/polar/callback",
        params={"code": "x", "state": "forged"},
        follow_redirects=False,
    )

    assert response.headers["location"] == "/#profiel?polar=geweigerd"
    assert fake_polar["requests"] == []
    assert client.get("/api/polar/status").json()["linked"] is False


def test_connect_without_credentials_explains_itself(client, monkeypatch):
    monkeypatch.delenv("POLAR_CLIENT_ID", raising=False)
    monkeypatch.delenv("POLAR_CLIENT_SECRET", raising=False)

    assert client.get("/api/polar/connect", follow_redirects=False).status_code == 503


def test_sync_imports_once_and_keeps_the_running_index(client, fake_polar):
    _link(client)

    first = client.post("/api/polar/sync").json()
    assert first == {"imported": 3, "updated": 0, "skipped": 0}

    second = client.post("/api/polar/sync").json()
    assert second == {"imported": 0, "updated": 0, "skipped": 3}

    workouts = {w["date"]: w for w in client.get("/api/workouts/").json()}

    run = workouts["2026-10-13T10:40:02"]["endurance_activity"]
    assert run["activity_type"] == "RUNNING"
    assert run["running_index"] == 51
    assert run["duration"] == 3000
    assert run["average_speed"] == 3.33
    assert run["average_heart_rate"] == 150

    ride = workouts["2026-10-14T10:00:00"]["endurance_activity"]
    assert ride["activity_type"] == "CYCLING"

    lift = workouts["2026-10-15T18:00:00"]
    assert lift["type"] == "STRENGTH"
    assert lift["endurance_activity"] is None


def test_sync_enriches_the_same_training_from_a_file(client, fake_polar):
    _link(client)

    client.post(
        "/api/workouts/complete",
        json={
            "user_id": 1,
            "date": "2026-10-13T10:40:02",
            "type": "ENDURANCE",
            "endurance_activity": {"activity_type": "RUNNING", "distance": 10000},
        },
    )
    fake_polar["exercises"] = [RUN]

    assert client.post("/api/polar/sync").json()["updated"] == 1

    workouts = client.get("/api/workouts/").json()
    assert len(workouts) == 1
    assert workouts[0]["endurance_activity"]["running_index"] == 51


def test_sync_without_a_link_or_with_a_revoked_token(client, fake_polar):
    assert client.post("/api/polar/sync").status_code == 401

    _link(client)
    fake_polar["status"] = 401

    assert client.post("/api/polar/sync").status_code == 401


def test_sync_handles_no_new_exercises(client, fake_polar):
    _link(client)
    fake_polar["exercises"] = []

    assert client.post("/api/polar/sync").json()["imported"] == 0


def test_unlink_keeps_the_trainings(client, fake_polar):
    _link(client)
    client.post("/api/polar/sync")

    assert client.delete("/api/polar/link").status_code == 200
    assert client.get("/api/polar/status").json()["linked"] is False
    assert len(client.get("/api/workouts/").json()) == 3
