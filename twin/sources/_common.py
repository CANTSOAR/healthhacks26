"""Shared helpers for twin/sources: recorded downloads, atomic writers, CMS Provider Data Catalog lookups.

Raw downloads go under data/raw/ (gitignored; override the directory with the environment variable TWIN_RAW).
Tracked extracts go to data/processed/hospitals/<ccn>/<source>.json and always carry a `source` block with the
URL, release / vintage, fetch time, sha256 of the raw file and the exact filter that produced the extract.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import tempfile
import time
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
RAW = pathlib.Path(os.environ.get("TWIN_RAW") or REPO / "data" / "raw")
PROCESSED = REPO / "data" / "processed"
HOSPITALS = PROCESSED / "hospitals"
UA = {"User-Agent": "Mozilla/5.0 (HospitalGym research fetch; public data only)"}
PDC_META = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{}"
PDC_LANDING = "https://data.cms.gov/provider-data/dataset/{}"


class SourceUnavailable(RuntimeError):
    """Raised by a source module when its public dataset cannot be reached or has no row for the hospital."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def norm_ccn(ccn) -> str:
    return str(ccn).strip().zfill(6)


def out_dir(ccn) -> pathlib.Path:
    d = HOSPITALS / norm_ccn(ccn)
    d.mkdir(parents=True, exist_ok=True)
    return d


def rel(path) -> str:
    try:
        return str(pathlib.Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def atomic_write_text(path, text: str) -> None:
    """Write through a temporary file in the same directory and rename (other processes read these files)."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def write_json(obj, path, compact: bool = False) -> None:
    txt = json.dumps(obj, separators=(",", ":")) if compact else json.dumps(obj, indent=1)
    atomic_write_text(path, txt + "\n")


def read_extract(ccn, source: str):
    p = HOSPITALS / norm_ccn(ccn) / f"{source}.json"
    return json.loads(p.read_text()) if p.exists() else None


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def http_get(url: str, timeout: int = 120, data: bytes | None = None, headers: dict | None = None, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - the caller turns this into SourceUnavailable
            last = e
            time.sleep(2 * (i + 1))
    raise SourceUnavailable(f"{url}: {type(last).__name__}: {last}")


def http_json(url: str, **kw):
    return json.loads(http_get(url, **kw))


def download(url: str, dest, force: bool = False, timeout: int = 3600) -> dict:
    """Download url to dest unless present; returns the sidecar record {file, url, bytes, sha256, fetched_utc}.

    The record lives next to the file as <name>.meta.json. A file that is present without a record (fetched with
    curl) gets one from its modification time and the url given here.
    """
    dest = pathlib.Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    side = dest.with_name(dest.name + ".meta.json")
    if dest.exists() and dest.stat().st_size > 0 and not force:
        if side.exists():
            return json.loads(side.read_text())
        rec = {"file": dest.name, "url": url, "bytes": dest.stat().st_size, "sha256": sha256_file(dest),
               "fetched_utc": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).isoformat(timespec="seconds")}
        write_json(rec, side)
        return rec
    tmp = dest.with_name(dest.name + ".part")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise SourceUnavailable(f"{url}: {type(e).__name__}: {e}") from e
    os.replace(tmp, dest)
    rec = {"file": dest.name, "url": url, "bytes": dest.stat().st_size, "sha256": sha256_file(dest), "fetched_utc": now()}
    write_json(rec, side)
    return rec


def pdc_dataset(dataset_id: str, force: bool = False) -> tuple[pathlib.Path, dict]:
    """Resolve a CMS Provider Data Catalog dataset to its current CSV, download it, return (path, source block)."""
    d = RAW / "pdc" / dataset_id
    cache = d / "resolved.json"
    meta = None
    if cache.exists() and not force:
        meta = json.loads(cache.read_text())
    else:
        try:
            m = http_json(PDC_META.format(dataset_id), timeout=60)
            meta = {"title": m["title"], "modified": m.get("modified"), "released": m.get("released"),
                    "url": m["distribution"][0]["downloadURL"]}
            d.mkdir(parents=True, exist_ok=True)
            write_json(meta, cache)
        except SourceUnavailable:
            have = sorted(d.glob("*.csv")) if d.exists() else []
            if not have:
                raise
            meta = {"title": dataset_id, "modified": None, "released": None, "url": None}
    name = urllib.parse.unquote(meta["url"].rsplit("/", 1)[1]) if meta.get("url") else sorted(d.glob("*.csv"))[0].name
    rec = download(meta["url"], d / name, force=force)
    src = {"dataset": f"CMS Provider Data Catalog: {meta['title']}", "dataset_id": dataset_id, "release": meta.get("released"),
           "modified": meta.get("modified"), "url": rec["url"], "landing": PDC_LANDING.format(dataset_id),
           "raw_file": f"data/raw/pdc/{dataset_id}/{name}", "bytes": rec["bytes"], "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"]}
    return d / name, src


def clean(v):
    """JSON-safe scalar from a pandas / numpy cell."""
    try:
        import pandas as pd
        if v is None or (not isinstance(v, (list, dict, str)) and pd.isna(v)):
            return None
    except Exception:  # noqa: BLE001
        pass
    if hasattr(v, "item"):
        v = v.item()
    return v
