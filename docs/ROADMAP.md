# CiciByte AI — Roadmap

Status: **Draft v0.1**
Last updated: 2026-10-01

Each phase must end with a **working, testable** application — no phase
hands off a half-wired feature to the next one. After finishing a phase,
update `IMPLEMENTATION_STATUS.md` before starting the next.

Legend: ✅ done · 🔄 in progress · ⬜ not started

## Phase 1 — Foundation
Goal: a running backend + frontend shell with config and logging, nothing
AI-specific yet.

- ✅ Repository scaffold matches `ARCHITECTURE.md` layout
- ✅ FastAPI app boots, `/api/health` returns hardware + version info
- ✅ React app boots, shows the shell (sidebar nav, panels marked "soon" where unbuilt, ● LOCAL/OFFLINE status)
- ✅ Config system (`config/default.yaml` + env override + `/api/config`)
- ✅ Structured logging (JSON lines to `logs/`, human-readable console)
- ✅ `START-AI` launcher script (Windows `.bat`/`.ps1`; POSIX `start.sh` deferred to Phase 9b)
- ✅ (added, ahead of schedule) model registry (`config/models.yaml`) + `/api/models/registry` + Models panel, per the requested GENERAL/UNCENSORED/CODING/REASONING/EXPERIMENTAL taxonomy — see `docs/MODELS.md`

**Exit test:** ✅ done 2026-10-02 — backend started via uvicorn, `/api/health`
and `/api/models/registry` verified live with real hardware data; frontend
dev server verified in-browser against the live backend (Dashboard shows
real CPU/RAM/OS/GPU, Models panel shows the 5-entry registry grouped and
selectable). `npm run build` and `pytest` both pass. Launcher script not yet
exercised on a second machine (single-machine smoke test only) — full
cross-machine check happens in Phase 9.

## Phase 2 — AI Runtime
Goal: real local chat with a real model, streaming, no agent/tools yet.

- ✅ `ModelProvider` interface + `OllamaProvider` implementation
- ✅ Model discovery (live `ollama list`-equivalent merged into `/api/models/registry`, + `/api/models/ollama/status`)
- ✅ Model Router (rule-based, task-type → category mapping, manual override wins)
- ✅ Chat endpoint with WebSocket streaming (`/ws/chat`)
- ✅ Chat UI: model selector, streamed tokens, error surface when Ollama/model unavailable
- ✅ (added, ahead of schedule) Network Mode switch (offline/lan/internet) + gated model download (`POST /api/models/pull`, streamed progress) — needed so a user can fetch a new model on demand without the system defaulting to always-online

**Exit test:** ⚠️ **partially verified** — this dev machine has no Ollama
installed, so the full "streamed conversation" path could not be exercised
end-to-end yet. What *was* verified on 2026-10-02:
- Every code path fails soft when Ollama is absent (`ollama_reachable: false`,
  no crash, clear error surfaced in both API responses and the Chat/Models UI).
- WebSocket chat correctly rejects empty input and unknown model names, and
  correctly reports "Ollama not reachable" for a configured model.
- Network Mode toggle works end-to-end (header control → backend → Models
  panel reacts); pulling a model is blocked with HTTP 409 while offline, and
  attempts a real `ollama pull` once switched to Internet (observed the
  expected "Ollama is not reachable" failure, not a silent hang or crash).
- 13/13 backend tests pass; frontend builds clean.

**Follow-up required before this phase is fully ✅:** install Ollama on a
dev/test machine, pull at least one registered tag (`dolphin3:8b` is the
most likely to resolve as-is), and verify an actual streamed chat
response end-to-end. Also confirm the `qwen3-coder:30b` tag against
`ollama list`/ollama.com's library — it was not possible to verify this
tag's exact spelling without a reachable Ollama instance; treat it as
unconfirmed until checked (`docs/MODELS.md` and `config/models.yaml` both
flag this).

## Phase 3 — Agent Core ✅ (2026-10-02)
Goal: the Plan/Execute/Observe/Validate loop runs end-to-end against a
no-op or trivial tool set, with persistence and the kill switch.

- ✅ `AgentRun`/`Step` data model + SQLite persistence (`apps/backend/app/agent/db.py`, plain sqlite3 + `asyncio.to_thread`)
- ✅ Planner (stub-plan only, by design — see `planner.py`), Executor, bounded RetryPolicy (`retry.py`). Validator is a stub pass-through for now, with the hook point already in place in `manager.py` for a real one.
- ✅ Checkpointing after each step; resume-after-crash (`recover_interrupted_runs()` on startup marks stuck "running" rows "interrupted" and resets their in-flight step to "pending")
- ✅ Kill switch: UI "🛑 STOP AGENT" button (global, always visible, badge shows active count), per-run Stop button, `POST /api/agent/runs/{id}/stop`, `POST /api/agent/stop-all`, `cici stop [run_id]` CLI (`apps/cli/cici.py`)
- ✅ Live Agent View: step list with status, expandable params/output/error, live via `WS /ws/agent/{id}`

