import { useEffect, useRef, useState } from "react";
import { api, type ModelEntry } from "../api/client";

interface DisplayMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export function Chat({
  seedText,
  onSeedConsumed,
}: {
  seedText?: string | null;
  onSeedConsumed?: () => void;
}) {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.modelRegistry().then((r) => {
      setModels(r.models);
      const installed = r.models.find((m) => m.installed);
      setSelectedModel(installed?.name ?? r.models.find((m) => m.default)?.name ?? "");
    });
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  useEffect(() => {
    if (seedText) {
      setInput((prev) => (prev ? prev : `Here is recent terminal output:\n\n${seedText}\n\nWhat happened here?`));
      onSeedConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedText]);

  const send = () => {
    if (!input.trim() || streaming) return;
    const userMsg: DisplayMessage = { role: "user", content: input.trim() };
    const history = [...messages, userMsg];
    setMessages([...history, { role: "assistant", content: "" }]);
    setInput("");
    setStreaming(true);
    setConnectionError(null);

    const ws = new WebSocket(api.chatSocketUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          model: selectedModel || null,
          messages: history.map((m) => ({ role: m.role, content: m.content })),
        })
      );
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "chunk") {
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: next[next.length - 1].content + data.content,
          };
          return next;
        });
      } else if (data.type === "error") {
        setConnectionError(data.message);
        setStreaming(false);
        ws.close();
      } else if (data.type === "done") {
        setStreaming(false);
      }
    };

    ws.onerror = () => {
      setConnectionError("WebSocket connection failed — is the backend running?");
      setStreaming(false);
    };

    ws.onclose = () => setStreaming(false);
  };

  const installedModels = models.filter((m) => m.installed);

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-3 border-b border-cici-border flex items-center gap-3">
        <label className="text-xs text-cici-muted">Model</label>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="bg-cici-panel border border-cici-border rounded text-xs px-2 py-1"
        >
          {models.map((m) => (
            <option key={m.name} value={m.name} disabled={!m.installed}>
              {m.name}
              {!m.installed ? " (not installed)" : ""}
            </option>
          ))}
        </select>
        {installedModels.length === 0 && (
          <span className="text-xs text-cici-muted">
            No installed models — pull one from the Models panel first.
          </span>
        )}
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto p-6 space-y-4">
        {messages.length === 0 && (
          <p className="text-sm text-cici-muted">
            Send a message to start a conversation with the local model. Nothing
            leaves this machine — chat runs entirely through your local Ollama
            instance.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-cici-text" : "text-cici-text"}>
            <div className="text-[10px] uppercase tracking-wide text-cici-muted mb-1">
              {m.role}
            </div>
            <div className="text-sm whitespace-pre-wrap">{m.content || (streaming && i === messages.length - 1 ? "…" : "")}</div>
          </div>
        ))}
        {connectionError && (
          <div className="text-sm text-red-400 border border-red-900 rounded p-3 bg-red-950/30">
            {connectionError}
          </div>
        )}
      </div>

      <div className="border-t border-cici-border p-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Message..."
          disabled={streaming || !selectedModel}
          className="flex-1 bg-cici-panel border border-cici-border rounded px-3 py-2 text-sm disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim() || !selectedModel}
          className="px-4 py-2 text-sm rounded bg-cici-green/20 border border-cici-green text-cici-green disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {streaming ? "Streaming..." : "Send"}
        </button>
      </div>
    </div>
  );
}
