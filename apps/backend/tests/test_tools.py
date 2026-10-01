import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime_state import set_autonomy_mode


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def teardown_function(_):
    set_autonomy_mode("SAFE")


def _wait_until_terminal(client, invocation_id, timeout_s=5):
    terminal = {"done", "failed", "denied", "cancelled"}
    deadline = time.time() + timeout_s
    detail = None
    while time.time() < deadline:
        detail = client.get(f"/api/tools/invocations/{invocation_id}").json()
        if detail["status"] in terminal:
            return detail
        time.sleep(0.05)
    return detail


def test_registry_lists_phase4_tools(client):
    resp = client.get("/api/tools/registry")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert {"python", "git", "filesystem_list", "filesystem_read", "filesystem_write", "filesystem_delete"} <= names


def test_unknown_tool_rejected(client):
    resp = client.post("/api/tools/invoke", json={"tool": "nmap", "args": {}})
    assert resp.status_code == 400


def test_low_risk_tool_runs_without_confirmation_even_in_safe_mode(client):
    # filesystem_list is LOW risk but SAFE mode confirms *everything* per
    # the Permission Engine (app/tools/permission.py) -- so this actually
    # verifies SAFE mode gates even a LOW-risk tool, then we approve it.
    set_autonomy_mode("SAFE")
    resp = client.post("/api/tools/invoke", json={"tool": "filesystem_list", "args": {"path": "workspace"}})
    assert resp.status_code == 200
    invocation = resp.json()
    assert invocation["status"] == "pending_confirmation"

    approve_resp = client.post(f"/api/tools/invocations/{invocation['id']}/approve")
    assert approve_resp.status_code == 200

    detail = _wait_until_terminal(client, invocation["id"])
    assert detail["status"] == "done"
    assert isinstance(detail["output"], list)


def test_auto_mode_runs_low_risk_tool_without_confirmation(client):
    set_autonomy_mode("AUTO")
    resp = client.post("/api/tools/invoke", json={"tool": "filesystem_list", "args": {"path": "workspace"}})
    invocation = resp.json()
    assert invocation["status"] == "approved"  # no confirmation needed

    detail = _wait_until_terminal(client, invocation["id"])
    assert detail["status"] == "done"


def test_deny_blocks_execution(client):
    set_autonomy_mode("SAFE")
    resp = client.post("/api/tools/invoke", json={"tool": "filesystem_list", "args": {"path": "workspace"}})
    invocation = resp.json()

    deny_resp = client.post(f"/api/tools/invocations/{invocation['id']}/deny")
    assert deny_resp.status_code == 200

    detail = _wait_until_terminal(client, invocation["id"])
    assert detail["status"] == "denied"
    assert detail["output"] is None


def test_filesystem_path_traversal_rejected(client):
    set_autonomy_mode("FULL")
    resp = client.post("/api/tools/invoke", json={"tool": "filesystem_read", "args": {"path": "../../etc/passwd"}})
    invocation = resp.json()
    detail = _wait_until_terminal(client, invocation["id"])
    assert detail["status"] == "failed"
    assert "outside the allowed roots" in detail["error"]


def test_filesystem_write_then_read_roundtrip(client):
    set_autonomy_mode("FULL")
    write_resp = client.post(
        "/api/tools/invoke",
        json={"tool": "filesystem_write", "args": {"path": "workspace/phase4_test.txt", "content": "hello from tests"}},
    )
    write_detail = _wait_until_terminal(client, write_resp.json()["id"])
    assert write_detail["status"] == "done"

    read_resp = client.post("/api/tools/invoke", json={"tool": "filesystem_read", "args": {"path": "workspace/phase4_test.txt"}})
    read_detail = _wait_until_terminal(client, read_resp.json()["id"])
    assert read_detail["status"] == "done"
    assert read_detail["output"]["content"] == "hello from tests"

    # cleanup
    delete_resp = client.post("/api/tools/invoke", json={"tool": "filesystem_delete", "args": {"path": "workspace/phase4_test.txt"}})
    _wait_until_terminal(client, delete_resp.json()["id"])


