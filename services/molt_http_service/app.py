# Phase 8.1: Molt HTTP service — transport shell поверх shared-core.
from __future__ import annotations

from fastapi import FastAPI

from .routes import router

app = FastAPI(title="Molt HTTP Service", version="0.1.0")
app.include_router(router, tags=["molt"])
