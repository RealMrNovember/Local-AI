"""WebSocket chat endpoint.

Protocol (client -> server), one JSON message per turn:
  {"model": "<registry name>" | null, "task_type": "coding"|"reasoning"|"general"|null,
   "messages": [{"role": "user", "content": "..."}, ...]}

Server -> client, one JSON object per line for the duration of the turn:
  {"type": "chunk", "content": "...", "model": "<registry name>"}
  {"type": "done", "model": "<registry name>"}
  {"type": "error", "message": "..."}

If `model` is omitted, the Model Router (Phase 2 scope: rule-based only)
picks one from `task_type`, falling back to the registry's default model.
This endpoint does not persist conversation history — that's the Memory
Engine, Phase 7.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import get_config
from ..models.ollama_provider import OllamaProvider
from ..models.provider import ChatMessage
from ..models.router import pick_model
from ..models_registry import load_registry

logger = logging.getLogger("cicibyte.routers.chat")
router = APIRouter(tags=["chat"])


def _ollama_provider() -> OllamaProvider:
    cfg = get_config().get("models", {})
    return OllamaProvider(
        host=cfg.get("ollama_host", "http://127.0.0.1:11434"),
        timeout_s=cfg.get("request_timeout_s", 180),
    )


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    provider = _ollama_provider()
    try:
        while True:
            payload = await websocket.receive_json()
            raw_messages = payload.get("messages", [])
            if not raw_messages:
                await websocket.send_json({"type": "error", "message": "messages[] is required"})
                continue

            entry_name = payload.get("model")
            task_type = payload.get("task_type")

            entry = None
            if entry_name:
                entries = load_registry()
                entry = next((e for e in entries if e.name == entry_name), None)
                if entry is None:
                    await websocket.send_json(
                        {"type": "error", "message": f"Unknown model '{entry_name}' — not in registry"}
                    )
                    continue
            else:
                entry = pick_model(task_type=task_type, installed_only=False)
                if entry is None:
                    await websocket.send_json(
                        {"type": "error", "message": "No models registered. Check config/models.yaml"}
                    )
                    continue

            if not entry.ollama_tag:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": (
                            f"'{entry.name}' has no ollama_tag configured in config/models.yaml — "
                            "cannot run it via the Ollama provider yet."
                        ),
                    }
                )
                continue

            if not await provider.is_reachable():
                await websocket.send_json(
                    {"type": "error", "message": f"Ollama is not reachable at {provider.host}"}
                )
                continue

            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in raw_messages]

            async for chunk in provider.chat(entry.ollama_tag, messages):
                if chunk.error:
                    await websocket.send_json({"type": "error", "message": chunk.error})
                    break
                if chunk.content:
                    await websocket.send_json(
                        {"type": "chunk", "content": chunk.content, "model": entry.name}
                    )
                if chunk.done:
                    await websocket.send_json({"type": "done", "model": entry.name})
                    break
    except WebSocketDisconnect:
        logger.info("Chat websocket disconnected")
