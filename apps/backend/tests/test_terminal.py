import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_create_list_and_close_session(client):
    resp = client.post("/api/terminal/sessions", json={"shell": "powershell"})
    assert resp.status_code == 200
    session = resp.json()
    assert session["alive"] is True
    assert session["shell"] == "powershell"

    listing = client.get("/api/terminal/sessions").json()
    assert any(s["id"] == session["id"] for s in listing["sessions"])

    close_resp = client.delete(f"/api/terminal/sessions/{session['id']}")
    assert close_resp.status_code == 200
    assert close_resp.json()["closed"] is True


def test_unknown_shell_rejected(client):
    resp = client.post("/api/terminal/sessions", json={"shell": "zsh"})
    assert resp.status_code == 400


def test_real_command_roundtrip_via_websocket(client):
    create = client.post("/api/terminal/sessions", json={"shell": "powershell"})
    session_id = create.json()["id"]

    with client.websocket_connect(f"/ws/terminal/{session_id}") as ws:
        backlog = ws.receive_json()
        assert backlog["type"] == "backlog"

        ws.send_json({"type": "input", "data": "echo CICIBYTE_TERMINAL_TEST\r"})

        collected = ""
        deadline = time.time() + 8
        while "CICIBYTE_TERMINAL_TEST" not in collected and time.time() < deadline:
            msg = ws.receive_json()
            if msg["type"] == "output":
                collected += msg["data"]

        assert "CICIBYTE_TERMINAL_TEST" in collected

    # history endpoint should also contain it (used by "Send output to AI")
    history = client.get(f"/api/terminal/sessions/{session_id}/history").json()["history"]
    assert "CICIBYTE_TERMINAL_TEST" in history

    client.delete(f"/api/terminal/sessions/{session_id}")


def test_close_session_marks_not_alive_and_rejects_double_close(client):
    create = client.post("/api/terminal/sessions", json={"shell": "powershell"})
    session_id = create.json()["id"]

    close_resp = client.delete(f"/api/terminal/sessions/{session_id}")
    assert close_resp.status_code == 200

    second_close = client.delete(f"/api/terminal/sessions/{session_id}")
    assert second_close.status_code == 404
