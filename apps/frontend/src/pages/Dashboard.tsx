import { useEffect, useState } from "react";
import { api, type HealthResponse } from "../api/client";

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-lg font-semibold mb-2">Dashboard</h1>
        <p className="text-red-400 text-sm">
          Backend unreachable: {error}. Start it with{" "}
          <code className="text-cici-text">apps/launcher/START-AI.bat</code> or{" "}
          <code className="text-cici-text">
            uvicorn app.main:app --port 8765
          </code>{" "}
          from <code className="text-cici-text">apps/backend</code>.
        </p>
      </div>
    );
  }

  if (!health) {
    return <div className="p-6 text-sm text-cici-muted">Loading hardware profile...</div>;
  }

  const hw = health.hardware;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">{health.app_name}</h1>
        <p className="text-xs text-cici-muted">
          v{health.version} · network: {health.network_mode}
        </p>
      </div>

      <section className="grid grid-cols-2 gap-4 max-w-2xl">
        <Stat label="CPU" value={hw.cpu_model} />
        <Stat
          label="Cores"
          value={`${hw.cpu_cores_physical ?? "?"} physical / ${hw.cpu_cores_logical ?? "?"} logical`}
        />
        <Stat label="RAM" value={`${hw.ram_total_gb} GB`} />
        <Stat label="OS" value={`${hw.os_name} ${hw.os_version}`} />
        <Stat
          label="GPU"
          value={
            hw.gpus.length === 0
              ? "None detected (CPU-only)"
              : hw.gpus.map((g) => `${g.name ?? g.vendor} (${g.backend})`).join(", ")
          }
        />
      </section>

      <section className="border border-cici-border rounded p-4 max-w-2xl bg-cici-panel">
        <h2 className="text-sm font-semibold mb-2">Phase status</h2>
        <p className="text-xs text-cici-muted">
          Phase 1 (Foundation) — backend, hardware detection, model registry,
          and this dashboard are live. Chat, Agent, Tools, and Security panels
          ship in Phases 2–6 — see{" "}
          <code className="text-cici-text">docs/ROADMAP.md</code>.
        </p>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-cici-border rounded p-3 bg-cici-panel">
      <div className="text-[10px] uppercase tracking-wide text-cici-muted">{label}</div>
      <div className="text-sm mt-1 break-words">{value}</div>
    </div>
  );
}
