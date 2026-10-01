# CiciByte AI — Model Registry

Last updated: 2026-10-02

The model registry (`config/models.yaml`) is a flat list of model entries the
Model Router and the UI's **Models** panel read from. CiciByte AI itself does
not ship model weights or modify model behavior — it loads whatever GGUF
files you place under `models/<CATEGORY>/` and point a registry entry at.
Categories below are **organizational metadata only** (how the Models panel
groups and labels entries); they do not change how a model is executed.

## Directory layout

```text
models/
├── GENERAL/
│   └── dolphin3-8b.gguf
├── UNCENSORED/
│   └── dolphin3-24b.gguf
├── CODING/
│   └── qwen3-coder-30b-a3b.gguf
├── REASONING/
│   └── deepseek-r1.gguf
└── EXPERIMENTAL/
    ├── qwen-abliterated.gguf
    └── ...community GGUFs
```

`models/` is gitignored (weights are large, local-only, and not portable via
the git repo — they're part of the USB/SSD payload instead, see
`DEPLOYMENT.md`).

## Registry schema

Each entry in `config/models.yaml`:

```yaml
- name: Qwen3-Coder
  category: CODING          # GENERAL | UNCENSORED | CODING | REASONING | EXPERIMENTAL
  provider: ollama           # ollama | llama_cpp | (cloud providers, later, opt-in)
  type: coding               # task-type used by the Model Router
  format: GGUF
  context: 256000
  capabilities: [coding, agent, reasoning, tool-use]
  min_vram_gb: 8
  path: models/CODING/qwen3-coder-30b-a3b.gguf
  default: true              # preselected in the UI
```

`provider` + `path`/`ollama_tag` tell the backend how to actually load it
(Phase 2: `OllamaProvider` / `LlamaCppProvider`, see `ARCHITECTURE.md` §5).
Phase 1 only reads and lists this registry — it does not load models yet.

## Default registry (initial set)

| Category | Model | Type | Notes |
|---|---|---|---|
| CODING | Qwen3-Coder | coding | Default selected model — coding/agent/tool-use tasks |
| UNCENSORED | Dolphin 3 24B | general | No built-in content filtering beyond the base model |
| GENERAL | Dolphin 3 8B | general | Lighter-weight default for low-VRAM hardware |
| REASONING | DeepSeek-R1 | reasoning | Deep reasoning / long chain-of-thought tasks |
| EXPERIMENTAL | Qwen Abliterated | experimental | Community fine-tune; unvetted, opt-in |
| EXPERIMENTAL | *(user-added community GGUFs)* | experimental | Anything else you drop into `models/EXPERIMENTAL/` + register |

All five categories are visible in the UI's Models panel at all times; only
entries whose `.gguf` file is actually present on disk show as
"Installed" / selectable. The Model Router (Phase 2) only ever picks a model
from this registry — never an undeclared file.

## Models panel (UI)

```text
MODEL

● Qwen3-Coder
  Coding / Agent

○ Dolphin 3 24B
  Uncensored / General

○ DeepSeek-R1
  Reasoning

○ Experimental
  Community Models
```

`●` = currently selected/loaded, `○` = available. Selecting "Experimental"
expands to the list of registered `EXPERIMENTAL`-category models rather than
loading one directly, since that category is expected to grow/change as the
user adds community GGUFs.

## Scope note

CiciByte AI does not evaluate, filter, or restrict model *outputs* based on
category — "UNCENSORED"/"EXPERIMENTAL" are labels telling the user what kind
of model behavior to expect, not a system guarantee. The operational
controls described in `ARCHITECTURE.md` §9 (Target Scope, Confirmation
Engine, Audit Log) are independent of which model is loaded and apply the
same way regardless of category — they govern *tool execution*, not model
text generation.
