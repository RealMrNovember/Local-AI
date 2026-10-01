const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8765";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export interface GpuInfo {
  vendor: string;
  name: string | null;
  vram_total_mb: number | null;
  backend: string | null;
}

export interface HardwareProfile {
  cpu_model: string;
  cpu_cores_physical: number | null;
  cpu_cores_logical: number | null;
  ram_total_gb: number;
  os_name: string;
  os_version: string;
  gpus: GpuInfo[];
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  network_mode: string;
  hardware: HardwareProfile;
}

export type NetworkMode = "offline" | "lan" | "internet";

export interface ModelEntry {
  name: string;
  category: "GENERAL" | "UNCENSORED" | "CODING" | "REASONING" | "EXPERIMENTAL";
  provider: string;
  type: string;
  format: string;
  context: number;
  capabilities: string[];
  min_vram_gb: number;
  path: string;
  ollama_tag: string | null;
  default: boolean;
  installed: boolean;
  install_source: "file" | "ollama" | null;
}

export interface ModelRegistryResponse {
  models: ModelEntry[];
  ollama_reachable: boolean;
}

export type AgentRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "stopped"
  | "interrupted"
  | "discarded";

export type AgentStepStatus = "pending" | "running" | "done" | "failed" | "stopped";

export interface AgentRun {
  id: string;
  goal: string;
  status: AgentRunStatus;
  created_at: string;
  updated_at: string;
  error: string | null;
  is_active?: boolean;
}

export interface AgentStep {
  id: string;
  run_id: string;
  step_index: number;
  type: string;
  params: Record<string, unknown>;
  status: AgentStepStatus;
  output: Record<string, unknown> | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AgentRunDetail {
  run: AgentRun;
  steps: AgentStep[];
}

export type AutonomyMode = "SAFE" | "AUTO" | "FULL";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface ToolDefinition {
  name: string;
  category: string;
  kind: "subprocess" | "filesystem";
  risk_level: RiskLevel;
  requires_confirmation: boolean;
  enabled: boolean;
  description: string;
  executable: string | null;
  action: string | null;
}

export type InvocationStatus =
  | "pending_confirmation"
  | "approved"
  | "denied"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

export interface ToolInvocation {
  id: string;
  tool_name: string;
  args: Record<string, unknown>;
  risk_level: RiskLevel;
  status: InvocationStatus;
  requested_by: "user" | "agent";
  run_id: string | null;
  step_id: string | null;
  exit_code: number | null;
  stdout: string | null;
  stderr: string | null;
  output: unknown;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_s: number | null;
}

export interface TerminalSessionInfo {
  id: string;
  shell: string;
  created_at: string;
  alive: boolean;
  pid: number | null;
  cols: number;
  rows: number;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} -> HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${path} -> HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} -> HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} -> HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<HealthResponse>("/api/health"),
  modelRegistry: () => get<ModelRegistryResponse>("/api/models/registry"),
  networkMode: () => get<{ mode: NetworkMode; valid_modes: NetworkMode[] }>("/api/network/mode"),
  setNetworkMode: (mode: NetworkMode) => put<{ mode: NetworkMode }>("/api/network/mode", { mode }),
  chatSocketUrl: () => `${WS_BASE}/ws/chat`,

  createAgentRun: (goal: string, steps?: { type: string; params: Record<string, unknown> }[]) =>
    post<AgentRunDetail>("/api/agent/runs", { goal, steps }),
  listAgentRuns: () => get<{ runs: AgentRun[] }>("/api/agent/runs"),
  getAgentRun: (runId: string) => get<AgentRunDetail>(`/api/agent/runs/${runId}`),
  stopAgentRun: (runId: string) => post<{ stopped: boolean }>(`/api/agent/runs/${runId}/stop`),
  resumeAgentRun: (runId: string) => post<AgentRunDetail>(`/api/agent/runs/${runId}/resume`),
  discardAgentRun: (runId: string) => post<AgentRunDetail>(`/api/agent/runs/${runId}/discard`),
  stopAllAgents: () => post<{ stopped_count: number }>("/api/agent/stop-all"),
  agentSocketUrl: (runId: string) => `${WS_BASE}/ws/agent/${runId}`,

  autonomyMode: () => get<{ mode: AutonomyMode; valid_modes: AutonomyMode[] }>("/api/autonomy/mode"),
  setAutonomyMode: (mode: AutonomyMode) => put<{ mode: AutonomyMode }>("/api/autonomy/mode", { mode }),

  toolRegistry: () => get<{ tools: ToolDefinition[] }>("/api/tools/registry"),
  invokeTool: (tool: string, args: Record<string, unknown>) =>
    post<ToolInvocation>("/api/tools/invoke", { tool, args }),
  listInvocations: (limit = 100) => get<{ invocations: ToolInvocation[] }>(`/api/tools/invocations?limit=${limit}`),
  listPendingConfirmations: () => get<{ pending: ToolInvocation[] }>("/api/tools/invocations/pending"),
  getInvocation: (id: string) => get<ToolInvocation>(`/api/tools/invocations/${id}`),
  approveInvocation: (id: string) => post<ToolInvocation>(`/api/tools/invocations/${id}/approve`),
  denyInvocation: (id: string) => post<ToolInvocation>(`/api/tools/invocations/${id}/deny`),
  cancelInvocation: (id: string) => post<{ cancelled: boolean }>(`/api/tools/invocations/${id}/cancel`),

  createTerminalSession: (shell: "powershell" | "cmd" = "powershell") =>
    post<TerminalSessionInfo>("/api/terminal/sessions", { shell }),
  listTerminalSessions: () => get<{ sessions: TerminalSessionInfo[] }>("/api/terminal/sessions"),
  closeTerminalSession: (id: string) => del<{ closed: boolean }>(`/api/terminal/sessions/${id}`),
  getTerminalHistory: (id: string) => get<{ history: string }>(`/api/terminal/sessions/${id}/history`),
  terminalSocketUrl: (id: string) => `${WS_BASE}/ws/terminal/${id}`,
  pullModel: async (ollamaTag: string, onEvent: (e: Record<string, unknown>) => void): Promise<void> => {
    const res = await fetch(`${API_BASE}/api/models/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ollama_tag: ollamaTag }),
    });
    if (!res.ok || !res.body) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `pull -> HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) continue;
        onEvent(JSON.parse(line));
      }
    }
  },
};
