import { useEffect, useState } from "react";
import { api, type ToolDefinition, type ToolInvocation } from "../api/client";

const RISK_COLOR: Record<string, string> = {
  LOW: "text-cici-green",
  MEDIUM: "text-yellow-400",
  HIGH: "text-orange-400",
  CRITICAL: "text-red-400",
};

const STATUS_COLOR: Record<string, string> = {
  pending_confirmation: "text-yellow-400",
  approved: "text-cici-muted",
  running: "text-yellow-400",
  done: "text-cici-green",
  failed: "text-red-400",
  denied: "text-red-400",
  cancelled: "text-orange-400",
};

export function Tools() {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [invocations, setInvocations] = useState<ToolInvocation[]>([]);
  const [selected, setSelected] = useState<string>("filesystem_list");
  const [argsText, setArgsText] = useState('{"path": "workspace"}');
  const [error, setError] = useState<string | null>(null);

  const refreshInvocations = () => {
    api.listInvocations(50).then((r) => setInvocations(r.invocations));
  };

  useEffect(() => {
    api.toolRegistry().then((r) => setTools(r.tools));
    refreshInvocations();
    const id = setInterval(refreshInvocations, 2000);
    return () => clearInterval(id);
  }, []);

  const runTool = async () => {
    setError(null);
    let args: Record<string, unknown>;
    try {
      args = JSON.parse(argsText);
    } catch {
      setError("Args must be valid JSON");
      return;
    }
    try {
      await api.invokeTool(selected, args);
      refreshInvocations();
    } catch (e) {
      setError(String(e));
    }
  };

  const selectedDef = tools.find((t) => t.name === selected);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Tools</h1>
        <p className="text-xs text-cici-muted">
          Tool Registry from <code className="text-cici-text">config/tools.yaml</code>. Every
          invocation below runs through the real Permission Engine for the current Autonomy Mode —
          this is also the audit log (product brief Section 31/32).
        </p>
      </div>

      <div className="border border-cici-border rounded bg-cici-panel divide-y divide-cici-border">
        <div className="px-4 py-2 text-[10px] uppercase tracking-wide text-cici-muted">Registry</div>
        {tools.map((t) => (
          <div key={t.name} className="px-4 py-2 flex items-center gap-3 text-sm">
            <code className="w-40 shrink-0">{t.name}</code>
            <span className={`text-xs ${RISK_COLOR[t.risk_level] ?? ""}`}>{t.risk_level}</span>
            <span className="text-xs text-cici-muted">{t.category}</span>
            <span className="text-xs text-cici-muted flex-1 truncate">{t.description}</span>
            {t.requires_confirmation && (
              <span className="text-[10px] border border-cici-border rounded px-1 text-cici-muted">
                always confirms
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="border border-cici-border rounded bg-cici-panel p-4 space-y-2 max-w-xl">
        <h2 className="text-sm font-semibold">Try a tool</h2>
        <div className="flex gap-2">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="bg-cici-bg border border-cici-border rounded text-xs px-2 py-1"
          >
            {tools.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
          <button onClick={runTool} className="text-xs px-3 py-1 rounded border border-cici-green text-cici-green">
            Invoke
          </button>
        </div>
        {selectedDef?.kind === "subprocess" && selectedDef.name === "python" && (
          <p className="text-[10px] text-cici-muted">args: {`{"code": "print(1)"}`} or {`{"script_path": "..."}`}</p>
        )}
        {selectedDef?.kind === "subprocess" && selectedDef.name === "git" && (
          <p className="text-[10px] text-cici-muted">args: {`{"args": ["status"]}`}</p>
        )}
        {selectedDef?.kind === "filesystem" && (
          <p className="text-[10px] text-cici-muted">
            args: {`{"path": "workspace/..."}`}
            {selectedDef.action === "write" && ' + {"content": "..."}'}
          </p>
        )}
        <textarea
          value={argsText}
          onChange={(e) => setArgsText(e.target.value)}
          rows={2}
          className="w-full bg-cici-bg border border-cici-border rounded text-xs px-2 py-1 font-mono"
        />
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>

      <div>
        <h2 className="text-sm font-semibold mb-2">Recent invocations (audit log)</h2>
        <div className="border border-cici-border rounded bg-cici-panel divide-y divide-cici-border max-h-96 overflow-auto">
          {invocations.map((inv) => (
            <InvocationRow key={inv.id} invocation={inv} onChanged={refreshInvocations} />
          ))}
          {invocations.length === 0 && <p className="p-4 text-xs text-cici-muted">No invocations yet.</p>}
        </div>
      </div>
    </div>
  );
}

function InvocationRow({ invocation, onChanged }: { invocation: ToolInvocation; onChanged: () => void }) {
  const [open, setOpen] = useState(false);

  const cancel = async () => {
    await api.cancelInvocation(invocation.id);
    onChanged();
  };

  return (
    <div>
      <button onClick={() => setOpen((v) => !v)} className="w-full text-left px-4 py-2 flex items-center gap-3 text-sm">
        <span className={`text-xs ${STATUS_COLOR[invocation.status] ?? ""}`}>{invocation.status}</span>
        <code className="text-xs">{invocation.tool_name}</code>
        <span className="text-[10px] text-cici-muted">{invocation.requested_by}</span>
        <span className="ml-auto text-[10px] text-cici-muted">{new Date(invocation.created_at).toLocaleTimeString()}</span>
        {(invocation.status === "running" || invocation.status === "pending_confirmation") && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              cancel();
            }}
            className="text-[10px] px-2 py-0.5 rounded border border-red-600 text-red-400"
          >
            Cancel
          </button>
        )}
      </button>
      {open && (
        <div className="px-4 pb-3 text-xs text-cici-muted space-y-1">
          <div>args: {JSON.stringify(invocation.args)}</div>
          {invocation.exit_code !== null && <div>exit_code: {invocation.exit_code}</div>}
          {invocation.stdout && <pre className="whitespace-pre-wrap text-cici-text">{invocation.stdout}</pre>}
          {invocation.stderr && <pre className="whitespace-pre-wrap text-red-400">{invocation.stderr}</pre>}
          {invocation.output != null && <div>output: {JSON.stringify(invocation.output)}</div>}
          {invocation.error && <div className="text-red-400">error: {invocation.error}</div>}
        </div>
      )}
    </div>
  );
}
