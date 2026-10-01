export function ComingSoon({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold mb-2">{title}</h1>
      <p className="text-sm text-cici-muted">
        Not implemented yet — scheduled for {phase}. See{" "}
        <code className="text-cici-text">docs/ROADMAP.md</code> for the exit
        criteria for this panel.
      </p>
    </div>
  );
}
