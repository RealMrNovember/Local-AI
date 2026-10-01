export function StatusBadge({
  networkMode,
  connected,
}: {
  networkMode: string | null;
  connected: boolean;
}) {
  const label = !connected
    ? "BACKEND UNREACHABLE"
    : networkMode === "offline"
      ? "LOCAL / OFFLINE"
      : networkMode?.toUpperCase() ?? "UNKNOWN";

  const dotColor = !connected
    ? "bg-red-500"
    : networkMode === "offline"
      ? "bg-cici-green"
      : "bg-yellow-500";

  return (
    <div className="flex items-center gap-2 text-xs text-cici-muted">
      <span className={`inline-block h-2 w-2 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </div>
  );
}
