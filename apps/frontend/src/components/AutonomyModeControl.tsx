import { useEffect, useState } from "react";
import { api, type AutonomyMode } from "../api/client";

const MODE_LABEL: Record<AutonomyMode, string> = {
  SAFE: "Safe",
  AUTO: "Auto",
  FULL: "Full",
};

export function AutonomyModeControl() {
  const [mode, setMode] = useState<AutonomyMode | null>(null);
  const [options, setOptions] = useState<AutonomyMode[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.autonomyMode().then((r) => {
      setMode(r.mode);
      setOptions(r.valid_modes);
    });
  }, []);

  if (!mode) return null;

  const handleChange = async (next: AutonomyMode) => {
    setBusy(true);
    try {
      const r = await api.setAutonomyMode(next);
      setMode(r.mode);
    } finally {
      setBusy(false);
    }
  };

  return (
    <select
      value={mode}
      disabled={busy}
      onChange={(e) => handleChange(e.target.value as AutonomyMode)}
      title="Autonomy mode — SAFE confirms every tool call, AUTO confirms MEDIUM+ risk, FULL only confirms CRITICAL"
      className="bg-cici-panel border border-cici-border rounded text-xs px-2 py-1 text-cici-text"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {MODE_LABEL[o]}
        </option>
      ))}
    </select>
  );
}
