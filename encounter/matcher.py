"""Offline intent step: which fact IDs / requests / conversational cues does a learner message touch?

Deterministic topic, keyword and fuzzy matching over each fact's `topics` (taxonomy keys expand to
shared synonym lists), the fact ID slug and the fact's category. It only PROPOSES; the disclosure
engine decides what is released.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from rapidfuzz import fuzz

from . import taxonomy as tx

MAX_FACTS_PER_TURN = 4


@dataclass
class Intent:
    fact_scores: dict[str, float] = field(default_factory=dict)   # fact_id -> score (all candidates)
    fact_ids: list[str] = field(default_factory=list)             # selected, best first
    via: dict[str, str] = field(default_factory=dict)             # fact_id -> phrase that matched
    requests: list[str] = field(default_factory=list)             # canonical request strings found in free text
    cues: dict[str, list[str]] = field(default_factory=dict)      # rapport / structure cues -> matched phrases
    is_question: bool = False
    is_open_question: bool = False
    source: str = "offline"


@lru_cache(maxsize=4096)
def _ptoks(phrase: str) -> tuple[str, ...]:
    return tuple(tx.tokens(phrase))


def _content_weight(ptoks: tuple[str, ...]) -> float:
    c = sum(1 for t in ptoks if t not in tx.STOPWORDS)
    return c + 0.5 * (len(ptoks) - c)


def _fuzzy_word(word: str, text_toks: list[str]) -> bool:
    if len(word) < 6:
        return False
    return any(len(t) >= 5 and abs(len(t) - len(word)) <= 2 and fuzz.ratio(word, t) >= 86 for t in text_toks)


def _match_phrase(text_toks: list[str], phrase: str) -> float:
    pt = _ptoks(phrase)
    if not pt:
        return 0.0
    if tx.contains_phrase(text_toks, list(pt)):
        return _content_weight(pt)
    if len(pt) == 1 and _fuzzy_word(pt[0], text_toks):
        return 0.8 * _content_weight(pt)
    return 0.0


DIMENSION_KEYS = {"onset", "duration", "character", "location", "severity", "radiation", "aggravating", "relieving"}


def fact_phrases(fact: dict) -> list[tuple[str, float, str]]:
    """(phrase, weight, topic key) triples that count as asking about this fact."""
    return list(_fact_phrases_cached(str(fact.get("fact_id", "")), str(fact.get("category", "")),
                                     tuple(str(t) for t in fact.get("topics") or [])))


@lru_cache(maxsize=4096)
def _fact_phrases_cached(fact_id: str, category: str, topics: tuple[str, ...]) -> tuple[tuple[str, float, str], ...]:
    fact = {"fact_id": fact_id, "category": category, "topics": list(topics)}
    out: list[tuple[str, float, str]] = []
    seen = set()
    cur = [""]

    def add(p: str, w: float):
        p = tx.normalize(p)
        if p and p not in seen:
            seen.add(p)
            out.append((p, w, cur[0]))

    for t in fact.get("topics") or []:
        key = str(t).strip().lower().replace(" ", "_")
        if key in tx.TOPICS:
            cur[0] = key
            for p in tx.TOPICS[key]:
                add(p, 2.0)
            add(key.replace("_", " "), 2.0)
        else:
            cur[0] = "authored"
            add(str(t), 3.0)          # authored trigger phrase: most specific
    # the fact id slug (f.social.smoking -> "smoking") and, when it names a taxonomy key, that key's phrases
    parts = str(fact.get("fact_id", "")).split(".")
    slug = parts[-1] if len(parts) >= 2 else ""
    cur[0] = "slug"
    if slug:
        if slug in tx.TOPICS:
            cur[0] = slug
            for p in tx.TOPICS[slug]:
                add(p, 1.6)
        words = [w for w in slug.split("_") if len(w) > 2 and w not in tx.STOPWORDS]
        if words:
            add(" ".join(words), 1.6)
            for w in words:
                if w in tx.TOPICS:
                    for p in tx.TOPICS[w]:
                        add(p, 1.3)
    for key in tx.CATEGORY_TOPICS.get(fact.get("category", ""), []):
        cur[0] = "category:" + key
        for p in tx.TOPICS.get(key, []):
            add(p, 1.0)
    return tuple(out)


_Q_START = re.compile(
    r"^(do|does|did|are|is|was|were|have|has|had|can|could|would|will|what|when|where|who|why|how|which|any|tell|describe|"
    r"walk|explain|show|and|so|ever|been|whats|hows|wheres|whens)\b")


def detect_cues(text: str) -> dict[str, list[str]]:
    norm = tx.normalize(text)
    cues = {}
    for name, phrases in (
        ("introduction", tx.INTRODUCTION), ("agenda", tx.AGENDA), ("empathy", tx.EMPATHY),
        ("normalising", tx.NORMALISING), ("judgmental", tx.JUDGMENTAL), ("summarising", tx.SUMMARISING),
        ("closing", tx.CLOSING), ("explaining", tx.EXPLAINING), ("open_question", tx.OPEN_QUESTION),
        ("confront", tx.CONFRONT_CUES),
    ):
        hits = tx.phrase_in(norm, phrases)
        if hits:
            cues[name] = hits
    padded = f" {norm} "
    jargon = [j.strip() for j in tx.JARGON if f" {j.strip()} " in padded]
    if jargon:
        cues["jargon"] = jargon
    return cues


_ALLERGY_TO_MEDS = re.compile(r"allerg\w*\s+(?:to|with)\s+(?:any\s+|your\s+|some\s+)?(?:med|drug|pill|antibiotic|tablet)|(?:med\w*|drug|medicine)\s+allerg")
_ABOUT_PATIENT = re.compile(r"^(and |so |ok |okay )?(do|did|have|has|had|are|were|was|is|does|when|why|how|what|who) (you|your|they|he|she|it|the|that|this|anyone|any)\b")
_FIRST_PERSON = re.compile(r"\b(i|id|ill|im|ive|we|well|lets|let|were)\b")
_IMPERATIVE = re.compile(r"^(please )?(order|get|send|run|check|obtain|request|perform|draw|do|examine|repeat|pull|review|show)\b")


def match_requests(text: str, case_requests: list[str], require_verb: bool = True) -> list[str]:
    """Requests named in free text. `case_requests` are the case's own request strings (always preferred)."""
    norm = tx.normalize(text)
    toks = tx.tokens(norm)
    if require_verb:
        # only the clinician acting ("can I get an ECG", "let me listen to your chest", "order a troponin"),
        # never a question about the patient ("do you check your blood sugar?")
        if _ABOUT_PATIENT.match(norm):
            return []
        if not (_FIRST_PERSON.search(norm) or _IMPERATIVE.match(norm)):
            return []
        if not tx.phrase_in(norm, tx.REQUEST_VERBS):
            return []
    found: list[tuple[float, str]] = []
    candidates: dict[str, list[str]] = {k: list(v) for k, v in tx.REQUEST_ALIASES.items()}
    for r in case_requests:
        slug = r.split(":", 1)[-1].replace("_", " ")
        candidates.setdefault(r, []).append(slug)
    for req, aliases in candidates.items():
        best = 0.0
        for a in aliases:
            best = max(best, _match_phrase(toks, a))
        if best > 0:
            found.append((best, req))
    found.sort(reverse=True)
    out = []
    for _, r in found:
        # "order:xray" is a generic alias: drop it when a more specific x-ray/ct request also matched
        if r == "order:xray" and any(o != r and ("xray" in o or "x_ray" in o) for _, o in found):
            continue
        if r not in out:
            out.append(r)
    return out[:3]


