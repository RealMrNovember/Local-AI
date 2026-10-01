"""Config loading: config/default.yaml + environment variable overrides.

Env override format: CICIBYTE__<SECTION>__<KEY>=value (double underscore
separated, case-insensitive), e.g. CICIBYTE__SERVER__PORT=9000.
"""
from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Repo root = four levels up from this file (app/ -> backend/ -> apps/ -> root)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.yaml"
ENV_PREFIX = "CICIBYTE__"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping at the top level")
    return data


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(config)
    for env_key, raw_value in os.environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue
        path_parts = env_key[len(ENV_PREFIX):].lower().split("__")
        if not path_parts or not all(path_parts):
            continue
        node = config
        for part in path_parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ValueError(
                    f"Cannot override {env_key}: {'.'.join(path_parts[:-1])} is not a mapping"
                )
        node[path_parts[-1]] = _coerce(raw_value)
    return config


def _coerce(value: str) -> Any:
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


@lru_cache(maxsize=1)
def get_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load and cache the merged configuration (defaults + env overrides).

    Pass an explicit config_path (and call get_config.cache_clear() first)
    in tests that need a different base file.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    base = _load_yaml(path)
    return _apply_env_overrides(base)


def resolve_path(relative: str) -> Path:
    """Resolve a config path value (e.g. paths.logs) against the repo root."""
    p = Path(relative)
    return p if p.is_absolute() else (REPO_ROOT / p)
