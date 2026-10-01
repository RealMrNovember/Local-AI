import { useEffect, useRef, useState } from "react";
import { api, type AgentRun, type AgentRunDetail, type AgentStep } from "../api/client";

const STATUS_COLOR: Record<string, string> = {
  pending: "text-cici-muted",
  running: "text-yellow-400",
  completed: "text-cici-green",
  done: "text-cici-green",
  failed: "text-red-400",
  stopped: "text-orange-400",
  interrupted: "text-orange-400",
  discarded: "text-cici-muted",
};

export function Agents() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [goal, setGoal] = useState("");

  const refreshList = () => {
    api.listAgentRuns().then((r) => setRuns(r.runs));
  };

  useEffect(() => {
    refreshList();
    const id = setInterval(refreshList, 2000);
    return () => clearInterval(id);
  }, []);

  const runQuickTest = async (kind: "echo" | "sleep") => {
    const detail = await api.createAgentRun(
      kind === "echo" ? `echo test: ${goal || "hello from CiciByte"}` : "sleep test (10s, try STOP)",
      kind === "echo"
        ? [{ type: "stub_echo", params: { text: goal || "hello from CiciByte" } }]
        : [{ type: "stub_sleep", params: { seconds: 10 } }]
    );
    setSelectedId(detail.run.id);
    refreshList();
  };

  return (
    <div className="flex h-full">
      <div className="w-72 border-r border-cici-border flex flex-col">
        <div className="p-4 border-b border-cici-border space-y-2">
          <p className="text-xs text-cici-muted">
            Phase 3 scope: only <code className="text-cici-text">stub_echo</code> /{" "}
            <code className="text-cici-text">stub_sleep</code> step types exist — this proves the
            Plan→Execute→Observe→Validate loop, persistence, and kill switch. Real tools arrive in
            Phase 4.
          </p>
          <input
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Text for echo test..."
            className="w-full bg-cici-panel border border-cici-border rounded px-2 py-1 text-xs"
          />
          <div className="flex gap-2">
            <button
              onClick={() => runQuickTest("echo")}
              className="flex-1 text-xs px-2 py-1 rounded border border-cici-green text-cici-green"
            >
              Run echo
            </button>
            <button
              onClick={() => runQuickTest("sleep")}
              className="flex-1 text-xs px-2 py-1 rounded border border-yellow-600 text-yellow-400"
            >
              Run sleep (10s)
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto">
          {runs.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedId(r.id)}
              className={[
                "w-full text-left px-4 py-2 border-b border-cici-border/50 text-xs",
                selectedId === r.id ? "bg-cici-border/40" : "hover:bg-cici-border/20",
              ].join(" ")}
            >
              <div className="flex items-center justify-between">
                <span className={STATUS_COLOR[r.status] ?? "text-cici-text"}>{r.status}</span>
                {r.is_active && <span className="text-cici-green">●</span>}
              </div>
              <div className="text-cici-muted truncate">{r.goal}</div>
            </button>
          ))}
          {runs.length === 0 && (
            <p className="p-4 text-xs text-cici-muted">No runs yet — try one of the buttons above.</p>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {selectedId ? (
          <RunDetail runId={selectedId} onChanged={refreshList} />
        ) : (
          <div className="p-6 text-sm text-cici-muted">Select or start a run to see its Live Agent View.</div>
        )}
      </div>
    </div>
  );
}

function RunDetail({ runId, onChanged }: { runId: string; onChanged: () => void }) {
  const [detail, setDetail] = useState<AgentRunDetail | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    setDetail(null);
    api.getAgentRun(runId).then(setDetail);

    const ws = new WebSocket(api.agentSocketUrl(runId));
    wsRef.current = ws;
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "snapshot") {
        setDetail({ run: data.run, steps: data.steps });
      } else if (data.type === "run_update") {
        setDetail((prev) => (prev ? { ...prev, run: data.run } : prev));
        onChanged();
      } else if (data.type === "step_update") {
        setDetail((prev) => {
          if (!prev) return prev;
          const steps = prev.steps.map((s: AgentStep) => (s.id === data.step.id ? data.step : s));
          return { ...prev, steps };
        });
      }
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  if (!detail) return <div className="p-6 text-sm text-cici-muted">Loading...</div>;

  const { run, steps } = detail;
  const isActive = run.status === "pending" || run.status === "running";

  const act = async (fn: () => Promise<unknown>) => {
    await fn();
    const fresh = await api.getAgentRun(runId);
    setDetail(fresh);
    onChanged();
  };

  return (
    <div className="p-6 space-y-4">
      <div>
        <h2 className="text-sm font-semibold">{run.goal}</h2>
        <p className={`text-xs ${STATUS_COLOR[run.status] ?? ""}`}>
          {run.status}
          {run.error ? ` — ${run.error}` : ""}
        </p>
      </div>

      <div className="flex gap-2">
        {isActive && (
          <button
            onClick={() => act(() => api.stopAgentRun(runId))}
            className="text-xs px-3 py-1 rounded border border-red-600 text-red-400"
          >
            🛑 Stop
          </button>
        )}
        {(run.status === "interrupted" || run.status === "stopped" || run.status === "failed") && (
          <button
            onClick={() => act(() => api.resumeAgentRun(runId))}
            className="text-xs px-3 py-1 rounded border border-cici-green text-cici-green"
          >
            Resume
          </button>
        )}
        {run.status !== "discarded" && !isActive && (
          <button
            onClick={() => act(() => api.discardAgentRun(runId))}
            className="text-xs px-3 py-1 rounded border border-cici-border text-cici-muted"
          >
            Discard
          </button>
        )}
      </div>

      <div className="space-y-2">
        {steps.map((step) => (
          <StepRow key={step.id} step={step} />
        ))}
      </div>
    </div>
  );
}

function StepRow({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(false);
  const icon = step.status === "done" ? "✓" : step.status === "failed" ? "✗" : step.status === "running" ? "●" : "○";

  return (
    <div className="border border-cici-border rounded bg-cici-panel">
      <button onClick={() => setOpen((v) => !v)} className="w-full text-left px-3 py-2 flex items-center gap-2 text-sm">
        <span className={STATUS_COLOR[step.status] ?? ""}>{icon}</span>
        <span>
          {step.step_index + 1}. {step.type}
        </span>
        <span className={`ml-auto text-xs ${STATUS_COLOR[step.status] ?? ""}`}>{step.status}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 text-xs text-cici-muted space-y-1">
          <div>params: {JSON.stringify(step.params)}</div>
          {step.output && <div>output: {JSON.stringify(step.output)}</div>}
          {step.error && <div className="text-red-400">error: {step.error}</div>}
        </div>
      )}
    </div>
  );
}
