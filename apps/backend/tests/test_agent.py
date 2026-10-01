import time

import pytest
from fastapi.testclient import TestClient

from app.agent import db as agent_db
from app.agent.manager import get_agent_manager
from app.main import app


@pytest.fixture(scope="module")
def client():
    # Agent routes depend on state set up in the app's lifespan (SQLite db,
    # AgentManager) — must enter TestClient as a context manager to trigger it.
    with TestClient(app) as c:
        yield c


def test_create_run_with_explicit_steps_completes(client):
    resp = client.post(
        "/api/agent/runs",
        json={"goal": "say hi", "steps": [{"type": "stub_echo", "params": {"text": "hello"}}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    run_id = body["run"]["id"]
    assert body["run"]["status"] in ("pending", "running")
    assert len(body["steps"]) == 1

    for _ in range(50):
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)

    assert detail["run"]["status"] == "completed"
    assert detail["steps"][0]["status"] == "done"
    assert detail["steps"][0]["output"]["echoed"] == "hello"


def test_create_run_without_explicit_steps_uses_trivial_plan(client):
    resp = client.post("/api/agent/runs", json={"goal": "just echo my goal text"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["steps"]) == 1
    assert body["steps"][0]["type"] == "stub_echo"


def test_unknown_step_type_rejected(client):
    resp = client.post(
        "/api/agent/runs",
        json={"goal": "bad plan", "steps": [{"type": "nmap", "params": {}}]},
    )
    assert resp.status_code == 400


def test_kill_switch_stops_a_sleeping_run(client):
    resp = client.post(
        "/api/agent/runs",
        json={"goal": "long task", "steps": [{"type": "stub_sleep", "params": {"seconds": 30}}]},
    )
    run_id = resp.json()["run"]["id"]

    # give it a moment to actually enter the sleep step
    for _ in range(20):
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["steps"][0]["status"] == "running":
            break
        time.sleep(0.05)
    assert detail["steps"][0]["status"] == "running"

    stop_resp = client.post(f"/api/agent/runs/{run_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["stopped"] is True

    detail = client.get(f"/api/agent/runs/{run_id}").json()
    assert detail["run"]["status"] == "stopped"
    assert detail["steps"][0]["status"] == "stopped"


def test_stop_on_inactive_run_returns_409(client):
    resp = client.post("/api/agent/runs", json={"goal": "quick", "steps": [{"type": "stub_echo", "params": {"text": "x"}}]})
    run_id = resp.json()["run"]["id"]
    for _ in range(50):
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] != "running":
            break
        time.sleep(0.05)

    stop_resp = client.post(f"/api/agent/runs/{run_id}/stop")
    assert stop_resp.status_code == 409


def test_list_runs_reports_active_flag(client):
    resp = client.post(
        "/api/agent/runs",
        json={"goal": "long task 2", "steps": [{"type": "stub_sleep", "params": {"seconds": 10}}]},
    )
    run_id = resp.json()["run"]["id"]
    listing = client.get("/api/agent/runs").json()
    match = next(r for r in listing["runs"] if r["id"] == run_id)
    assert match["is_active"] is True
    client.post(f"/api/agent/runs/{run_id}/stop")


def test_failed_step_marks_run_failed_after_retries(client):
    resp = client.post(
        "/api/agent/runs",
        json={"goal": "bad sleep", "steps": [{"type": "stub_sleep", "params": {"seconds": -1}}]},
    )
    run_id = resp.json()["run"]["id"]
    for _ in range(50):
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)
    assert detail["run"]["status"] == "failed"
    assert detail["steps"][0]["status"] == "failed"


def test_crash_recovery_marks_stuck_running_run_interrupted(client):
    import asyncio

    # Simulate a backend that died mid-run: a run+step stuck at "running"
    # with no corresponding in-memory asyncio task (there never was one in
    # this test — that's exactly what a crash looks like from the DB's
    # point of view).
    run = agent_db.create_run("crashed mid-flight", status="running")
    steps = agent_db.create_steps(run["id"], [{"type": "stub_sleep", "params": {"seconds": 5}}])
    agent_db.update_step(steps[0]["id"], "running", started_at="2026-01-01T00:00:00+00:00")

    recovered = asyncio.run(get_agent_manager().recover_interrupted_runs())
    assert recovered >= 1

    detail = client.get(f"/api/agent/runs/{run['id']}").json()
    assert detail["run"]["status"] == "interrupted"
    assert detail["steps"][0]["status"] == "pending"


def test_resume_after_crash_reruns_from_last_checkpoint(client):
    run_id = agent_db.create_run("resume me", status="interrupted")["id"]
    agent_db.create_steps(
        run_id,
        [
            {"type": "stub_echo", "params": {"text": "first"}},
            {"type": "stub_echo", "params": {"text": "second"}},
        ],
    )
    steps = agent_db.get_steps(run_id)
    agent_db.update_step(steps[0]["id"], "done", output={"echoed": "first"})
    # step[1] stays "pending" — simulates a crash after step 0 checkpointed

    resp = client.post(f"/api/agent/runs/{run_id}/resume")
    assert resp.status_code == 200

    for _ in range(50):
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)

    assert detail["run"]["status"] == "completed"
    assert detail["steps"][0]["output"]["echoed"] == "first"  # untouched, not re-run
    assert detail["steps"][1]["status"] == "done"


def test_discard_run(client):
    resp = client.post("/api/agent/runs", json={"goal": "to discard", "steps": [{"type": "stub_echo", "params": {"text": "x"}}]})
    run_id = resp.json()["run"]["id"]
    for _ in range(50):
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)

    discard_resp = client.post(f"/api/agent/runs/{run_id}/discard")
    assert discard_resp.status_code == 200
    assert discard_resp.json()["run"]["status"] == "discarded"
