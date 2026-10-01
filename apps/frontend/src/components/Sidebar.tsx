export type NavKey =
  | "dashboard"
  | "chat"
  | "models"
  | "agents"
  | "tools"
  | "projects"
  | "workspace"
  | "security"
  | "terminal"
  | "logs"
  | "settings";

interface NavItem {
  key: NavKey;
  label: string;
  implemented: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { key: "dashboard", label: "Dashboard", implemented: true },
  { key: "chat", label: "Chat", implemented: true },
  { key: "models", label: "Models", implemented: true },
  { key: "agents", label: "Agents", implemented: true },
  { key: "tools", label: "Tools", implemented: false },
  { key: "projects", label: "Projects", implemented: false },
  { key: "workspace", label: "Workspace", implemented: false },
  { key: "security", label: "Security", implemented: false },
  { key: "terminal", label: "Terminal", implemented: false },
  { key: "logs", label: "Logs", implemented: false },
  { key: "settings", label: "Settings", implemented: false },
];

export function Sidebar({
  active,
  onSelect,
}: {
  active: NavKey;
  onSelect: (key: NavKey) => void;
}) {
  return (
    <nav className="w-56 shrink-0 border-r border-cici-border bg-cici-panel flex flex-col">
      <div className="px-4 py-4 border-b border-cici-border">
        <div className="text-sm font-semibold tracking-wide text-cici-green">
          CICIBYTE-AI
        </div>
      </div>
      <ul className="flex-1 py-2">
        {NAV_ITEMS.map((item) => (
          <li key={item.key}>
            <button
              onClick={() => onSelect(item.key)}
              className={[
                "w-full text-left px-4 py-2 text-sm flex items-center justify-between",
                active === item.key
                  ? "bg-cici-border text-cici-text"
                  : "text-cici-muted hover:text-cici-text hover:bg-cici-border/40",
              ].join(" ")}
            >
              <span>{item.label}</span>
              {!item.implemented && (
                <span className="text-[10px] uppercase tracking-wide text-cici-muted/70">
                  soon
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
