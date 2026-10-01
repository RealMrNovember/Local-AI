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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${path} -> HTTP ${res.status}`);
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
