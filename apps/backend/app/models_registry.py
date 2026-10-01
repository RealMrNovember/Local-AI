"""Model registry loader — reads config/models.yaml.

Phase 1 scope: list registry entries and whether their GGUF file is present
on disk ("installed"). Loading/running a model is Phase 2 (ModelProvider /
ModelRouter, see ARCHITECTURE.md Section 5).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import REPO_ROOT


@dataclass
class ModelEntry:
    name: str
    category: str
    provider: str
    type: str
    format: str
    context: int
    capabilities: list[str]
    min_vram_gb: float
    path: str
    ollama_tag: str | None
    default: bool
    installed: bool
    install_source: str | None = None  # "file" | "ollama" | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "provider": self.provider,
            "type": self.type,
            "format": self.format,
            "context": self.context,
            "capabilities": self.capabilities,
            "min_vram_gb": self.min_vram_gb,
            "path": self.path,
            "ollama_tag": self.ollama_tag,
            "default": self.default,
            "installed": self.installed,
            "install_source": self.install_source,
        }


CATEGORY_ORDER = ["CODING", "UNCENSORED", "GENERAL", "REASONING", "EXPERIMENTAL"]


def load_registry(registry_path: Path | None = None) -> list[ModelEntry]:
    path = registry_path or (REPO_ROOT / "config" / "models.yaml")
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    entries: list[ModelEntry] = []
    for raw in data.get("models", []):
        model_path = REPO_ROOT / raw["path"]
        file_installed = model_path.exists()
        entries.append(
            ModelEntry(
                name=raw["name"],
                category=raw["category"],
                provider=raw["provider"],
                type=raw["type"],
                format=raw["format"],
                context=raw["context"],
                capabilities=list(raw.get("capabilities", [])),
                min_vram_gb=raw.get("min_vram_gb", 0),
                path=raw["path"],
                ollama_tag=raw.get("ollama_tag"),
                default=bool(raw.get("default", False)),
                installed=file_installed,
                install_source="file" if file_installed else None,
            )
        )

    def sort_key(e: ModelEntry) -> tuple[int, str]:
        try:
            idx = CATEGORY_ORDER.index(e.category)
        except ValueError:
            idx = len(CATEGORY_ORDER)
        return (idx, e.name)

    return sorted(entries, key=sort_key)


def merge_ollama_status(entries: list[ModelEntry], ollama_installed_tags: list[str]) -> list[ModelEntry]:
    """Mark entries as installed when their ollama_tag is already pulled,
    even if no local GGUF file sits at `path`. Does not mutate in place —
    returns a new list, since entries are otherwise treated as immutable
    registry data."""
    tag_set = set(ollama_installed_tags)
    merged: list[ModelEntry] = []
    for e in entries:
        if not e.installed and e.ollama_tag and e.ollama_tag in tag_set:
            merged.append(
                ModelEntry(
                    **{**e.to_dict(), "installed": True, "install_source": "ollama"}
                )
            )
        else:
            merged.append(e)
    return merged
