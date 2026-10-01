from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "hardware" in body
    assert "cpu_model" in body["hardware"]
    assert "ram_total_gb" in body["hardware"]
    assert isinstance(body["hardware"]["gpus"], list)


def test_config_endpoint_exposes_safe_sections_only():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"app", "network", "autonomy"}
