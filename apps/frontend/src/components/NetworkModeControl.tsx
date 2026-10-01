import { useEffect, useState } from "react";
import { api, type NetworkMode } from "../api/client";

const MODE_LABEL: Record<NetworkMode, string> = {
  offline: "Offline",
  lan: "LAN",
  internet: "Internet",
};

export function NetworkModeControl({ onChange }: { onChange?: (mode: NetworkMode) => void }) {
  const [mode, setMode] = useState<NetworkMode | null>(null);
  const [options, setOptions] = useState<NetworkMode[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .networkMode()
      .then((r) => {
        setMode(r.mode);
        setOptions(r.valid_modes);
      })
      .catch(() => {});
  }, []);

  if (!mode) return null;

  const handleChange = async (next: NetworkMode) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.setNetworkMode(next);
      setMode(r.mode);
      onChange?.(r.mode);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {error && <span className="text-[10px] text-red-400">{error}</span>}
      <select
        value={mode}
        disabled={busy}
        onChange={(e) => handleChange(e.target.value as NetworkMode)}
        className="bg-cici-panel border border-cici-border rounded text-xs px-2 py-1 text-cici-text"
        title="Network mode — switch to LAN/Internet only when you actually need to download a model"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {MODE_LABEL[o]}
          </option>
        ))}
      </select>
    </div>
  );
}
