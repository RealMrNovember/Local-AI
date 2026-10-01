# CiciByte AI — Implementation Status

Last updated: 2026-10-02

This file tracks what actually exists and runs, as opposed to what's
planned. Update it at the end of every phase (see `ROADMAP.md`'s working
agreement: IMPLEMENT → TEST → FIX → DOCUMENT → VERIFY → CONTINUE). A phase
is only marked ✅ once its exit test has actually been executed.

## Decisions on record

- **Model freedom, operational safety unchanged.** The user chooses which
  local model weights to run (e.g. Qwen3-Coder, DeepSeek-R1) — the system is
  provider-independent and does not police model content. What the system
  *does* keep, regardless of model: Target Scope enforcement, the
  Confirmation/Risk Engine, and the Audit Log (Architecture §9). These are
  operational controls (don't hit out-of-scope targets, keep a record of
  what ran, allow instant kill), not content moderation, and they stay in
  place even in FULL autonomy mode and even for the user's own
  infrastructure.
- **Offline-first is a hard requirement, not an aspiration.** Network Mode
  "Offline" must result in zero outbound connections from backend, agent,
  and tool processes. This is load-bearing for the user's stated use case
  (testing owned infrastructure without any data leaving the local network).
- **USB bootable OS sequencing (2026-10-02):** build the full
  backend/agent/tool/UI stack on a normal OS first (Phases 1–8), validate it
  end-to-end, *then* port it into a bootable Linux USB image (Phase 9b /
  `BOOT.md`). Rejected alternative: building the live-boot environment in
  parallel from day one — more realistic target-env coverage, but slows
  every phase down and was declined in favor of faster iteration.

## Phase status

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Planning | ✅ | `ARCHITECTURE.md`, `ROADMAP.md`, this file created. Repo is currently an empty folder skeleton (no code, not a git repo yet). |
| 1 | Foundation | ✅ | See "Phase 1 — completed" below. |
| 2 | AI Runtime | ⚠️ | Built and fail-soft-tested; needs a real Ollama install to confirm an actual end-to-end streamed chat. See "Phase 2 — completed" below. |
| 3 | Agent Core | ✅ | Fully built and verified, including a real kill-switch click in the browser. See "Phase 3 — completed" below. |
| 4 | Tool Engine | ⬜ | Not started |
| 5 | Terminal | ⬜ | Not started |
| 6 | Cyber Toolchain | ⬜ | Not started |
| 7 | Memory | ⬜ | Not started |
| 8 | UI Completion | ⬜ | Not started |
| 9 | Portable Runtime (9a/9b) | ⬜ | Not started |
| 10 | Hardening | ⬜ | Not started |
| 11 | Testing matrix | ⬜ | Not started |

## Phase 1 — completed (2026-10-02)

**Backend** (`apps/backend`, FastAPI + Python 3.12, venv at `apps/backend/.venv`):
- `app/config.py` — loads `config/default.yaml`, applies `CICIBYTE__SECTION__KEY` env overrides.
- `app/logging_config.py` — JSON-lines file logging (`logs/app.jsonl`) + console.
- `app/hardware.py` — CPU/RAM always detected via `psutil`; GPU detection tries
  `nvidia-smi` then `rocm-smi`, returns an empty list (not an error) when neither
  is found. Verified on this dev machine: correctly reports 0 GPUs (none present).
- `app/models_registry.py` — loads `config/models.yaml`, resolves each entry's
  `path` against the repo root to compute `installed: bool`.
- Routers: `GET /api/health` (status+version+hardware), `GET /api/config`
  (safe subset only), `GET /api/models/registry`.
- Tests: `apps/backend/tests/` — 5 tests, all passing (`pytest -q`).
- Verified live: started with `uvicorn app.main:app`, hit both endpoints with
  `Invoke-RestMethod`, got real hardware values and the 5-entry model registry
  back, correctly sorted and categorized.

**Frontend** (`apps/frontend`, React 19 + TypeScript + Vite + Tailwind v4):
- `src/api/client.ts` — typed fetch wrapper for `/api/health`, `/api/models/registry`.
- `src/components/Sidebar.tsx` — full nav from the product brief; unimplemented
  panels are visibly marked "soon," not fake-interactive.
