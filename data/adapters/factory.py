from __future__ import annotations

import os
from typing import Any

from .public_extracts import PublicExtracts
from .vlada import Vlada, VladaError


class _WithFallback:
    """Vlada first; on any failure serve that call from the public extracts and remember that it happened."""

    def __init__(self, online: Vlada, offline: PublicExtracts):
        self.online, self.offline = online, offline
        self.name = "vlada"
        self.fallbacks: list[dict] = []

    def list_tables(self) -> list[str]:
        return sorted(set(self.online.list_tables()) | set(self.offline.list_tables()))

    def get_table(self, name: str, **filters: Any) -> list[dict]:
        try:
            return self.online.get_table(name, **filters)
        except VladaError as e:
            self.fallbacks.append({"table": name, "reason": str(e)[:200]})
            return self.offline.get_table(name, **filters)

    def status(self) -> dict:
        s = self.online.status()
        s.update(fallback_calls=len(self.fallbacks), last_fallback=self.fallbacks[-1] if self.fallbacks else None)
        return s


def get_data_service(env: dict | None = None, **vlada_kwargs: Any):
    env = os.environ if env is None else env
    key = env.get("VLADA_API_KEY", "")
    if key:
        return _WithFallback(Vlada(api_key=key, **vlada_kwargs), PublicExtracts())
    return PublicExtracts()
