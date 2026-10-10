"""File-backed case store with the draft -> approved -> published lifecycle.

Seed cases ship (tracked, published, read-only) in encounter/cases/. Everything created at run time
lives in <data_dir>/cases/ (gitignored). One JSON file per case version: <case_id>.v<N>.json.
Published versions are immutable; editing one creates a new draft version.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import taxonomy as tx
from .paths import SEED_CASES_DIR, data_dir
from .rubric import get_rubric
from .validate import PATIENT_VOICED, validate_case

_FILE = re.compile(r"^(?P<id>.+)\.v(?P<v>\d+)\.json$")
_LOCK = threading.RLock()


class CaseError(Exception):
    def __init__(self, message: str, status: int = 400, detail: dict | None = None):
        super().__init__(message)
        self.status = status
        self.detail = detail or {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str, fallback: str = "case") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:48] or fallback


# ------------------------------------------------------------------ authoring helpers

_THIRD_TO_FIRST = [
    (r"\b(he|she|they|the patient|patient|pt)\s+(is|was)\b", r"I \2"),
    (r"\b(he|she|the patient|patient|pt)\s+has\b", "I have"),
    (r"\b(he|she|the patient|patient|pt)\s+does not\b", "I do not"),
    (r"\b(he|she|the patient|patient|pt)\s+doesn['’]?t\b", "I don't"),
    (r"\bhis\b|\bher\b(?=\s+[a-z])", "my"),
    (r"\bhimself\b|\bherself\b", "myself"),
    (r"\bhim\b", "me"),
]
_VERB_3RD = {
    "smokes": "smoke", "drinks": "drink", "consumes": "have", "uses": "use", "takes": "take",
    "lives": "live", "works": "work", "denies": "do not have", "reports": "have", "has": "have", "is": "am",
    "was": "was", "struggles": "struggle", "avoids": "avoid", "dislikes": "dislike", "needs": "need", "walks": "walk",
    "plays": "play", "eats": "eat", "feels": "feel", "loves": "love", "mistrusts": "do not really trust",
    "expresses": "have", "presents": "came in", "challenges": "tend to push back on", "moved": "moved", "lost": "lost",
    "sleeps": "sleep", "exercises": "exercise", "vapes": "vape", "wants": "want", "worries": "worry", "misses": "miss",
    "skips": "skip", "stopped": "stopped", "noticed": "noticed", "had": "had", "developed": "developed", "fell": "fell",
    "experiences": "get", "complains": "have been bothered", "endorses": "have", "admits": "do",
}


def to_first_person(statement: str) -> str:
    """Best-effort rewrite of a third-person clinical statement into something a patient could say.
    Used only to DRAFT patient_answer wording for faculty review (flagged patient_answer_auto)."""
    s = (statement or "").strip().rstrip(".")
    if not s:
        return ""
    out = s
    for pat, rep in _THIRD_TO_FIRST:
        out = re.sub(pat, rep, out, flags=re.I)
    words = out.split()
    first = words[0].lower() if words else ""
    if first in _VERB_3RD:
        out = "I " + _VERB_3RD[first] + " " + " ".join(words[1:])
    elif re.match(r"^(he|she|they)\s+(\w+)", out, flags=re.I):
        m = re.match(r"^(he|she|they)\s+(\w+)(.*)$", out, flags=re.I | re.S)
        verb = _VERB_3RD.get(m.group(2).lower(), re.sub(r"s$", "", m.group(2)) if m.group(2).lower().endswith("s") and not m.group(2).lower().endswith("ss") else m.group(2))
        out = f"I {verb}{m.group(3)}"
    elif re.match(r"^(no|denies|without)\b", out, flags=re.I):
        out = "No, " + re.sub(r"^(no|denies|without)\s+", "no ", out, flags=re.I)
    elif not re.match(r"^(i|my|yes|no)\b", out, flags=re.I):
        out = "From what I know: " + out[0].lower() + out[1:]
    out = re.sub(r"\s+", " ", out).strip()
    return out[0].upper() + out[1:] + "."


def fill_defaults(case: dict) -> dict:
    """Make a partial case body structurally complete (drafts only). Never touches clinical values."""
    c = copy.deepcopy(case) if isinstance(case, dict) else {}
    c.setdefault("schema_version", 1)
    c.setdefault("title", (c.get("profile") or {}).get("name") or "Untitled case")
    c.setdefault("origin", {"kind": "authored"})
    prof = c.setdefault("profile", {})
    prof.setdefault("name", "Unnamed patient")
    prof.setdefault("age", 40)
    prof.setdefault("gender", "unspecified")
    rev = c.setdefault("review", {})
    rev.setdefault("needs_faculty_review", True)
    rev["synthetic"] = True
    c.setdefault("facts", [])
    chart = c.setdefault("chart", {})
    chart.setdefault("sections", [])
    chart.setdefault("artifacts", [])
    c.setdefault("objectives", [])
    c.setdefault("rubric_id", "default")
    c.setdefault("sources", [])
    c.setdefault("unknown_response", "I'm not sure. I can't really tell you anything about that.")
    seen = set()
    for i, f in enumerate(c["facts"]):
        if not isinstance(f, dict):
            continue
        f.setdefault("category", "hpi")
        if not f.get("fact_id"):
            base = slugify(f.get("label") or f.get("statement") or f"fact {i + 1}", "fact").replace("-", "_")[:32]
            f["fact_id"] = f"f.{f['category']}.{base}"
        if f["fact_id"] in seen:
            pass  # validator reports duplicates
        seen.add(f["fact_id"])
        f.setdefault("statement", "")
        disc = f.get("disclosure") if isinstance(f.get("disclosure"), dict) else None
        if disc is None:
            rule = "chart_initial" if f["category"] in ("vitals",) else ("on_request" if f["category"] in ("lab", "imaging", "exam") else "if_asked")
            disc = f["disclosure"] = {"rule": rule}
        if "patient_knows" not in f:
            f["patient_knows"] = disc.get("rule") in PATIENT_VOICED
        if f["patient_knows"] and disc.get("rule") in PATIENT_VOICED and not (f.get("patient_answer") or "").strip() and f.get("statement"):
            f["patient_answer"] = to_first_person(f["statement"])
            f["patient_answer_auto"] = True
        if not f.get("chart_section"):
            f["chart_section"] = tx.CATEGORY_SECTION.get(f["category"], ("hpi", ""))[0]
    # make sure every section a fact or artifact uses exists
    have = {s.get("section_id") for s in chart["sections"] if isinstance(s, dict)}
    titles = {sid: title for sid, title in tx.CATEGORY_SECTION.values()}
    used = [f.get("chart_section") for f in c["facts"] if isinstance(f, dict)] + \
           [a.get("section_id") for a in chart["artifacts"] if isinstance(a, dict)]
    for sid in used:
        if sid and sid not in have:
            initial = any(isinstance(f, dict) and f.get("chart_section") == sid and (f.get("disclosure") or {}).get("rule") == "chart_initial" for f in c["facts"])
            chart["sections"].append({"section_id": sid, "title": titles.get(sid, sid.replace("_", " ").title()),
                                      "release": "initial" if initial else "on_fact"})
            have.add(sid)
    for a in chart["artifacts"]:
        if isinstance(a, dict):
            a.setdefault("release", {"rule": "on_request", "request": f"artifact:{a.get('artifact_id')}"})
            a.setdefault("synthetic", True)
    for i, o in enumerate(c["objectives"]):
        if isinstance(o, dict) and not o.get("objective_id"):
            o["objective_id"] = "obj." + slugify(o.get("criterion") or f"objective {i + 1}").replace("-", "_")[:40]
    return c


class CaseStore:
    def __init__(self, data: Path | None = None, seed: Path | None = None):
        self._data = Path(data) if data else None
        self.seed_dir = Path(seed) if seed else SEED_CASES_DIR

    @property
    def cases_dir(self) -> Path:
        d = (self._data or data_dir()) / "cases"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- reading
    def _files(self) -> dict[tuple[str, int], Path]:
        out: dict[tuple[str, int], Path] = {}
        for d in (self.seed_dir, self.cases_dir):       # run-time files win on a clash
            if not d.is_dir():
                continue
            for p in d.glob("*.json"):
                m = _FILE.match(p.name)
                if m:
                    out[(m.group("id"), int(m.group("v")))] = p
        return out

    def _ids(self) -> set[str]:
        return {cid for cid, _ in self._files()}

    def versions(self, case_id: str) -> list[int]:
        return sorted(v for (cid, v) in self._files() if cid == case_id)

    def get(self, case_id: str, version: int | None = None, status: str | None = None) -> dict:
        files = self._files()
        vs = sorted(v for (cid, v) in files if cid == case_id)
        if not vs:
            raise CaseError(f"case '{case_id}' not found", 404)
        if version is not None:
            if version not in vs:
                raise CaseError(f"case '{case_id}' has no version {version}", 404)
            return self._read(files[(case_id, version)])
        for v in reversed(vs):
            c = self._read(files[(case_id, v)])
            if status is None or c.get("status") == status:
                return c
        raise CaseError(f"case '{case_id}' has no {status} version", 409)

    def _read(self, path: Path) -> dict:
        c = json.loads(path.read_text())
        c.setdefault("updated", datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"))
        c["_seed"] = path.parent == self.seed_dir
        return c

    def list(self, status: str | None = None, all_versions: bool = False) -> list[dict]:
        files = self._files()
        by_case: dict[str, list[int]] = {}
        for cid, v in files:
            by_case.setdefault(cid, []).append(v)
        out = []
        for cid, vs in sorted(by_case.items()):
            chosen = []
            for v in sorted(vs, reverse=True):
                c = self._read(files[(cid, v)])
                if status and c.get("status") != status:
                    continue
                chosen.append(c)
                if not all_versions:
                    break
            for c in chosen:
                out.append(self.summary(c, sorted(vs)))
        return out

    @staticmethod
    def summary(c: dict, versions: list[int] | None = None) -> dict:
        p = c.get("profile") or {}
        return {"case_id": c.get("case_id"), "version": c.get("version"), "status": c.get("status"), "title": c.get("title"),
                "origin": c.get("origin"), "profile": {"name": p.get("name"), "age": p.get("age"), "gender": p.get("gender")},
                "updated": c.get("updated"), "versions": versions or [c.get("version")], "seed": bool(c.get("_seed")),
                "n_facts": len(c.get("facts") or []), "n_objectives": len(c.get("objectives") or []),
                "needs_faculty_review": bool((c.get("review") or {}).get("needs_faculty_review")),
                "setting": c.get("setting"), "learner_role": c.get("learner_role")}

    # ---- writing
    def _write(self, case: dict) -> dict:
        c = {k: v for k, v in case.items() if not k.startswith("_")}
        path = self.cases_dir / f"{c['case_id']}.v{c['version']}.json"
        with _LOCK:
            existing = self._files().get((c["case_id"], c["version"]))
            if existing is not None:
                old = json.loads(existing.read_text())
                if old.get("status") == "published":
                    raise CaseError(f"{c['case_id']} v{c['version']} is published and immutable", 409)
                if existing.parent == self.seed_dir:
                    raise CaseError("seed cases are read-only", 409)
            c["updated"] = now_iso()
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(c, indent=2, ensure_ascii=False))
            tmp.replace(path)
        return self._read(path)

    def create(self, body: dict, case_id: str | None = None) -> dict:
        c = fill_defaults(body)
        cid = case_id or c.get("case_id")
        with _LOCK:
            if not cid or self.versions(cid):
                base = slugify(cid or c.get("title") or c["profile"]["name"])
                digest = hashlib.sha1(f"{base}{now_iso()}{len(self._files())}".encode()).hexdigest()[:6]
                cid = f"{base}-{digest}"
            c["case_id"] = cid
            c["version"] = 1
            c["status"] = "draft"
            return self._write(c)

    def update(self, case_id: str, body: dict) -> dict:
        with _LOCK:
            cur = self.get(case_id)
            merged = {k: v for k, v in cur.items() if not k.startswith("_")}
            for k, v in (body or {}).items():
                if k in ("case_id", "version", "status", "updated") or k.startswith("_"):
                    continue
                merged[k] = v
            merged = fill_defaults(merged)
            merged["case_id"] = case_id
            if cur.get("status") == "published":
                merged["version"] = max(self.versions(case_id)) + 1
                rev = dict(merged.get("review") or {})
                rev.pop("reviewer", None)
                rev.pop("reviewed_at", None)
                rev["synthetic"] = True
                merged["review"] = rev
            else:
                merged["version"] = cur["version"]
            merged["status"] = "draft"      # any edit returns the version to draft
            return self._write(merged)

    def validate(self, case_id: str, version: int | None = None) -> dict:
        c = self.get(case_id, version)
        return validate_case({k: v for k, v in c.items() if not k.startswith("_") and k != "updated"}, get_rubric(c.get("rubric_id")))

    def approve(self, case_id: str, reviewer: str | None = None, acknowledge_warnings: bool | None = None) -> dict:
        """Approval needs zero errors and contradictions. `acknowledge_warnings`: None (default) approves and records
        that 'attention' warnings were not explicitly acknowledged; False refuses (409) while such warnings exist;
        True records the acknowledgement."""
        with _LOCK:
            c = self.get(case_id)
            if c.get("status") == "published":
                raise CaseError("the latest version is already published; edit it to start a new draft", 409)
            report = self.validate(case_id, c["version"])
            if not report["ok"]:
                raise CaseError("case does not validate; fix errors and contradictions before approval", 422, report)
            attention = [w for w in report["warnings"] if w.get("level") == "attention"]
            if attention and acknowledge_warnings is False:
                raise CaseError("this case has warnings that need acknowledgement; resend with acknowledge_warnings: true", 409,
                                {"needs_acknowledgement": True, "warnings": attention})
            c["status"] = "approved"
            rev = dict(c.get("review") or {})
            rev["reviewer"] = reviewer or rev.get("reviewer") or "faculty"
            rev["reviewed_at"] = now_iso()
            rev["synthetic"] = True
            rev["warnings_at_approval"] = [w["message"] for w in attention]
            rev["warnings_acknowledged"] = bool(acknowledge_warnings) if attention else True
            c["review"] = rev
            return self._write(c)

    def publish(self, case_id: str) -> dict:
        with _LOCK:
            c = self.get(case_id)
            if c.get("status") == "published":
                raise CaseError("the latest version is already published", 409)
            if c.get("status") != "approved":
                raise CaseError("only an approved version can be published (draft -> approved -> published)", 409)
            report = self.validate(case_id, c["version"])
            if not report["ok"]:
                raise CaseError("case does not validate", 422, report)
            c["status"] = "published"
            return self._write(c)

    def save_published(self, case: dict) -> dict:
        """Store a machine-instantiated case (from a simulated patient or a sample profile) as a published
        version so an encounter can start on it. It stays flagged needs_faculty_review."""
        c = fill_defaults(case)
        with _LOCK:
            vs = self.versions(c["case_id"])
            if vs:
                latest = self.get(c["case_id"])
                same = {k: v for k, v in latest.items() if k not in ("updated", "version", "status") and not k.startswith("_")} == \
                       {k: v for k, v in c.items() if k not in ("updated", "version", "status") and not k.startswith("_")}
                if same and latest.get("status") == "published":
                    return latest
                c["version"] = max(vs) + 1
            else:
                c["version"] = c.get("version") or 1
            c["status"] = "published"
            return self._write(c)


_default: CaseStore | None = None


def default_store() -> CaseStore:
    global _default
    if _default is None:
        _default = CaseStore()
    return _default
