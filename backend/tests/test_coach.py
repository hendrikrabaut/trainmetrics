import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


@pytest.fixture
def fake_ollama(monkeypatch):
    """A local server that answers like Ollama and records what it receives."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, json.loads(body)))

            answer = json.dumps(
                {"message": {"content": "<think>hmm</think>Je trainde goed."}}
            ).encode()

            self.send_response(200)
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    monkeypatch.setenv("OLLAMA_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")

    yield received

    server.shutdown()
    server.server_close()


def test_coach_sends_calculated_data_and_cleans_the_answer(client, fake_ollama):
    client.post(
        "/api/body-measurements/",
        json={"date": "2026-10-01", "weight": 90.4},
    )

    response = client.post("/api/coach/ask", json={"question": "Hoe gaat het?"})

    assert response.status_code == 200, response.text
    assert response.json() == {"answer": "Je trainde goed."}

    path, payload = fake_ollama[0]
    prompt = payload["messages"][1]["content"]

    assert path == "/api/chat"
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert "90.4" in prompt
    assert "Hoe gaat het?" in prompt


def test_coach_reports_when_ollama_is_unreachable(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")

    response = client.post("/api/coach/ask", json={"question": "Hallo"})

    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_coach_refuses_an_empty_question(client):
    response = client.post("/api/coach/ask", json={"question": ""})
    assert response.status_code == 422