- `src/components/StatusBadge.tsx` — ● LOCAL/OFFLINE indicator, reflects
  actual backend reachability + `network_mode`, not a hardcoded value.
- `src/pages/Dashboard.tsx` — live hardware profile from the backend.
- `src/pages/Models.tsx` — model list matching the requested category
  taxonomy (CODING/UNCENSORED/GENERAL/REASONING/EXPERIMENTAL), Qwen3-Coder
  preselected as default, Experimental grouped as a collapsible "Community
  Models" section. Un-installed entries are shown but disabled (no GGUF on
  disk yet) rather than silently clickable.
- `src/pages/ComingSoon.tsx` — explicit placeholder for not-yet-built panels.
- `npm run build` passes (tsc + vite build, no errors).
- Verified live end-to-end in the browser pane against the real backend:
  Dashboard renders real CPU/RAM/OS/GPU data; Models panel renders the
  5-entry registry grouped and labeled exactly as specified, with ●/○
  selection state and the Experimental accordion working.

**Config/model registry:**
- `config/default.yaml` — app/server/network/paths/logging/autonomy defaults.
- `config/models.yaml` — 5-entry registry per the requested taxonomy (see
  `docs/MODELS.md` for the full schema and the scope note on what
  "UNCENSORED"/"EXPERIMENTAL" categories do and don't mean for the system's
  behavior).
