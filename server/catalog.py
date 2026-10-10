"""Catalog routes: summary, entity files, and catalog_ref resolution. Reads catalog/ per request (mtime cache)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import cache
from .paths import catalog_dir

SOURCES = ("measured", "literature", "assumed")
ORDER = ["patient", "staff", "space", "equipment", "event", "hospital", "condition", "interaction", "validation_target"]
DIR_ALIASES = {"hospital": "hospitals", "hospitals": "hospitals", "condition": "conditions", "conditions": "conditions"}


def _files() -> list[Path]:
    d = catalog_dir()
    return sorted(d.glob("*.yaml")) if d.exists() else []


def _dir_files(sub: str) -> list[Path]:
    d = catalog_dir() / sub
    return sorted(d.glob("*.yaml")) if d.exists() else []


def _count(attrs, by: dict) -> tuple[int, int]:
    n = nv = 0
    for a in (attrs or {}).values() if isinstance(attrs, dict) else []:
        if isinstance(a, dict) and a.get("source"):
            by[a["source"]] = by.get(a["source"], 0) + 1
            n += 1
            nv += 1 if a.get("validation_only") else 0
    return n, nv


def _summarise(docs: list[dict], entity_type: str) -> dict | None:
    docs = [d for d in docs if isinstance(d, dict)]
    if not docs:
        return None
    by = {s: 0 for s in SOURCES}
    n_var = n_attr = n_val = 0
    for doc in docs:
        a, v = _count(doc.get("shared"), by)
        n_attr, n_val = n_attr + a, n_val + v
        a, v = _count(doc.get("attributes"), by)
        n_attr, n_val = n_attr + a, n_val + v
        variants = doc.get("variants") if isinstance(doc.get("variants"), dict) else {}
        for var in variants.values():
            a, v = _count((var or {}).get("attributes"), by)
            n_attr, n_val = n_attr + a, n_val + v
        n_var += len(variants) if variants else (len(doc.get("declarations") or []) or 1)
    desc = docs[0].get("description", "") if len(docs) == 1 else f"{len(docs)} files. " + str(docs[0].get("description", ""))
    return dict(entity_type=entity_type, description=str(desc), n_variants=n_var, n_attributes=n_attr, by_source=by,
                n_validation_only=n_val, n_files=len(docs))


def summary() -> dict:
    groups: dict[str, list[dict]] = {}
    for f in _files():
        doc = cache.load(f)
        if isinstance(doc, dict):
            groups.setdefault(str(doc.get("entity_type") or f.stem), []).append(doc)
    for et, sub in (("hospital", "hospitals"), ("condition", "conditions")):
        for f in _dir_files(sub):
            doc = cache.load(f)
            if isinstance(doc, dict):
                groups.setdefault(et, []).append(doc)
    ets = [s for s in (_summarise(v, k) for k, v in groups.items()) if s]
    ets.sort(key=lambda e: (ORDER.index(e["entity_type"]) if e["entity_type"] in ORDER else 99, e["entity_type"]))
    totals = dict(n_entity_types=len(ets), n_variants=sum(e["n_variants"] for e in ets), n_attributes=sum(e["n_attributes"] for e in ets),
                  by_source={s: sum(e["by_source"].get(s, 0) for e in ets) for s in SOURCES},
                  n_validation_only=sum(e["n_validation_only"] for e in ets))
    return dict(entity_types=ets, totals=totals)


def _file_for(entity_type: str) -> Path | None:
    d = catalog_dir()
    for name in (entity_type, entity_type.rstrip("s")):
        p = d / f"{name}.yaml"
        if p.exists():
            return p
    for f in _files():
        doc = cache.load(f)
        if isinstance(doc, dict) and doc.get("entity_type") in (entity_type, entity_type.rstrip("s")):
            return f
    return None


def entity(entity_type: str):
    """The catalog file as JSON; `conditions` / `hospitals` -> {items: [...]}. None when unknown."""
    if entity_type in DIR_ALIASES:
        items = []
        for f in _dir_files(DIR_ALIASES[entity_type]):
            doc = cache.load(f)
            if isinstance(doc, dict):
                items.append(dict(doc, id=doc.get("id", f.stem), file=f"catalog/{DIR_ALIASES[entity_type]}/{f.name}"))
        return dict(items=items)
    f = _file_for(entity_type)
    doc = cache.load(f) if f else None
    return doc if isinstance(doc, dict) else None


def _resolved(doc: dict, entity_type: str, variant: str, file: str) -> dict | None:
    variants = doc.get("variants") if isinstance(doc.get("variants"), dict) else {}
    attrs = dict(doc.get("shared") or {}) if isinstance(doc.get("shared"), dict) else {}
    label = None
    if variant in variants:
        v = variants[variant] or {}
        attrs.update(v.get("attributes") or {})
        label = v.get("label")
    elif entity_type == "condition":
        # a condition template: one file per group; its own attributes (if any) plus those of its only variant
        attrs.update(doc.get("attributes") or {} if isinstance(doc.get("attributes"), dict) else {})
        if len(variants) == 1:
            v = next(iter(variants.values())) or {}
            attrs.update(v.get("attributes") or {})
            label = v.get("label")
        label = label or doc.get("label") or doc.get("title")
    else:
        return None
    attrs = {k: a for k, a in attrs.items() if isinstance(a, dict)}
    out = dict(entity_type=str(doc.get("entity_type") or entity_type), variant=variant, label=str(label or variant.replace("_", " ")),
               attributes=attrs, file=file)
    if doc.get("description"):
        out["description"] = doc["description"]
    return out


def resolve_ref(path: str) -> dict | None:
    """`space/treatment_bay`, `staff/rn`, `hospital/rwjuh_nb`, `conditions/chest_pain` -> resolved definition or None."""
    parts = [p for p in str(path).strip("/").split("/") if p]
    if len(parts) != 2 or any(p.startswith(".") for p in parts):
        return None
    et, variant = parts
    if et in DIR_ALIASES:
        sub = DIR_ALIASES[et]
        kind = "hospital" if sub == "hospitals" else "condition"
        files = _dir_files(sub)
        # the file named after the variant first, then any file that declares the variant
        files.sort(key=lambda f: f.stem != variant)
        for f in files:
            doc = cache.load(f)
            if not isinstance(doc, dict):
                continue
            has = variant in (doc.get("variants") or {}) if isinstance(doc.get("variants"), dict) else False
            if has or (kind == "condition" and f.stem == variant):
                return _resolved(doc, kind, variant, f"catalog/{sub}/{f.name}")
        return None
    f = _file_for(et)
    doc = cache.load(f) if f else None
    if not isinstance(doc, dict):
        return None
    return _resolved(doc, et, variant, f"catalog/{f.name}")


def resolve_many(refs) -> dict:
    out = {}
    for r in refs or []:
        if isinstance(r, str):
            d = resolve_ref(r)
            if d is not None:
                out[r] = d
    return out


def content_hash(extra: list[Path] | None = None) -> str:
    """Hash of every simulator input file in the catalog (validation targets excluded)."""
    h = hashlib.sha1()
    files = [f for f in _files() if f.stem != "validation_targets"] + _dir_files("hospitals") + _dir_files("conditions")
    d = catalog_dir() / "hospitals"
    files += sorted(d.glob("*.layout.json")) if d.exists() else []
    for f in files + list(extra or []):
        try:
            h.update(f.name.encode())
            h.update(f.read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:16]


def hospitals() -> list[dict]:
    d = catalog_dir() / "hospitals"
    out = []
    for f in sorted(d.glob("*.layout.json")) if d.exists() else []:
        lay = cache.load(f)
        if isinstance(lay, dict):
            hid = str(lay.get("hospital_id") or f.name[: -len(".layout.json")])
            out.append(dict(id=hid, name=str(lay.get("name", hid)), disclaimer=str(lay.get("disclaimer", ""))))
    out.sort(key=lambda h: (h["id"] != "rwjuh_nb", h["id"]))
    return out


def layout(hospital_id: str):
    d = catalog_dir() / "hospitals"
    if "/" in hospital_id or hospital_id.startswith("."):
        return None
    lay = cache.load(d / f"{hospital_id}.layout.json")
    if isinstance(lay, dict):
        return lay
    for f in sorted(d.glob("*.layout.json")) if d.exists() else []:
        lay = cache.load(f)
        if isinstance(lay, dict) and lay.get("hospital_id") == hospital_id:
            return lay
    if hospital_id == "fixture":
        from .paths import FIXTURES
        return cache.load(FIXTURES / "layout.fixture.json")
    return None
