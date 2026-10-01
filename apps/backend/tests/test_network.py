from fastapi.testclient import TestClient

from app.main import app
from app.runtime_state import set_network_mode

client = TestClient(app)


def teardown_function(_):
    # keep tests isolated from each other
    set_network_mode("offline")


def test_get_mode_defaults_offline():
    resp = client.get("/api/network/mode")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "offline"


def test_set_mode_valid():
    resp = client.put("/api/network/mode", json={"mode": "internet"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "internet"
    assert client.get("/api/health").json()["network_mode"] == "internet"


def test_set_mode_invalid_rejected():
    resp = client.put("/api/network/mode", json={"mode": "not-a-mode"})
    assert resp.status_code == 400


def test_pull_blocked_when_offline():
    set_network_mode("offline")
    resp = client.post("/api/models/pull", json={"ollama_tag": "dolphin3:8b"})
    assert resp.status_code == 409
