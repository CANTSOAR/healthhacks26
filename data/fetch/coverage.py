"""Count catalog attributes by source tag (measured / literature / assumed) per catalog file -> data/processed/catalog_coverage.json.
Run: .venv/bin/python data/fetch/coverage.py"""
import collections
import datetime
import pathlib

import yaml

from _common import PROCESSED, REPO, write_json

FILES = ["patient", "staff", "space", "equipment", "event", "hospitals/rwjuh_nb", "validation_targets"]


def attrs(doc):
    for k, a in (doc.get("shared") or {}).items():
        yield "shared", k, a
    for v, body in (doc.get("variants") or {}).items():
        for k, a in (body.get("attributes") or {}).items():
            yield v, k, a


def main():
    out = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "files": {}, "measured_or_literature_attributes": {}}
    total = collections.Counter()
    for f in FILES:
        p = REPO / "catalog" / f"{f}.yaml"
        if not p.exists():
            continue
        c = collections.Counter(); names = []
        for v, k, a in attrs(yaml.safe_load(p.read_text())):
            c[a.get("source", "missing")] += 1
            if a.get("source") in ("measured", "literature"):
                names.append(f"{v}.{k} [{a['source']}]")
        n = sum(c.values())
        out["files"][f"catalog/{f}.yaml"] = {"attributes": n, **{s: c.get(s, 0) for s in ("measured", "literature", "assumed")},
                                             "measured_share": round(c.get("measured", 0) / n, 3) if n else None}
        out["measured_or_literature_attributes"][f"catalog/{f}.yaml"] = names
        if f != "validation_targets":
            total.update(c)
    n = sum(total.values())
    out["total_excluding_validation_targets"] = {"attributes": n, **{s: total.get(s, 0) for s in ("measured", "literature", "assumed")},
                                                 "measured_share": round(total.get("measured", 0) / n, 3)}
    write_json(out, PROCESSED / "catalog_coverage.json")
    for k, v in out["files"].items():
        print(k, v)
    print("TOTAL", out["total_excluding_validation_targets"])


if __name__ == "__main__":
    main()
