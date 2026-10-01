import { FitAddon } from "@xterm/addon-fit";
import { Terminal as XTerm } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { api, type TerminalSessionInfo } from "../api/client";

export function TerminalPanel({ onSendToAI }: { onSendToAI: (text: string) => void }) {
  const [sessions, setSessions] = useState<TerminalSessionInfo[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const refreshSessions = () => {
    api.listTerminalSessions().then((r) => setSessions(r.sessions));
  };

  useEffect(() => {
    refreshSessions();
    const id = setInterval(refreshSessions, 3000);
    return () => clearInterval(id);
  }, []);

  const createSession = async (shell: "powershell" | "cmd") => {
    const session = await api.createTerminalSession(shell);
    refreshSessions();
    setActiveId(session.id);
  };

  const closeSession = async (id: string) => {
    await api.closeTerminalSession(id).catch(() => {});
    if (activeId === id) setActiveId(null);
    refreshSessions();
  };

  return (
    <div className="flex h-full">
      <div className="w-64 border-r border-cici-border flex flex-col">
        <div className="p-3 border-b border-cici-border space-y-2">
          <p className="text-xs text-cici-muted">
            Real PTY sessions (pywinpty/ConPTY, Windows). This list is also the
            Phase 5 process-manager view.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => createSession("powershell")}
              className="flex-1 text-xs px-2 py-1 rounded border border-cici-green text-cici-green"
            >
              + PowerShell
            </button>
            <button
              onClick={() => createSession("cmd")}
              className="flex-1 text-xs px-2 py-1 rounded border border-cici-border text-cici-text"
            >
              + cmd
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={[
                "px-3 py-2 border-b border-cici-border/50 text-xs cursor-pointer",
                activeId === s.id ? "bg-cici-border/40" : "hover:bg-cici-border/20",
              ].join(" ")}
              onClick={() => setActiveId(s.id)}
            >
              <div className="flex items-center justify-between">
                <span>{s.shell}</span>
                <span className={s.alive ? "text-cici-green" : "text-cici-muted"}>
                  {s.alive ? "●" : "○"}
                </span>
              </div>
              <div className="text-[10px] text-cici-muted truncate">{s.id.slice(0, 12)}</div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeSession(s.id);
                }}
                className="mt-1 text-[10px] px-1.5 py-0.5 rounded border border-red-700 text-red-400"
              >
                Close
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="p-3 text-xs text-cici-muted">No sessions — start one above.</p>
          )}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        {activeId ? (
          <TerminalView key={activeId} sessionId={activeId} onSendToAI={onSendToAI} />
        ) : (
          <div className="p-6 text-sm text-cici-muted">Start or select a terminal session.</div>
        )}
      </div>
    </div>
  );
}

function TerminalView({ sessionId, onSendToAI }: { sessionId: string; onSendToAI: (text: string) => void }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const bufferRef = useRef<string>("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new XTerm({
      convertEol: true,
      fontSize: 13,
      theme: { background: "#0a0e0d", foreground: "#d4dbd8" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();

    const ws = new WebSocket(api.terminalSocketUrl(sessionId));
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "backlog" || msg.type === "output") {
        term.write(msg.data);
        bufferRef.current += msg.data;
      } else if (msg.type === "closed") {
        term.write("\r\n\x1b[31m[session closed]\x1b[0m\r\n");
      }
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
    };
  }, [sessionId]);

  // Strip ANSI escape sequences before handing text to the chat model —
  // it doesn't need cursor-positioning codes to understand command output.
  const stripAnsi = (s: string) => s.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, "");

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-1.5 border-b border-cici-border flex items-center gap-2">
        <span className="text-[10px] text-cici-muted">Session {sessionId.slice(0, 12)}</span>
        <button
          onClick={() => onSendToAI(stripAnsi(bufferRef.current).slice(-8000))}
          className="ml-auto text-[10px] px-2 py-0.5 rounded border border-cici-border text-cici-muted hover:text-cici-text"
          title="Send this terminal's recent output to the Chat panel as context"
        >
          Send output to AI
        </button>
      </div>
      <div ref={containerRef} className="flex-1 p-2" />
    </div>
  );
}
