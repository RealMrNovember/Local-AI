import { useEffect, useState } from "react";
import { api, type ModelEntry, type NetworkMode } from "../api/client";

const CATEGORY_LABEL: Record<ModelEntry["category"], string> = {
  CODING: "Coding / Agent",
  UNCENSORED: "Uncensored / General",
  GENERAL: "General",
  REASONING: "Reasoning",
  EXPERIMENTAL: "Community Models",
};

export function Models({ networkMode }: { networkMode: NetworkMode | null }) {
  const [models, setModels] = useState<ModelEntry[] | null>(null);
  const [ollamaReachable, setOllamaReachable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [experimentalOpen, setExperimentalOpen] = useState(false);
  const [pulling, setPulling] = useState<string | null>(null);
  const [pullProgress, setPullProgress] = useState<string>("");
  const [pullError, setPullError] = useState<string | null>(null);

  const reload = () => {
    api
      .modelRegistry()
      .then((res) => {
        setModels(res.models);
        setOllamaReachable(res.ollama_reachable);
        setSelected((prev) => prev ?? res.models.find((m) => m.default)?.name ?? null);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    reload();
  }, []);

  if (error) {
    return <div className="p-6 text-sm text-red-400">Backend unreachable: {error}</div>;
  }
  if (!models) {
    return <div className="p-6 text-sm text-cici-muted">Loading model registry...</div>;
  }

  const primary = models.filter((m) => m.category !== "EXPERIMENTAL");
  const experimental = models.filter((m) => m.category === "EXPERIMENTAL");

  const handlePull = async (m: ModelEntry) => {
    if (!m.ollama_tag) return;
    setPulling(m.name);
    setPullError(null);
    setPullProgress("starting...");
    try {
      await api.pullModel(m.ollama_tag, (event) => {
        if (event.error) {
          setPullError(String(event.error));
          return;
        }
        const status = event.status ?? "";
        const pct =
          typeof event.completed === "number" && typeof event.total === "number" && event.total > 0
            ? ` ${Math.round((event.completed / event.total) * 100)}%`
            : "";
        setPullProgress(`${status}${pct}`);
      });
      reload();
    } catch (e) {
      setPullError(String(e));
    } finally {
      setPulling(null);
    }
  };

  return (
    <div className="p-6 max-w-xl space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Models</h1>
        <p className="text-xs text-cici-muted">
          Registry defined in <code className="text-cici-text">config/models.yaml</code>.
          Ollama: {ollamaReachable ? "reachable" : "not reachable"} · Network mode:{" "}
          {networkMode ?? "?"}
          {networkMode === "offline" && " (switch to LAN/Internet above to download models)"}
        </p>
        {pullError && <p className="text-xs text-red-400 mt-1">{pullError}</p>}
      </div>

      <div className="border border-cici-border rounded bg-cici-panel divide-y divide-cici-border">
        <div className="px-4 py-2 text-[10px] uppercase tracking-wide text-cici-muted">
          Model
        </div>
        {primary.map((m) => (
          <ModelRow
            key={m.name}
            model={m}
            isSelected={selected === m.name}
            onSelect={() => setSelected(m.name)}
            onPull={() => handlePull(m)}
            pulling={pulling === m.name}
            pullProgress={pulling === m.name ? pullProgress : ""}
            canPull={networkMode !== "offline" && !!m.ollama_tag}
          />
        ))}

        <button
          className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-cici-border/30"
          onClick={() => setExperimentalOpen((v) => !v)}
        >
          <span className="mt-1 h-2 w-2 rounded-full border border-cici-muted shrink-0" />
          <div className="flex-1">
            <div className="text-sm">Experimental</div>
            <div className="text-xs text-cici-muted">
              {CATEGORY_LABEL.EXPERIMENTAL} ({experimental.length})
            </div>
          </div>
          <span className="text-xs text-cici-muted">{experimentalOpen ? "▲" : "▼"}</span>
        </button>
        {experimentalOpen &&
          experimental.map((m) => (
            <ModelRow
              key={m.name}
              model={m}
              isSelected={selected === m.name}
              onSelect={() => setSelected(m.name)}
              onPull={() => handlePull(m)}
              pulling={pulling === m.name}
              pullProgress={pulling === m.name ? pullProgress : ""}
              canPull={networkMode !== "offline" && !!m.ollama_tag}
              indent
            />
          ))}
      </div>
    </div>
  );
}

function ModelRow({
  model,
  isSelected,
  onSelect,
  onPull,
  pulling,
  pullProgress,
  canPull,
  indent = false,
}: {
  model: ModelEntry;
  isSelected: boolean;
  onSelect: () => void;
  onPull: () => void;
  pulling: boolean;
  pullProgress: string;
  canPull: boolean;
  indent?: boolean;
}) {
  return (
    <div
      className={[
        "w-full text-left px-4 py-3 flex items-start gap-3",
        indent ? "pl-8 bg-cici-bg/30" : "",
      ].join(" ")}
    >
      <button
        onClick={onSelect}
        disabled={!model.installed}
        className={[
          "mt-1 h-2 w-2 rounded-full shrink-0",
          isSelected ? "bg-cici-green" : "border border-cici-muted",
          !model.installed ? "cursor-not-allowed" : "",
        ].join(" ")}
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm flex items-center gap-2">
          {model.name}
          {!model.installed && (
            <span className="text-[10px] uppercase tracking-wide text-cici-muted/70 border border-cici-border rounded px-1">
              not installed
            </span>
          )}
          {model.installed && model.install_source && (
            <span className="text-[10px] uppercase tracking-wide text-cici-green/70 border border-cici-green/40 rounded px-1">
              {model.install_source}
            </span>
          )}
        </div>
        <div className="text-xs text-cici-muted">{CATEGORY_LABEL[model.category]}</div>
        {pulling && <div className="text-[10px] text-cici-green mt-1">{pullProgress}</div>}
        {!model.ollama_tag && !model.installed && (
          <div className="text-[10px] text-cici-muted/70 mt-1">
            No Ollama tag configured — place a GGUF at {model.path} manually.
          </div>
        )}
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        <div className="text-[10px] text-cici-muted text-right">
          {model.context.toLocaleString()} ctx
          <br />
          {model.min_vram_gb} GB VRAM
        </div>
        {!model.installed && model.ollama_tag && (
          <button
            onClick={onPull}
            disabled={!canPull || pulling}
            title={!canPull ? "Switch network mode to LAN/Internet first" : undefined}
            className="text-[10px] px-2 py-0.5 rounded border border-cici-green text-cici-green disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pulling ? "Pulling..." : "Pull"}
          </button>
        )}
      </div>
    </div>
  );
}