**Exit test:** ✅ done 2026-10-02. Backend: 10 dedicated agent tests
(23/23 total passing), including an actual `task.cancel()` kill mid-sleep,
a simulated crash (a run+step left "running" in the DB with no in-memory
task) correctly recovered to "interrupted," and a resume that skips the
already-"done" step and only re-runs from the checkpoint. Browser e2e:
started a 60-second stub_sleep run, clicked the real "🛑 STOP AGENT" button
in the UI, confirmed via the API that the run stopped ~8 seconds in with
status "stopped" — not a simulated UI state change, an actual cancelled
asyncio task. Note: "terminates the process tree" from the original exit
test wording applies starting Phase 4, once there's a real subprocess to
terminate — Phase 3 has no real external process yet, by design (stub
executors only), so the kill switch here cancels the asyncio task running
the step loop. The psutil-based process-tree kill described in
ARCHITECTURE.md §8 is still correct for Phase 4 and unaffected by this.

## Phase 4 — Tool Engine ✅ (2026-10-02)
Goal: the Universal Tool Adapter is real, with permissions, for a small set
of safe development/system tools.

- ✅ Tool Registry (`config/tools.yaml`) + loader/validator (`app/tools/registry.py`)
- ✅ Execution Engine: real subprocess (`python`, `git`) with stdout/stderr/exit code/timeout, **and real process-tree termination via psutil on cancel** — plus in-process filesystem ops (`list`/`read`/`write`/`delete`) scoped to `workspace/`+`projects/` with path-traversal rejection
- ✅ Permission Engine: risk levels (LOW/MEDIUM/HIGH/CRITICAL) × Autonomy Modes (SAFE/AUTO/FULL), runtime-switchable like Network Mode
- ✅ Confirmation UI: an always-visible top banner (`ConfirmationBar`) for pending confirmations, Allow/Deny, independent of which panel is open
- ✅ Built-in tools: `python`, `git`, `filesystem_list`/`filesystem_read`/`filesystem_write`/`filesystem_delete`
- ✅ Audit log: every invocation persisted (`data/tools.db`) with timestamp, tool, args, exit code, stdout/stderr/output, duration — exposed via `GET /api/tools/invocations` and the Tools panel
- ✅ (integration) Agent Core's `tool_call` step type now runs real tools through this exact engine — Phase 3's stub executors remain for regression tests, but the agent can now do real work

**Exit test:** ✅ done 2026-10-02, and taken further than originally scoped
(no live Ollama yet to drive "summarize a file" through chat, so the test
used an explicit 3-step plan instead of a model-authored one — see note
below). An agent run executed `filesystem_list` → `filesystem_write` →
`filesystem_read` as real `tool_call` steps; the read step's output
(`"Phase 4 proof"`) was confirmed to be exactly what the write step had
just written, through the real filesystem execution path, verified live in
the browser's Live Agent View. Separately verified: a SAFE-mode
`filesystem_list` invocation produced a `pending_confirmation` row, showed
up in the always-visible `ConfirmationBar`, and clicking "Allow" in the
actual UI (not the API) carried it to `done`. A **real OS subprocess**
(`python -c "import time; time.sleep(30)"`) was cancelled via
`POST /api/tools/invocations/{id}/cancel`, confirmed via `psutil.pid_exists()`
to have actually died (not just abandoned) — the single most
safety-critical claim in this phase, and it wasn't just asserted, it was
checked. 35/35 backend tests pass (12 new for the tool engine).

**Known scope note:** the exit test's original "summarize a given file"
wording implies a model reading file content — that needs Phase 2's chat
model wired into a real Planner, which doesn't exist yet (Phase 3's
planner is still rule-free by design, see `planner.py`). Explicit
multi-step plans work end-to-end today; a model-authored plan is a
reasonable Phase 5+ addition once there's a concrete reason to build it.

## Phase 5 — Terminal ✅ (2026-10-02)
Goal: a real, shared terminal in the UI.

- ✅ PTY-backed terminal session — Windows via `pywinpty`/ConPTY, verified against a real spawned `powershell.exe` before writing any app code (see IMPLEMENTATION_STATUS.md). POSIX (`ptyprocess`, near-identical API) is correctly deferred to Phase 9b — can't be verified on this dev machine, so it wasn't written speculatively.
- ✅ Terminal panel in UI (`@xterm/xterm` + `@xterm/addon-fit`) wired to the backend over `WS /ws/terminal/{id}`, full ANSI rendering (PSReadLine syntax highlighting, table formatting) confirmed live
- ✅ "Send output to AI" — strips ANSI codes from the session's captured buffer and seeds the Chat panel's input with it
- ✅ Process manager view: the session list (shell, alive/dead, created_at) doubles as this for Phase 5's scope — a full OS-wide process browser was never in scope, only sessions this app started

