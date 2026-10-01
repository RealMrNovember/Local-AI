import { useEffect, useState } from "react";
import { api, type NetworkMode } from "./api/client";
import { NetworkModeControl } from "./components/NetworkModeControl";
import { Sidebar, type NavKey } from "./components/Sidebar";
import { StatusBadge } from "./components/StatusBadge";
import { Chat } from "./pages/Chat";
import { ComingSoon } from "./pages/ComingSoon";
import { Dashboard } from "./pages/Dashboard";
import { Models } from "./pages/Models";

const PHASE_BY_PANEL: Record<
  Exclude<NavKey, "dashboard" | "models" | "chat">,
  string
> = {
  agents: "Phase 3 (Agent Core)",
  tools: "Phase 4 (Tool Engine)",
  projects: "Phase 7 (Memory) / Phase 8 (UI Completion)",
  workspace: "Phase 4 (Tool Engine)",
  security: "Phase 6 (Cyber Toolchain)",
  terminal: "Phase 5 (Terminal)",
  logs: "Phase 4 (Audit Log) / Phase 8 (UI Completion)",
  settings: "Phase 8 (UI Completion)",
};

export default function App() {
  const [active, setActive] = useState<NavKey>("dashboard");
  const [networkMode, setNetworkMode] = useState<NetworkMode | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setNetworkMode(h.network_mode as NetworkMode);
        setConnected(true);
      })
      .catch(() => setConnected(false));
  }, []);

  return (
    <div className="h-screen w-screen flex bg-cici-bg text-cici-text">
      <Sidebar active={active} onSelect={setActive} />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 border-b border-cici-border flex items-center justify-between px-4">
          <span className="text-xs text-cici-muted capitalize">{active}</span>
          <div className="flex items-center gap-4">
            <NetworkModeControl onChange={(m) => setNetworkMode(m)} />
            <StatusBadge networkMode={networkMode} connected={connected} />
          </div>
        </header>
        <main className="flex-1 overflow-auto">
          {active === "dashboard" && <Dashboard />}
          {active === "chat" && <Chat />}
          {active === "models" && <Models networkMode={networkMode} />}
          {active !== "dashboard" && active !== "models" && active !== "chat" && (
            <ComingSoon title={capitalize(active)} phase={PHASE_BY_PANEL[active]} />
          )}
        </main>
      </div>
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