def test_python_tool_runs_real_subprocess(client):
    set_autonomy_mode("FULL")
    resp = client.post("/api/tools/invoke", json={"tool": "python", "args": {"code": "print('hello from python tool')"}})
    detail = _wait_until_terminal(client, resp.json()["id"])
    assert detail["status"] == "done"
    assert detail["exit_code"] == 0
    assert "hello from python tool" in detail["stdout"]


def test_git_tool_runs_real_subprocess(client):
    set_autonomy_mode("FULL")
    resp = client.post("/api/tools/invoke", json={"tool": "git", "args": {"args": ["status"]}})
    detail = _wait_until_terminal(client, resp.json()["id"])
    assert detail["status"] == "done"
    assert detail["exit_code"] == 0


def test_cancel_kills_a_real_running_subprocess(client):
    set_autonomy_mode("FULL")
    resp = client.post(
        "/api/tools/invoke",
        json={"tool": "python", "args": {"code": "import time; time.sleep(30)", "timeout_s": 60}},
    )
    invocation_id = resp.json()["id"]

    deadline = time.time() + 5
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/tools/invocations/{invocation_id}").json()["status"]
        if status == "running":
            break
        time.sleep(0.05)
    assert status == "running"

    start = time.time()
    cancel_resp = client.post(f"/api/tools/invocations/{invocation_id}/cancel")
    assert cancel_resp.status_code == 200
    elapsed = time.time() - start

    detail = client.get(f"/api/tools/invocations/{invocation_id}").json()
    assert detail["status"] == "cancelled"
    # If this took anywhere near 30s, the real OS process wasn't actually
    # killed -- it would've kept running detached after we stopped awaiting it.
    assert elapsed < 5


def test_agent_tool_call_step_lists_workspace(client):
    set_autonomy_mode("FULL")
    resp = client.post(
        "/api/agent/runs",
        json={
            "goal": "list workspace via real tool",
            "steps": [{"type": "tool_call", "params": {"tool": "filesystem_list", "args": {"path": "workspace"}}}],
        },
    )
    run_id = resp.json()["run"]["id"]
    deadline = time.time() + 5
    detail = None
    while time.time() < deadline:
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)
    assert detail["run"]["status"] == "completed"
    assert detail["steps"][0]["status"] == "done"
    assert isinstance(detail["steps"][0]["output"]["output"], list)


def test_agent_tool_call_in_safe_mode_blocks_until_approved(client):
    set_autonomy_mode("SAFE")
    resp = client.post(
        "/api/agent/runs",
        json={
            "goal": "write a file, needs confirmation in SAFE mode",
            "steps": [
                {
                    "type": "tool_call",
                    "params": {"tool": "filesystem_write", "args": {"path": "workspace/phase4_safe.txt", "content": "x"}},
                }
            ],
        },
    )
    run_id = resp.json()["run"]["id"]

    # give the agent loop a moment to create the pending tool invocation
    pending = []
    deadline = time.time() + 5
    while time.time() < deadline and not pending:
        pending = client.get("/api/tools/invocations/pending").json()["pending"]
        time.sleep(0.05)
    assert pending, "expected a pending confirmation while the agent run waits"

    client.post(f"/api/tools/invocations/{pending[0]['id']}/approve")

    deadline = time.time() + 5
    detail = None
    while time.time() < deadline:
        detail = client.get(f"/api/agent/runs/{run_id}").json()
        if detail["run"]["status"] not in ("pending", "running"):
            break
        time.sleep(0.05)
    assert detail["run"]["status"] == "completed"

    # cleanup (FULL mode so the delete doesn't itself need a confirmation
    # nobody is waiting to approve)
    set_autonomy_mode("FULL")
    cleanup = client.post("/api/tools/invoke", json={"tool": "filesystem_delete", "args": {"path": "workspace/phase4_safe.txt"}})
    cleanup_detail = _wait_until_terminal(client, cleanup.json()["id"])
    assert cleanup_detail["status"] == "done"
