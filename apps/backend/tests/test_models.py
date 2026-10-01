from fastapi.testclient import TestClient

from app.main import app
from app.models_registry import CATEGORY_ORDER

client = TestClient(app)


def test_model_registry_returns_all_categories():
    resp = client.get("/api/models/registry")
    assert resp.status_code == 200
    body = resp.json()
    categories = {m["category"] for m in body["models"]}
    assert categories == set(CATEGORY_ORDER)


def test_model_registry_has_one_default():
    resp = client.get("/api/models/registry")
    body = resp.json()
    defaults = [m for m in body["models"] if m["default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "Qwen3-Coder"


def test_model_registry_reports_install_status():
    resp = client.get("/api/models/registry")
    body = resp.json()
    assert "ollama_reachable" in body
    for m in body["models"]:
        assert isinstance(m["installed"], bool)
        assert "ollama_tag" in m


def test_ollama_status_fails_soft_when_unreachable():
    # On a dev machine without Ollama installed, this must not raise —
    # it reports unreachable instead (offline-first: Phase 1 §1).
    resp = client.get("/api/models/ollama/status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["reachable"], bool)
    assert isinstance(body["installed_tags"], list)