**Exit test:** ✅ done 2026-10-02, verified live in the browser, not just
via backend tests. Opened a PowerShell session, typed
`Get-ChildItem | Select-Object -First 3`, watched the real, correctly
table-formatted output render in xterm.js. Clicked "Send output to AI" —
confirmed via direct DOM inspection (not just `get_page_text`, which
doesn't surface input values) that the Chat panel's message box was
seeded with the actual captured terminal text. Closed the session and
confirmed via `Get-CimInstance Win32_Process` that the real PowerShell
process was gone, not orphaned. 39/39 backend tests pass (4 new,
including one that runs a real command through the full WebSocket stack
and asserts its exact output string appears).

**Known rough edge (not a bug):** captured terminal output includes
PSReadLine's live incremental-redraw artifacts (e.g. a typed command can
appear partially duplicated character-by-character in the raw buffer)
because the capture is a faithful recording of the raw PTY stream. The
model can still make sense of it, but a cleaner capture (stripping
redraw sequences, not just color codes) would be a nice Phase 8 polish
item, not a Phase 5 blocker.

## Phase 6 — Cyber Toolchain
Goal: security tool adapters, gated by Target Scope from day one — this
phase does not ship without Section 9 of `ARCHITECTURE.md` enforced.

- ⬜ Target Scope config (per-project authorized targets, UI + `/api/scope`)
- ⬜ Scope-check enforced in Permission Engine *before* any network/security tool runs
- ⬜ Adapters: nmap, nikto, ffuf (start with tools that have simple CLI + parseable output)
- ⬜ Adapters: nuclei, sqlmap (template/payload-driven, HIGH risk, confirmation required)
- ⬜ YARA integration (rule scanning against files/workspace, not network-facing — lower friction)
- ⬜ Security workspace layout (`workspace/Security/{Recon,Scans,Reports,Evidence}`) + auto-filing of outputs
- ⬜ Wireshark/tshark + basic PCAP workflow (capture-to-file, tshark-based summarization)

**Exit test:** configure a scope of `localhost` only, ask the agent to scan
it with nmap — it runs; ask it to scan an out-of-scope address — it refuses
with a clear reason, logged in the audit log.

## Phase 7 — Memory
Goal: memory tiers are real and used, not just modeled.

- ⬜ Session memory (persisted, resumable conversations)
- ⬜ Project memory (`projects/<name>/memory/`, surfaced in Projects UI)
- ⬜ Global memory (explicit save/recall, user-visible and editable list)
- ⬜ Full-text search across memory tiers (`/api/memory/search`)
- ⬜ (Stretch, post-MVP) vector index for semantic recall over long project history

**Exit test:** close and reopen the app, a prior project's context and
findings are still there and searchable.

## Phase 8 — UI Completion
Goal: every panel in the product brief's nav exists and does real work
(no placeholders).

- ⬜ Dashboard (hardware, status, recent activity)
- ⬜ Models (list/download/load/unload/delete, respecting disk budget)
- ⬜ Agents (list runs, history, resume/discard interrupted runs)
- ⬜ Tools (registry browser + "Add custom tool" form)
- ⬜ Projects (create/switch/configure per-project settings)
- ⬜ Security (scope config, findings, reports)
- ⬜ Logs (searchable audit log + runtime log viewer)
- ⬜ Settings (autonomy mode, secrets, network mode, theme)

**Exit test:** a new user can go end-to-end — create a project, chat, run a
tool, view the audit log, generate a report — without touching a config
file by hand.

## Phase 9 — Portable Runtime
- ⬜ 9a. Windows portable mode: `START-AI.exe`, bundled runtime, relocatable
  from any drive letter (tests actual USB/external-SSD boot, not just `C:`)
- ⬜ 9b. Hardware/GPU detection validated on NVIDIA, AMD, and CPU-only machines
- ⬜ 9c. Linux boot environment — scoped and tracked separately in `BOOT.md`;
  treated as its own sub-roadmap, not a blocker for 1.0

**Exit test (9a/9b):** copy the SSD contents to a different machine with
different GPU vendor, run the launcher, hardware detection and model
recommendation adapt correctly.

## Phase 10 — Hardening
- ⬜ Secret store (OS keychain-backed, encrypted file fallback)
- ⬜ Encrypted workspace option for security-engagement data
- ⬜ Permission policy review (confirm default risk levels are conservative)
- ⬜ Crash recovery tested under induced failures (kill -9 mid-run, disk full, etc.)
- ⬜ Integrity checking for the portable image (checksums for runtime/tools)

## Phase 11 — Testing matrix
Run the full test suite + manual acceptance pass across:
CPU-only, NVIDIA, AMD, low RAM, high RAM, offline, LAN, internet-connected,
USB boot, Windows portable, Linux boot.

## Later / explicitly deferred
- Multi-agent orchestration (Research/Coding/Security/Verification/Reporting
  agents) — after Phase 4 is solid.
- Model download manager UI polish, tool marketplace browsing UI.
- Report Engine output formats beyond Markdown/JSON (HTML/PDF/CSV) — ship
  Markdown+JSON first since every downstream format can derive from them.

## Working agreement for each phase

```text
IMPLEMENT → TEST → FIX → DOCUMENT → VERIFY → CONTINUE
```

No phase is marked ✅ in `IMPLEMENTATION_STATUS.md` until its exit test above
has actually been run, not just "should work."