def canonical_request(raw: str, case_requests: list[str]) -> str:
    """Normalise a request string from the API ('Order: Trop', 'exam:belly') to a canonical key."""
    s = (raw or "").strip().lower()
    kind, _, name = s.partition(":")
    if not name:
        kind, name = "", s
    kind = kind.strip()
    name = name.strip().replace(" ", "_").replace("-", "_")
    direct = f"{kind}:{name}" if kind else name
    known = set(case_requests) | set(tx.REQUEST_ALIASES)
    if direct in known:
        return direct
    if kind == "artifact":
        return direct
    hits = match_requests(name.replace("_", " "), case_requests, require_verb=False)
    if kind:
        hits = [h for h in hits if h.startswith(kind + ":")] or hits
    if hits:
        # prefer a request the case defines
        for h in hits:
            if h in case_requests:
                return h
        return hits[0]
    return direct if kind else f"order:{name}"


@lru_cache(maxsize=1)
def _vocabulary() -> frozenset[str]:
    words: set[str] = set()
    for phrases in list(tx.TOPICS.values()) + list(tx.REQUEST_ALIASES.values()):
        for p in phrases:
            words |= {w for w in tx.normalize(p).replace("-", " ").split() if len(w) >= 6}
    return frozenset(words)


def correct_typos(norm: str, extra: set[str] | None = None) -> str:
    """Replace a misspelt long word with the closest topic word ('medcations' -> 'medications')."""
    vocab = _vocabulary() | (extra or set())
    out = []
    for w in norm.split():
        if len(w) >= 6 and w not in vocab and w not in tx.STOPWORDS and w.isalpha():
            best, score = None, 0.0
            for v in vocab:
                if v[0] == w[0] and abs(len(v) - len(w)) <= 2:
                    r = fuzz.ratio(w, v)
                    if r > score:
                        best, score = v, r
            if best is not None and score >= 88 and tx.stem(best) != tx.stem(w):
                w = best
        out.append(w)
    return " ".join(out)


