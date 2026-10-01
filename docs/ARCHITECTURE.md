# CiciByte AI — Architecture

Status: **Draft v0.1 — Phase 0 (Foundation planning)**
Last updated: 2026-10-01

This document describes the target architecture for CiciByte AI, a portable,
local-first AI + development + cybersecurity workstation. It is a living
document: update it whenever a phase changes a load-bearing decision (see
`ROADMAP.md` and `IMPLEMENTATION_STATUS.md`).

## 1. Guiding constraints

These constraints shape every decision below:

1. **Local-first, cloud-optional.** Core chat/agent/tool loop must work with
   zero internet access. Cloud model providers (Anthropic, OpenAI, Google) are
   pluggable, never required.
2. **Loose coupling.** Model, Agent Engine, Tool Registry, and UI are separate
   interfaces. Swapping the model backend must not require touching agent or
   tool code, and vice versa.
3. **No simulated functionality.** If a feature isn't implemented, the UI must
   not pretend it is. No hardcoded fake responses, no placeholder buttons that
   look wired up but aren't.
4. **Authorized use only for security tooling.** Every offensive/security tool
   adapter (nmap, sqlmap, ffuf, nuclei, hashcat, ...) is gated by a target
   scope allowlist and a confirmation/risk engine. The system is built for
   authorized penetration testing, CTFs, and defensive security work — it does
   not attempt to hide activity from the operator or bypass the scope/consent
   checks described in Section 9.
5. **Incremental, always-runnable.** Every phase in the roadmap ends with a
   working, testable application — never a multi-week integration gap.

## 2. High-level component view

```text
┌─────────────────────────────────────────────────────────────────┐
│                           WEB UI (React)                        │
│  Dashboard · Chat · Agent Monitor · Tools · Terminal · Projects  │
│  Security · Models · Logs · Settings                             │
└───────────────┬───────────────────────────────────────┬─────────┘
                 │ HTTP (REST)                 WebSocket/SSE (stream)
┌────────────────▼───────────────────────────────────────▼─────────┐
│                      BACKEND (FastAPI, Python)                    │
│                                                                    │
│  ┌───────────────┐   ┌────────────────┐   ┌────────────────────┐ │
│  │ Model Provider│   │  Agent Engine   │   │   Tool Registry    │ │
│  │   Abstraction │◄──┤ Plan/Execute/   │──►│  + Execution Engine│ │
│  │ (Ollama/llama.│   │ Observe/Validate│   │  + Permission Engine│ │
│  │  cpp/Cloud)   │   │ /Retry loop     │   │                    │ │
│  └───────────────┘   └────────────────┘   └──────────┬─────────┘ │
│                                                        │           │
│  ┌───────────────┐   ┌────────────────┐   ┌───────────▼────────┐ │
│  │ Memory Engine │   │ Project Manager │   │  Local OS Processes │ │
│  │ (session/proj/│   │ (per-project    │   │  (subprocess, venv, │ │
│  │  global, SQLite)│ │  config/memory) │   │   containers)       │ │
│  └───────────────┘   └────────────────┘   └────────────────────┘ │
│                                                                    │
│  Cross-cutting: Config · Structured Logging · Audit Log ·         │
│  Secret Store · Hardware Profiler · Kill Switch                   │
└─────────────────────────────────────────────────────────────────┘
```

Everything under "BACKEND" lives in `core/` as independent Python packages
with explicit interfaces (ABCs/Protocols), so each box can be tested and
replaced in isolation. `apps/backend` only wires them together and exposes
HTTP/WebSocket.

## 3. Repository layout (target)

```text
cicibyte-ai/
├── apps/
│   ├── backend/        # FastAPI app: routers, DI wiring, startup
│   ├── frontend/        # React + TS + Tailwind SPA
│   ├── cli/              # `cici` command-line client (talks to backend API)
│   └── launcher/        # START-AI.exe / START-AI.sh portable launcher
│
├── core/
│   ├── models/           # Model provider abstraction + implementations
│   ├── agent/            # Planner, Executor, Observer, Validator, loop
│   ├── tools/             # Tool registry, schemas, built-in tool adapters
│   ├── execution/        # Process execution engine (subprocess/sandbox)
│   ├── permissions/      # Risk levels, confirmation engine, scope engine
│   ├── memory/            # Session/project/global memory stores
│   ├── security/          # Secret store, audit log, policy engine
│   └── orchestration/    # Hardware profiling, model routing
│
├── runtime/               # Vendored/managed runtimes (llama.cpp, Ollama refs)
├── plugins/                # Optional plugin packages (cyber/dev/forensic/...)
├── cyber/                   # Security tool adapter configs (not the binaries)
├── models/                  # GGUF files / model registry data (gitignored)
├── workspace/                # Default sandbox for agent file operations
├── projects/                  # Per-project state (context/memory/reports)
├── scripts/                    # Dev/setup scripts
├── installer/                   # USB/portable image build scripts
├── boot/                          # Linux boot environment build (Phase 9+)
├── config/                         # Default config files, schemas
├── logs/                            # Runtime + audit logs (gitignored)
├── tests/                            # Unit/integration tests mirroring core/
└── docs/
    ├── ARCHITECTURE.md (this file)
    ├── ROADMAP.md
    ├── IMPLEMENTATION_STATUS.md
    ├── SECURITY.md
    ├── TOOLS.md
    ├── MODELS.md
    ├── BOOT.md
    ├── DEPLOYMENT.md
    └── CHANGELOG.md
```