- `models/{GENERAL,UNCENSORED,CODING,REASONING,EXPERIMENTAL}/` created
  (empty, `.gitkeep`'d — actual GGUF files are Phase 2+ and gitignored).

**Launcher:** `apps/launcher/START-AI.bat` + `START-AI.ps1` — creates the
backend venv if missing, installs deps, runs uvicorn. Not yet a bundled
no-dependency launcher (that's Phase 9a).

**Not done in Phase 1 (by design, deferred to later phases):** model
loading/inference (Phase 2), agent loop (Phase 3), tool execution (Phase 4),
terminal (Phase 5), security tools (Phase 6), persistent memory beyond
config files (Phase 7), remaining UI panels (Phase 8).

**Repo state:** still not a git repository — no commit has been made yet
(standing rule: commit only when the user asks).

## Phase 2 — completed (2026-10-02), pending real-Ollama verification

**Backend additions** (`apps/backend/app/models/`):
- `provider.py` — `ModelProvider` Protocol, `ChatMessage`/`ChatChunk` types.
- `ollama_provider.py` — `OllamaProvider`: `is_reachable()`, `list_installed()`,
  `chat()` (streams `/api/chat`), `pull()` (streams `/api/pull`). Every
  method fails soft (returns False/[]/an error chunk) instead of raising
  when Ollama is unreachable — verified live on this machine (no Ollama
  installed): zero crashes, clean error propagation end-to-end.
- `router.py` — rule-based `pick_model(task_type)`: CODING/REASONING/GENERAL
  category preference per task type, falls back to the registry default.
- `runtime_state.py` — in-memory, mutable `network_mode` (offline/lan/internet),
  separate from the cached static config so it can change without a restart.
  **Not persisted across restarts** — that's Phase 8's job.
- Routers: `GET/PUT /api/network/mode`, `GET /api/models/ollama/status`,
  `POST /api/models/pull` (409 if network mode is offline, 503 if Ollama
  unreachable, else streams NDJSON pull progress), `WS /ws/chat`.
- `models_registry.py` extended: entries now carry `ollama_tag` +
  `install_source` ("file" | "ollama" | null); `merge_ollama_status()`
  marks an entry installed if its tag shows up in a live `ollama list`,
  without needing a local GGUF file.
- Tests: 13/13 passing, including offline-first regression checks
  (`test_pull_blocked_when_offline`, `test_ollama_status_fails_soft_when_unreachable`)
  and WebSocket error-path checks (`test_chat.py`).

**Frontend additions:**
- `pages/Chat.tsx` — model selector (only installed models selectable),
  streaming message view over native `WebSocket`, visible error banner on
  failure (no silent failure, no fake "thinking" animation pretending to
  work when the backend errored).
- `components/NetworkModeControl.tsx` — header dropdown, calls
  `PUT /api/network/mode` live.
- `pages/Models.tsx` — "Pull" button per entry with an `ollama_tag`, gated
  client-side (disabled unless network mode ≠ offline) *and* server-side
  (409 regardless of what the client sends) — the client-side gate is a UX
  convenience, not the actual boundary. NDJSON streaming progress rendered
  inline during a pull.
- **Bug found and fixed during manual verification:** `Models.tsx`
  originally fetched `network_mode` itself in a one-shot `useEffect`, so it
  went stale the moment the header's `NetworkModeControl` changed it —
  Pull buttons stayed disabled after switching to Internet mode. Fixed by
  lifting `networkMode` state to `App.tsx` and passing it down as a prop.
  Caught by actually clicking through the UI in the browser pane, not just
  by reading the code.
- `npm run build` passes.

**What was and wasn't verified (be precise about this):**
- ✅ Verified live in-browser: Network Mode toggle propagates correctly;
  Pull against a real (absent) Ollama produces a clean, visible error;
  Chat page correctly refuses to let you send with no installed model and
  reports a clear error when attempted anyway.
- ❌ NOT verified: an actual successful model pull, and an actual streamed
  chat response from a running model. This dev machine does not have
  Ollama installed. **This must be done before Phase 2 is marked fully ✅**
  in `ROADMAP.md` — install Ollama, `ollama pull dolphin3:8b` (best-odds
  confirmed tag), and chat with it through the UI.
- ⚠️ `ollama_tag: qwen3-coder:30b` in `config/models.yaml` is a
  best-effort guess, not a confirmed tag — verify against a real
  `ollama list` / the Ollama library before relying on it.

## Phase 3 — completed (2026-10-02)

**Backend additions** (`apps/backend/app/agent/`):
- `db.py` — plain sqlite3 (no ORM yet — schema is small), `agent_runs` +
  `agent_steps` tables, every call synchronous and wrapped in
  `asyncio.to_thread` by callers so the event loop never blocks on disk I/O.
  DB file: `data/agent.db` (gitignored, like all other runtime state).
- `planner.py` — `plan_steps()`: explicit caller-supplied steps win;
  otherwise falls back to one trivial `stub_echo` step. Only two stub step
  types exist on purpose — this phase proves the state machine, not
  planning intelligence (that needs Phase 4's real Tool Registry and
  likely a model-backed decomposition step later).
- `executors.py` — `stub_echo`, `stub_sleep`. No filesystem/network/
  subprocess access — deliberately inert so the loop can be proven correct
  in isolation first.
- `retry.py` — bounded `run_with_retry()`, linear backoff, never swallows
  `CancelledError` (a kill-switch cancellation must always propagate).
- `manager.py` — `AgentManager`: the actual Plan→Execute→Observe→Validate
  loop, in-memory `asyncio.Task` registry (kill switch target), pub/sub
  queues per run (Live Agent View transport), `resume_run`/`discard_run`,
  and `recover_interrupted_runs()` (crash recovery, called once at startup).
- Routers (`app/routers/agent.py`): `POST/GET /api/agent/runs`,
  `GET /api/agent/runs/{id}`, `POST .../stop`, `POST .../resume`,
  `POST .../discard`, `POST /api/agent/stop-all`, `WS /ws/agent/{id}`.
- `main.py` lifespan now configures the agent DB, builds the
  `AgentManager` from `config/default.yaml`'s new `agent:` section
  (`max_step_retries`, `retry_backoff_base_s`, `max_steps_per_run`), runs
  crash recovery, and calls `stop_all()` on shutdown.
- `apps/cli/cici.py` (+ `cici.bat`) — stdlib-only HTTP client: `cici stop
  [run_id]`, `cici status`. Thin client only, no agent logic duplicated
  (ARCHITECTURE.md's no-tight-coupling rule).
- Tests: `tests/test_agent.py`, 10 tests — completion, trivial planning,
  rejection of an unknown step type, a **real** kill mid-`stub_sleep`
  (asserts the task actually gets cancelled and both the step and run
  persist as "stopped," not just that the endpoint returns 200), stop-on-
  inactive-run returns 409, the `is_active` flag in the run list, bounded-
  retry exhaustion marking a run "failed," discard, a **simulated crash**
  (a run+step manually left "running" in the DB with no backing task) that
  `recover_interrupted_runs()` correctly flips to "interrupted" with the
  step reset to "pending," and a **resume** that skips the already-"done"
  step and only re-executes from the checkpoint. 23/23 backend tests pass
  overall.

**Frontend additions:**
- `pages/Agents.tsx` — quick-test buttons (echo / 10s sleep, since there's
  no real planner yet to type arbitrary goals into), a run list, and a
  Live Agent View subscribed over `WS /ws/agent/{id}`: step list with
  ✓/✗/●/○ status icons, expandable params/output/error, and
  Stop/Resume/Discard actions gated by the run's actual status.
- `components/KillSwitch.tsx` — the always-visible "🛑 STOP AGENT" header
  button from the product brief (Section 15/45): polls active-run count
  every 3s, disabled at zero, calls `stop-all` when active.
- `api/client.ts` extended with `AgentRun`/`AgentStep`/`AgentRunDetail`
  types and the full agent endpoint set.

**Verified live, not just by reading the code:**
- Ran an echo test through the UI end-to-end: run reached "completed,"
  step showed ✓ with the correct echoed output, Live Agent View updated
  via WebSocket without a page reload.
- Started a **60-second** `stub_sleep` run via a direct API call (to get
  enough margin for manual browser-tool round-trips), confirmed the global
  "🛑 STOP AGENT" header button showed "Stop 1 active run(s)," clicked it,
  and confirmed via `GET /api/agent/runs/{id}` that the run's `status`
  became `"stopped"` with `finished_at` ~8 seconds after `started_at` —
  i.e. the button click actually cancelled a live asyncio task, not just
  changed a UI label. Two earlier attempts with the 10-second quick-test
  button raced against browser-automation round-trip latency and the run
  completed naturally before the click landed — not a product bug, just a
  test-timing artifact, which is why the follow-up used a longer duration.
- `npm run build` passes; 23/23 backend tests pass.

**Known Phase 3 scope boundaries (by design, not gaps):**
- The kill switch cancels an `asyncio.Task`, not a process tree — there is
  no real subprocess yet (stub executors only). The psutil-based
  process-tree termination in ARCHITECTURE.md §8 is correctly scoped to
  Phase 4, once the Tool Registry introduces real subprocesses.
- The Validator step is a pass-through stub (no-exception == valid). A
  real validation pass is a Phase 4+ concern once there's real tool output
  worth validating.
- No model-backed planning — `plan_steps()` is intentionally dumb. Wiring
  the Chat model (Phase 2) into planning is a reasonable Phase 4 addition
  once there are real tools for a model-authored plan to call.

## Environment notes (dev machine, 2026-10-02)

Checked on the current Windows dev machine — informational only, does not
block any phase:

- Python 3.12.10, Node v24.17.0, npm 11.13.0, Git 2.54.0 — all present.
- `ollama` CLI: not found on PATH — needs installing before Phase 2 can be
  exercised locally.
- `nvidia-smi`: not found — either no NVIDIA GPU on this machine or driver
  not on PATH; hardware profiler (Phase 1/Section 11) must handle this
  gracefully (fall back to CPU-only) rather than error.
- Working directory is not yet a git repository.

## Immediate next steps

1. **Close out Phase 2 for real:** install Ollama, `ollama pull dolphin3:8b`,
   confirm an actual end-to-end streamed chat through the UI, and verify/fix
   the `qwen3-coder:30b` tag.
2. Start Phase 4 (Tool Engine): Tool Registry (JSON schemas), real
   Execution Engine (subprocess, stdout/stderr/exit code, timeout, resource
   usage via psutil), Permission Engine (risk levels + Autonomy Modes +
   confirmation UI), audit log, and built-in `python`/`git`/`filesystem`
   tools. This is also where the Agent Core's executors stop being stubs
   and the Planner/Validator get something real to plan against and check.
3. Repo is connected to https://github.com/RealMrNovember/Local-AI and the
   Phase 1-2 commit is pushed to `main`. Remember to commit Phase 3's work
   too once reviewed.