def match_facts(text: str, facts: list[dict], exclude_categories: tuple[str, ...] = ()) -> Intent:
    norm = tx.normalize(text)
    authored = {w for f in facts for t in (f.get("topics") or []) for w in tx.normalize(str(t)).split() if len(w) >= 6}
    norm = correct_typos(norm, authored)
    toks = tx.tokens(norm)
    intent = Intent()
    intent.cues = detect_cues(text)
    intent.is_question = "?" in (text or "") or bool(_Q_START.match(norm))
    intent.is_open_question = "open_question" in intent.cues
    keys: dict[str, str] = {}
    cats: dict[str, str] = {}
    spans: dict[str, tuple[set[int], set[int]]] = {}
    for f in facts:
        if f.get("category") in exclude_categories:
            continue
        best, best_phrase, best_key = 0.0, "", ""
        authored_hits: list[float] = []
        covered: set[int] = set()
        best_pos: set[int] = set()
        for phrase, weight, key in fact_phrases(f):
            s = _match_phrase(toks, phrase)
            if s:
                s *= weight
                pos = set(tx.phrase_positions(toks, list(_ptoks(phrase))) or ())
                covered |= pos
                if key == "authored":
                    authored_hits.append(s)
                if s > best:
                    best, best_phrase, best_key, best_pos = s, phrase, key, pos
        if len(authored_hits) > 1:
            # several of the author's own trigger phrases in one message: stronger evidence than any single one
            authored_hits.sort(reverse=True)
            best = max(best, sum(authored_hits[:3]))
        if best >= 1.0:
            intent.fact_scores[f["fact_id"]] = round(best, 3)
            intent.via[f["fact_id"]] = best_phrase
            keys[f["fact_id"]] = best_key
            cats[f["fact_id"]] = f.get("category", "")
            spans[f["fact_id"]] = (best_pos, covered)
    if intent.fact_scores:
        sc = dict(intent.fact_scores)
        dims = {k for k in sc if keys[k] in DIMENSION_KEYS}
        if dims:
            # a question about a dimension of the complaint ("when did the chest pain start?") is about the
            # dimension, not a request to restate the complaint; a specific topic ("how long have you smoked?")
            # beats a generic dimension phrase.
            specific = {k for k in sc if k not in dims and cats[k] != "chief_complaint" and not keys[k].startswith("category:")}
            background = {k for k in specific if cats[k] not in ("hpi", "ros")}
            if background or (specific and max(sc[k] for k in specific) >= max(sc[k] for k in dims)):
                for k in dims:
                    sc.pop(k)
            else:
                for k in [k for k in sc if cats[k] == "chief_complaint" and k not in dims]:
                    sc.pop(k)
        # "does anyone in your family have heart problems?" is a family question, not a question about the patient
        if any(cats[k] == "family" and keys[k] in ("family_history", "category:family_history", "authored") for k in sc) \
                and tx.phrase_in(norm, tx.TOPICS["family_history"]):
            for k in [k for k in sc if cats[k] in ("pmh", "risk", "ros", "hpi", "chief_complaint")]:
                sc.pop(k)
        # an opener phrase inside a pointed message ("...can you tell me what happened?") does not restate the complaint
        if "confront" in intent.cues:
            generic = [k for k in sc if keys[k] in ("chief_complaint", "category:chief_complaint")]
            if len(generic) < len(sc):
                for k in generic:
                    sc.pop(k)
        # "are you allergic to any medications?" asks about allergies, not for the medication list
        if any(cats[k] == "allergies" for k in sc) and _ALLERGY_TO_MEDS.search(norm):
            for k in [k for k in sc if cats[k] == "medications"]:
                sc.pop(k)
        # "...or anything else?" at the end of a pointed question is not a request for associated symptoms
        pointed = [k for k in sc if keys[k] not in ("associated_symptoms", "chief_complaint") and not keys[k].startswith("category:")]
        if pointed:
            for k in [k for k in sc if keys[k] == "associated_symptoms"]:
                sc.pop(k)
        # a word that only matched inside a longer phrase belonging to a stronger match is not a topic of its own
        # ("water pill" is not a request for the medication list; "travel to your arm" is not about travel)
        for k in sorted(sc, key=lambda x: sc[x]):
            bp = spans[k][0]
            if bp and any(o != k and o in sc and sc[o] > sc[k] and bp <= spans[o][1] for o in list(sc)):
                sc.pop(k)
        top = max(sc.values())
        # a named topic ("...or diabetes?") stays even next to a longer phrase; only broad category matches are pruned relatively
        keep = [(s, fid) for fid, s in sc.items() if s >= 0.55 * top or (s >= 2.0 and not keys[fid].startswith("category:") and keys[fid] != "slug")]
        order = {f["fact_id"]: i for i, f in enumerate(facts)}
        keep.sort(key=lambda x: (-x[0], order.get(x[1], 0)))
        intent.fact_ids = [fid for _, fid in keep[:MAX_FACTS_PER_TURN]]
    return intent