## 4. Backend technology choices

| Concern            | Choice                              | Why |
|--------------------|--------------------------------------|-----|
| API framework      | **FastAPI** (Python 3.12)            | async-native, typed, OpenAPI for free, pairs well with WebSocket streaming |
| Realtime transport | **WebSocket** (fallback SSE)         | bidirectional needed for kill-switch/cancel signals, not just one-way streaming |
| Local model runtime| **Ollama** first, **llama.cpp** (direct GGUF) as a lower-level/advanced backend | Ollama gives model mgmt + GPU detection out of the box; llama.cpp direct gives control for the portable/no-install boot scenario |
| Database           | **SQLite** (via SQLAlchemy) now, **PostgreSQL** optional later | zero-install, file-based, fits USB-portable requirement; swappable via the same ORM layer |
| Process execution  | `asyncio.create_subprocess_exec` + psutil | async-friendly, cross-platform, gives resource usage + PID tree for kill switch |
| Sandboxing         | Docker (if present) → OS-native fallback | Docker/Podman where available; graceful degrade to plain subprocess with filesystem scoping elsewhere (bubblewrap/Firejail are Linux-only, used in Phase 9's Linux boot target) |
| Secrets            | OS keychain (via `keyring` lib) with local encrypted-file fallback | avoids plaintext secrets in config without requiring a master password UX up front |

## 5. Model layer

### 5.1 Provider abstraction

```python
class ModelProvider(Protocol):
    async def generate(self, messages: list[Message], tools: list[ToolSchema],
                        stream: bool = True) -> AsyncIterator[ModelChunk]: ...
    async def list_models(self) -> list[ModelInfo]: ...
    def capabilities(self) -> ModelCapabilities: ...
```

Implementations: `OllamaProvider`, `LlamaCppProvider`, and later
`AnthropicProvider` / other cloud providers — all optional, all behind the
same interface. The Agent Engine and UI never import a concrete provider
directly; they go through `ModelRouter`.

### 5.2 Model registry entry (JSON)

```json
{
  "name": "Qwen3-Coder",
  "provider": "ollama",
  "type": "coding",
  "format": "GGUF",
  "context": 256000,
  "capabilities": ["coding", "agent", "reasoning", "tool-use"],
  "min_vram_gb": 8
}
```

### 5.3 Model Router

Rule-based first (task-type → model-type mapping, as in the product brief);
each rule is overridable from Settings, and the user can always pin a model
manually per-conversation. A learned/ranked router is an explicit
**non-goal** for the initial phases — adds complexity with no local-first
benefit yet.

## 6. Agent Engine

Core loop (see `core/agent/`):

```text
Understand → Plan → Select Tools → Execute → Observe → Analyze
    → Correct → Retry → Validate → Report
```

Implemented as an explicit state machine (`AgentRun` with a `status` and a
list of `Step`s), not a hidden prompt loop — every step is persisted
(Memory Engine) so the UI's Live Agent View can render it and a crashed run
can be resumed from its last checkpoint (Section 8).

Key interfaces:

- `Planner`: turns a user goal + context into an ordered step list.
- `Executor`: runs one step, which is either a tool call or a model call.
- `Observer`: captures step output, truncates/summarizes for context budget.
- `Validator`: checks a step's result against its stated intent (e.g. "file
  was actually created", "scan actually returned data") before continuing.
- `RetryPolicy`: bounded retries with backoff and a max-steps safety limit.

## 7. Tool system

### 7.1 Tool Registry

Tools are **data, not code paths** — defined by a JSON/YAML schema and
resolved generically:

```json
{
  "name": "nmap",
  "category": "security",
  "executable": "nmap",
  "args_schema": { "type": "object", "properties": { "target": {"type": "string"}, "flags": {"type": "array"} } },
  "enabled": true,
  "risk_level": "HIGH",
  "requires_confirmation": true,
  "requires_scope_check": true,
  "supports_streaming": true
}
```

### 7.2 Universal Tool Adapter

```text
Agent: run_tool(tool="nmap", arguments={...})
    → Tool Router (resolves registry entry)
    → Permission Engine (risk level + scope check + user confirmation if needed)
    → Execution Engine (subprocess, capture stdout/stderr/exit code, timeout)
    → Output Parser (optional, per-tool structured parsing, e.g. nmap XML)
    → back to Agent as an Observation
```

The agent only ever calls `run_tool(name, args)` — it does not need
tool-specific glue code. New tools are added by registering a schema, not by
writing new agent logic. User-defined custom tools (Section "Tool
Marketplace" in the product brief) use the exact same path.

### 7.3 Built-in categories (see `TOOLS.md` for the authoritative, versioned list)

System, Development, Network, Security, Forensics, Custom — matching the
product brief's taxonomy. **Security-category tools are off by default** and
require the Confirmation Engine + Target Scope to be configured before they
can run even once (Section 9).

## 8. Execution Engine & crash recovery

- Every tool invocation and every agent run gets a `run_id`, persisted
  before execution starts.
- Long agent runs checkpoint after each validated step (append-only in
  SQLite): on restart, `AgentRun.status == "interrupted"` runs are offered to
  the user as "Resume" or "Discard" — never silently auto-resumed.
- Kill switch (Section below) terminates the full process tree
  (parent + children via `psutil`), not just the top-level PID.

## 9. Permission, scope, and confirmation engine

Three independent gates, all must pass for a HIGH/CRITICAL action:

1. **Risk classification** (per tool, from registry: LOW/MEDIUM/HIGH/CRITICAL)
2. **Target Scope** — an explicit allowlist of IPs/CIDRs/hostnames the user
   has configured as authorized targets for the current project. Any
   network/security tool call against a target outside this list is
   **rejected before execution**, not just flagged after.
3. **Autonomy Mode** — SAFE (confirm every tool call) / AUTO (confirm
   MEDIUM+) / FULL (confirm CRITICAL only, within workspace+scope bounds).
   FULL mode is opt-in per session and still enforces the Target Scope and
   kill switch.

This is the mechanism that lets the product brief's "autonomous cybersecurity
agent" goal coexist with the project's safety requirements: autonomy is about
*not asking the user to approve every click*, not about removing the
scope/consent boundary.

### Kill switch

UI-visible `STOP AGENT` button + `cici stop` CLI + `/api/agent/{id}/stop`:
cancels the agent loop, terminates child processes via the Execution Engine,
releases resources, persists final state. This is implemented in Phase 3/4,
not deferred — it's a prerequisite for enabling AUTO/FULL autonomy at all.

## 10. Memory system

Three tiers, all backed by SQLite initially:

- **Session memory**: current conversation, in-process + persisted per
  session id.
- **Project memory**: `projects/<name>/memory/` — findings, context, and
  conversation history scoped to one project.
- **Global memory**: explicit, user-saved facts (not an automatic log of
  everything) — same model as this assistant's own memory convention:
  one fact per record, with a reason it was saved.

A vector/embedding index is a **Phase 7 addition**, not a Phase 1
requirement — full-text search over SQLite is sufficient until there's a
real need for semantic recall.

## 11. Hardware profiling & model routing

`core/orchestration/hardware_profile.py` detects CPU, RAM, and GPU
(NVIDIA via `nvidia-smi` / `pynvml`, AMD via `rocm-smi`, else CPU-only) at
backend startup, and exposes `/api/system/hardware`. The frontend shows this
on the Dashboard; the Model Router uses VRAM to filter which registered
models are even offered as "recommended."

## 12. Frontend

React + TypeScript + TailwindCSS SPA (`apps/frontend`), dark/premium theme
per the design language in the product brief (dark green / deep blue /
black / soft gray; no oversized cards or childish UI). Talks to the backend
over REST for CRUD-style calls and WebSocket for chat streaming + Live Agent
View updates. No separate state-management framework beyond React context +
a lightweight query layer (TanStack Query) until there's evidence more is
needed.

## 13. Portable/offline runtime (Windows first, Linux boot later)

- **Phase 9a (Windows portable):** `START-AI.exe` launches the bundled
  Python runtime + Ollama/llama.cpp + backend + frontend static build, opens
  the default browser to `http://localhost:<port>`. This is the realistic
  near-term target and is explicitly *not* the same thing as a bootable
  USB OS image.
- **Phase 9b (Linux boot environment):** a minimal Debian/Ubuntu-based live
  image is a substantially larger effort (custom ISO build, driver
  bundling, UEFI boot testing across hardware) and is scoped as its own
  mini-project under `boot/`, tracked separately in `BOOT.md`. It is not a
  blocker for Phases 1–8.

## 14. Non-goals (for now)

- Multi-agent orchestration (Section 42 of the brief) — valuable, but only
  after the single-agent loop, tool registry, and validation are solid.
  Revisit after Phase 4.
- Encrypted workspace, full secret-store UX — ship a working unencrypted
  default first (Phase 1-4), harden in Phase 10.
- A general plugin marketplace UI — the plugin *interface* ships early
  (Section 36 of the brief), a marketplace browsing UI does not.

## 15. Open decisions

These need a decision before the phase that depends on them starts (tracked
in `IMPLEMENTATION_STATUS.md`):

- Exact sandboxing strategy on Windows for untrusted code execution (Docker
  Desktop dependency vs. a lighter-weight approach) — affects Phase 4/20.
- Whether `cici` CLI is a thin HTTP client to the same backend (recommended)
  or an independent entry point duplicating agent logic.
