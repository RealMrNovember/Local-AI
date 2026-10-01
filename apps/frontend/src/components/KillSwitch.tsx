import { useEffect, useState } from "react";
import { api } from "../api/client";

/** Always-visible global kill switch (product brief Section 15/45). Polls
 * active run count rather than opening a dedicated socket just for a
 * badge — cheap, and good enough at this scale (Phase 3). */
export function KillSwitch() {
  const [activeCount, setActiveCount] = useState(0);
  const [busy, setBusy] = useState(false);

  const refresh = () => {
    api
      .listAgentRuns()
      .then((r) => setActiveCount(r.runs.filter((run) => run.is_active).length))
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  const handleStopAll = async () => {
    setBusy(true);
    try {
      await api.stopAllAgents();
      refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={handleStopAll}
      disabled={activeCount === 0 || busy}
      title={activeCount === 0 ? "No active agent runs" : `Stop ${activeCount} active run(s)`}
      className={[
        "text-xs px-3 py-1 rounded border flex items-center gap-1.5",
        activeCount > 0
          ? "border-red-600 text-red-400 hover:bg-red-950/40"
          : "border-cici-border text-cici-muted/50 cursor-not-allowed",
      ].join(" ")}
    >
      🛑 STOP AGENT{activeCount > 0 ? ` (${activeCount})` : ""}
    </button>
  );
}
