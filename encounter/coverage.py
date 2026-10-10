"""Completeness check for cases drafted from a free-text description.

Every sentence of `review.source_description` must be reflected somewhere in the case (a fact, an artifact,
the profile or the title). The check is deliberately independent of how the draft was produced: it compares
the words and numbers of each sentence with the text of the finished case, so a silently dropped medicine,
allergy or lab value shows up here whatever the extractor did.

    coverage_report(case) -> {"sentences": n, "covered": k, "uncovered": [{"text": sentence, "missing_words": [...]}]}

It is a word-level check: it cannot tell whether a fact says the RIGHT thing about a word it contains.
"""
from __future__ import annotations

import json
import re

from . import taxonomy as tx

_IGNORE = set(
    "she he his her hers him they their them himself herself patient pt mr mrs ms miss dr year years yrs old yo aged age man woman male female boy girl "
    "gentleman lady child kid presents present presenting presented comes came come coming brought bring arrives arrived arriving complains complaining "
    "complaint complaints takes take taking taken prescribed uses use using used history known has had having have been being also because since after "
    "before but who whom which while when during with without over per about named called name says said states stated reports reported report tell told "
    "telling anyone anybody want wants wanted does doesnt did didnt hiding hides hide hidden conceals concealing mention mentions admit admits reluctant "
    "currently current recently past still now then both all only very quite some any the and for from into out off than that this these those there here "
    "are was were not nor yes its into onto upon etc regular regularly include includes including well other others each every per via ago time times "
    "pmh pmhx hx meds says say describes describe notes goes found given seen last one whom where give gives gave cause causes caused make makes rated rates rate scored out over works work working worked employed job level levels value values result results shows show showed found noted note on in at of to is it by as or an be am if so up".split()
)
_WORD = re.compile(r"[a-z][a-z'\-]*|\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?")
_ABBR = re.compile(r"(?:\b(?:mr|mrs|ms|dr|st|vs|approx|e\.g|i\.e|y\.o)|\b[a-z])\.$", re.I)


def split_sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) character spans of the sentences / semicolon clauses of a description."""
    t = text or ""
    out, start = [], 0
    for m in re.finditer(r"[.!?;]+(?=\s|$)|\n+", t):
        seg = t[start:m.end()]
        if m.group(0).startswith(".") and _ABBR.search(seg.rstrip()):
            continue
        if seg.strip(" .;!?\n\t"):
            out.append((start, m.end()))
        start = m.end()
    if t[start:].strip(" .;!?\n\t"):
        out.append((start, len(t)))
    return out


def _num(s: str) -> str:
    s = s.replace(" ", "")
    if "/" in s:
        return s
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else str(f)


def _tokens(text: str) -> tuple[dict[str, str], set[str]]:
    """({word stem: word as written}, numbers) of a text."""
    words, nums = {}, set()
    for m in _WORD.finditer((text or "").lower().replace("’", "'")):
        w = m.group(0)
        if w[0].isdigit():
            nums.add(_num(w))
            if "/" in w:
                nums |= {_num(p) for p in w.split("/")}
            continue
        for part in w.replace("'", "").split("-"):
            if len(part) >= 3 and part not in _IGNORE:
                words.setdefault(tx.stem(part), part)
    return words, nums


def _strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [str(obj)]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in _strings(v)]
    return []


def case_text(case: dict) -> str:
    """Everything in the case a sentence of the description could have ended up in (never the description itself)."""
    parts: list[str] = [str(case.get("title") or "")]
    parts += _strings(case.get("profile") or {})
    for f in case.get("facts") or []:
        if isinstance(f, dict):
            parts += _strings({k: f.get(k) for k in ("statement", "patient_answer", "cover_answer", "label", "value", "unit", "source_text")})
    for a in (case.get("chart") or {}).get("artifacts") or []:
        if isinstance(a, dict):
            parts += _strings({k: a.get(k) for k in ("title", "content")})
    ft = case.get("faculty_truth") or {}
    parts += _strings({k: ft.get(k) for k in ("diagnosis", "differential", "teaching_points", "severity_basis")})
    return "\n".join(parts)


def coverage_report(case: dict, source: str | None = None) -> dict:
    src = source if source is not None else ((case.get("review") or {}).get("source_description") or "")
    if not isinstance(src, str) or not src.strip():
        return {"sentences": 0, "covered": 0, "uncovered": []}
    have_w, have_n = _tokens(case_text(case))
    uncovered = []
    spans = split_sentences(src)
    for a, b in spans:
        sent = src[a:b].strip()
        w, n = _tokens(sent)
        miss = sorted(w[k] for k in set(w) - set(have_w)) + sorted(n - have_n)
        if miss:
            uncovered.append({"text": sent, "missing_words": miss})
    return {"sentences": len(spans), "covered": len(spans) - len(uncovered), "uncovered": uncovered}


def missing_words_text(item: dict) -> str:
    return json.dumps(item["text"], ensure_ascii=False) + " (not found in the draft: " + ", ".join(item["missing_words"][:8]) + ")"
