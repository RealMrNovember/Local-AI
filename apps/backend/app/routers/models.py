from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import get_config
from ..models.ollama_provider import OllamaProvider
from ..models_registry import load_registry, merge_ollama_status
from ..runtime_state import get_network_mode

logger = logging.getLogger("cicibyte.routers.models")
router = APIRouter(prefix="/api/models", tags=["models"])


def _ollama_provider() -> OllamaProvider:
    cfg = get_config().get("models", {})
    return OllamaProvider(
        host=cfg.get("ollama_host", "http://127.0.0.1:11434"),
        timeout_s=cfg.get("request_timeout_s", 180),
    )


@router.get("/registry")
async def get_model_registry() -> dict:
    entries = load_registry()
    provider = _ollama_provider()
    ollama_reachable = await provider.is_reachable()
    if ollama_reachable:
        installed_tags = await provider.list_installed()
        entries = merge_ollama_status(entries, installed_tags)
    return {
        "models": [e.to_dict() for e in entries],
        "ollama_reachable": ollama_reachable,
    }


@router.get("/ollama/status")
async def ollama_status() -> dict:
    provider = _ollama_provider()
    reachable = await provider.is_reachable()
    installed = await provider.list_installed() if reachable else []
    return {"reachable": reachable, "host": provider.host, "installed_tags": installed}


class PullRequest(BaseModel):
    ollama_tag: str


@router.post("/pull")
async def pull_model(body: PullRequest):
    mode = get_network_mode()
    if mode == "offline":
        raise HTTPException(
            status_code=409,
            detail=(
                "Network mode is 'offline' — model downloads are blocked. "
                "Switch to 'lan' or 'internet' via PUT /api/network/mode first."
            ),
        )

    provider = _ollama_provider()
    if not await provider.is_reachable():
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is not reachable at {provider.host}. Is it installed and running?",
        )

    logger.info(
        "Model pull started",
        extra={"extra_fields": {"ollama_tag": body.ollama_tag, "network_mode": mode}},
    )

    async def stream():
        async for event in provider.pull(body.ollama_tag):
            yield json.dumps(event) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
