from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_rejects_empty_messages():
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"messages": []})
        data = ws.receive_json()
        assert data["type"] == "error"


def test_chat_rejects_unknown_model():
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"model": "Not-A-Real-Model", "messages": [{"role": "user", "content": "hi"}]})
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "Unknown model" in data["message"]


def test_chat_reports_ollama_unreachable_on_dev_machine_without_it():
    # Qwen3-Coder has an ollama_tag configured, so this exercises the
    # reachability check rather than the "no tag configured" path.
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"model": "Qwen3-Coder", "messages": [{"role": "user", "content": "hi"}]})
        data = ws.receive_json()
        assert data["type"] == "error"
