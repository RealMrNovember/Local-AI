"""Model provider abstraction (ARCHITECTURE.md Section 5.1).

The Agent Engine (Phase 3) and chat endpoint only ever talk to a
ModelProvider — never to a concrete backend (Ollama, llama.cpp, a cloud
API) directly. This keeps the model layer swappable without touching
callers, per the project's "no tight coupling" rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatChunk:
    content: str
    done: bool
    model: str | None = None
    error: str | None = None


class ModelProvider(Protocol):
    async def is_reachable(self) -> bool: ...

    async def list_installed(self) -> list[str]:
        """Return provider-native model identifiers currently available
        to run (e.g. Ollama tags already pulled)."""
        ...

    def chat(self, model: str, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]: ...

    def pull(self, model: str) -> AsyncIterator[dict]:
        """Download a model. Caller is responsible for checking the
        network policy gate before calling this — the provider itself
        does not know about CiciByte's network modes."""
        ...
