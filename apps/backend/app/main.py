from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_config, resolve_path
from .logging_config import configure_logging
from .routers import chat as chat_router
from .routers import config as config_router
from .routers import health as health_router
from .routers import models as models_router
from .routers import network as network_router

logger = logging.getLogger("cicibyte.backend")


def create_app() -> FastAPI:
    cfg = get_config()
    logging_cfg = cfg.get("logging", {})
    configure_logging(
        logs_dir=resolve_path(cfg["paths"]["logs"]),
        level=logging_cfg.get("level", "INFO"),
        json_file=logging_cfg.get("json_file", True),
        console=logging_cfg.get("console", True),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(
            "CiciByte AI backend starting",
            extra={"extra_fields": {"version": __version__, "network_mode": cfg.get("network", {}).get("mode")}},
        )
        yield
        logger.info("CiciByte AI backend stopped")

    app = FastAPI(
        title=cfg.get("app", {}).get("name", "CiciByte AI"),
        version=__version__,
        lifespan=lifespan,
    )

    # Local-only dev CORS: frontend dev server runs on a different port.
    # This never needs to be internet-facing — the UI and backend are both
    # local processes (ARCHITECTURE.md Section 1).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router.router)
    app.include_router(config_router.router)
    app.include_router(models_router.router)
    app.include_router(network_router.router)
    app.include_router(chat_router.router)

    return app


app = create_app()
