"""Standalone app for testing the encounter engine on its own:

    .venv/bin/python -m uvicorn encounter.app:app --port 8010

Serves the encounter router under /api plus a minimal /api/status. The main server (server/) mounts the
same router; this file is only a convenience.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import status as encounter_status
from .api import router

app = FastAPI(title="HospitalGym encounter engine", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")


@app.get("/api/status")
def status():
    s = encounter_status()
    return {"services": {"sim": {"live": False}, "llm": s["llm"], "voice": s["voice"]}, "version": app.version}
