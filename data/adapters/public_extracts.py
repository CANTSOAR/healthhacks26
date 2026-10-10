"""Offline implementation: reads the small tracked extracts in data/processed/ (CSV or JSON). No network."""
from __future__ import annotations

import csv
import json
import pathlib
from typing import Any

from .base import TableNotFound

PROCESSED = pathlib.Path(__file__).resolve().parents[1] / "processed"


def _coerce(v: str) -> Any:
    if v == "":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in v and "e" not in v.lower() else f
    except ValueError:
        return v


class PublicExtracts:
    name = "public_extracts"

    def __init__(self, root: pathlib.Path | str = PROCESSED):
        self.root = pathlib.Path(root)

    def list_tables(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*") if p.suffix in (".csv", ".json"))

    def get_table(self, name: str, **filters: Any) -> list[dict]:
        for suffix in (".csv", ".json"):
            p = self.root / f"{name}{suffix}"
            if p.exists():
                break
        else:
            raise TableNotFound(name)
        if p.suffix == ".csv":
            with open(p, newline="") as f:
                rows = [{k: _coerce(v) for k, v in r.items()} for r in csv.DictReader(f)]
        else:
            data = json.loads(p.read_text())
            rows = data if isinstance(data, list) else [data]
        return [r for r in rows if all(str(r.get(k)) == str(v) for k, v in filters.items())]

    def status(self) -> dict:
        return {"service": self.name, "online": False, "tables": len(self.list_tables())}
