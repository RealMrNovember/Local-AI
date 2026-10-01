"""OllamaProvider — talks to a local Ollama daemon over its REST API.

No part of this module assumes Ollama is reachable; every public method
fails soft (is_reachable() -> False / list_installed() -> []) so Phase 1's
offline-first guarantee holds even when Ollama isn't installed or running.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from .provider import ChatChunk, ChatMessage

logger = logging.getLogger("cicibyte.models.ollama")


class OllamaProvider:
    def __init__(self, host: str, timeout_s: float = 180.0) -> None:
        self.host = host.rstrip("/")
        self.timeout_s = timeout_s

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.host}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_installed(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.host}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return []
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    async def chat(self, model: str, messages: list[ChatMessage]) -> AsyncIterator[ChatChunk]:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                async with client.stream("POST", f"{self.host}/api/chat", json=payload) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield ChatChunk(content="", done=True, model=model, error=f"Ollama HTTP {resp.status_code}: {body.decode(errors='replace')[:300]}")
                        return
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if "error" in data:
                            yield ChatChunk(content="", done=True, model=model, error=str(data["error"]))
                            return
                        msg = data.get("message", {}) or {}
                        yield ChatChunk(content=msg.get("content", ""), done=bool(data.get("done")), model=model)
        except httpx.HTTPError as exc:
            yield ChatChunk(content="", done=True, model=model, error=f"Could not reach Ollama at {self.host}: {exc}")

    async def pull(self, model: str) -> AsyncIterator[dict[str, Any]]:
        payload = {"model": model, "stream": True}
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{self.host}/api/pull", json=payload) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield {"status": "error", "error": f"Ollama HTTP {resp.status_code}: {body.decode(errors='replace')[:300]}"}
                        return
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPError as exc:
            yield {"status": "error", "error": f"Could not reach Ollama at {self.host}: {exc}"}
