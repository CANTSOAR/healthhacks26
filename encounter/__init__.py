"""HospitalGym encounter engine: the played resolver for the clinician-patient interaction.

Case as data -> deterministic disclosure engine + event ledger -> patient role-play behind a provider
interface (Bedrock / Anthropic / offline) -> separate grader -> interaction-contract write-back.
"""
from __future__ import annotations

__all__ = ["status", "router"]


def status() -> dict:
    """Provider status for /api/status: {"llm": {live, provider, model, last_error?}, "voice": {live, provider}}."""
    from .providers import get_provider, voice_status
    return {"llm": get_provider().status(), "voice": voice_status()}


def __getattr__(name: str):
    if name == "router":
        from .api import router
        return router
    raise AttributeError(name)
