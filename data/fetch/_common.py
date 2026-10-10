"""Shared helpers for data/fetch scripts: downloads that record their URL, and small-file writers."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
PROCESSED = REPO / "data" / "processed"
UA = {"User-Agent": "Mozilla/5.0 (HospitalGym research fetch; public data only)"}


def download(url: str, dest: pathlib.Path, force: bool = False, timeout: int = 300) -> pathlib.Path:
    """Download url to dest unless present. Appends a line to <dest.parent>/SOURCES.jsonl recording the URL."""
    dest = pathlib.Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    h = hashlib.sha256(dest.read_bytes()).hexdigest() if dest.stat().st_size < 500e6 else None
    rec = {"file": dest.name, "url": url, "bytes": dest.stat().st_size, "sha256": h,
           "fetched_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}
    with open(dest.parent / "SOURCES.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return dest


def write_json(obj, path: pathlib.Path) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=False) + "\n")
