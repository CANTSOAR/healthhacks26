"""Read YAML / JSON from disk with an mtime cache, so edits made overnight show up without a restart."""
from __future__ import annotations

import gzip
import json
import math
import threading
from pathlib import Path

import yaml

_lock = threading.Lock()
_cache: dict[str, tuple[tuple, object]] = {}


def _key(path: Path):
    st = path.stat()
    return (st.st_mtime_ns, st.st_size)


def load(path: Path | str, default=None):
    """Parsed content of a .yaml/.yml/.json/.json.gz file, or `default` when missing or unreadable."""
    path = Path(path)
    try:
        key = _key(path)
    except OSError:
        return default
    with _lock:
        hit = _cache.get(str(path))
        if hit and hit[0] == key:
            return hit[1]
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt") as f:
                data = json.load(f)
        elif path.suffix in (".yaml", ".yml"):
            with open(path) as f:
                data = yaml.safe_load(f)
        else:
            with open(path) as f:
                data = json.load(f)
    except Exception:  # noqa: BLE001 - a half-written file must not take a route down
        return default
    with _lock:
        _cache[str(path)] = (key, data)
    return data


def clean(o):
    """Make a structure strictly JSON-serialisable: tensors -> numbers, NaN/inf -> None."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, (str, int, bool)) or o is None:
        return o
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [clean(v) for v in o]
    if hasattr(o, "tolist"):
        return clean(o.tolist())
    if hasattr(o, "item"):
        return clean(o.item())
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def dumps(o) -> str:
    try:
        return json.dumps(o, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError):
        return json.dumps(clean(o), allow_nan=False, separators=(",", ":"))
