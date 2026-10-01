import { useEffect, useState } from "react";
import { api, type NetworkMode } from "./api/client";
import { AutonomyModeControl } from "./components/AutonomyModeControl";
import { ConfirmationBar } from "./components/ConfirmationBar";
import { KillSwitch } from "./components/KillSwitch";
import { NetworkModeControl } from "./components/NetworkModeControl";
import { Sidebar, type NavKey } from "./components/Sidebar";
import { StatusBadge } from "./components/StatusBadge";
import { Agents } from "./pages/Agents";
import { Chat } from "./pages/Chat";
import { ComingSoon } from "./pages/ComingSoon";
import { Dashboard } from "./pages/Dashboard";
import { Models } from "./pages/Models";
import { TerminalPanel } from "./pages/Terminal";
import { Tools } from "./pages/Tools";

const PHASE_BY_PANEL: Record<
  Exclude<NavKey, "dashboard" | "models" | "chat" | "agents" | "tools" | "terminal">,
  string
> = {
  projects: "Phase 7 (Memory) / Phase 8 (UI Completion)",
  workspace: "Phase 4 (Tool Engine) — see the Tools panel for filesystem_* calls",
  security: "Phase 6 (Cyber Toolchain)",
  logs: "Phase 8 (UI Completion) — see the Tools panel for the audit log in the meantime",
  settings: "Phase 8 (UI Completion)",
};

export default function App() {
  const [active, setActive] = useState<NavKey>("dashboard");
  const [networkMode, setNetworkMode] = useState<NetworkMode | null>(null);
  const [connected, setConnected] = useState(false);
  const [chatSeed, setChatSeed] = useState<string | null>(null);

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
        <header className="h-12 border-b border-cici-border flex items-center justify-between px-4 shrink-0">
          <span className="text-xs text-cici-muted capitalize">{active}</span>
          <div className="flex items-center gap-4">
            <KillSwitch />
            <AutonomyModeControl />
            <NetworkModeControl onChange={(m) => setNetworkMode(m)} />
            <StatusBadge networkMode={networkMode} connected={connected} />
          </div>
        </header>
        <ConfirmationBar />
        <main className="flex-1 overflow-auto">
          {active === "dashboard" && <Dashboard />}
          {active === "chat" && <Chat seedText={chatSeed} onSeedConsumed={() => setChatSeed(null)} />}
          {active === "models" && <Models networkMode={networkMode} />}
          {active === "agents" && <Agents />}
          {active === "tools" && <Tools />}
          {active === "terminal" && (
            <TerminalPanel
              onSendToAI={(text) => {
                setChatSeed(text);
                setActive("chat");
              }}
            />
          )}
          {active !== "dashboard" &&
            active !== "models" &&
            active !== "chat" &&
            active !== "agents" &&
            active !== "tools" &&
            active !== "terminal" && (
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
