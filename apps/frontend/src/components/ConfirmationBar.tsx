import { useEffect, useState } from "react";
import { api, type ToolInvocation } from "../api/client";

const RISK_COLOR: Record<string, string> = {
  LOW: "text-cici-green",
  MEDIUM: "text-yellow-400",
  HIGH: "text-orange-400",
  CRITICAL: "text-red-400",
};

/** Always-polling confirmation surface (product brief's "SAFE mode asks
 * before every tool call" requirement) — a pending invocation otherwise
 * sits invisible until someone opens the Tools panel, which defeats the
 * point of a confirmation gate. */
export function ConfirmationBar() {
  const [pending, setPending] = useState<ToolInvocation[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = () => {
    api
      .listPendingConfirmations()
      .then((r) => setPending(r.pending))
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 1500);
    return () => clearInterval(id);
  }, []);

  if (pending.length === 0) return null;

  const act = async (id: string, fn: (id: string) => Promise<unknown>) => {
    setBusyId(id);
    try {
      await fn(id);
      refresh();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="border-b border-yellow-800 bg-yellow-950/30">
      {pending.map((inv) => (
        <div key={inv.id} className="px-4 py-2 flex items-center gap-3 text-xs">
          <span className={`font-semibold ${RISK_COLOR[inv.risk_level] ?? ""}`}>{inv.risk_level}</span>
          <span>
            {inv.requested_by === "agent" ? "Agent wants to run" : "Requested"}:{" "}
            <code className="text-cici-text">{inv.tool_name}</code>{" "}
            <span className="text-cici-muted">{JSON.stringify(inv.args)}</span>
          </span>
          <div className="ml-auto flex gap-2">
            <button
              disabled={busyId === inv.id}
              onClick={() => act(inv.id, api.approveInvocation)}
              className="px-2 py-0.5 rounded border border-cici-green text-cici-green"
            >
              Allow
            </button>
            <button
              disabled={busyId === inv.id}
              onClick={() => act(inv.id, api.denyInvocation)}
              className="px-2 py-0.5 rounded border border-red-600 text-red-400"
            >
              Deny
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
