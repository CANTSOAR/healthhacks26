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
    topics_asked: list[str] = field(default_factory=list)         # taxonomy keys the question touches, whatever the case defines
    clinical_yes_no: bool = False                                 # a yes/no question with clinical vocabulary
    clinical_words: bool = False
    starts_as_question: bool = False
    is_question: bool = False
    is_open_question: bool = False
    off_topic: bool = False                                       # words that belong to neither medicine nor this case, and nothing matched
    norm: str = ""                                                # the message after normalisation and typo correction
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


_GENERIC_SLUG = {"other", "others", "none", "current", "list", "history", "general", "negatives", "negative", "positive", "main", "new", "old",
                 "item", "fact", "misc", "details", "detail", "info", "status", "result", "results", "conditions", "condition", "context", "described",
                 "presenting", "visit", "reason", "symptoms", "symptom", "concern", "own", "words", "stopped", "hidden", "habits", "drug", "nkda"}
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
        words = [w for w in slug.split("_") if len(w) > 2 and w not in tx.STOPWORDS and w not in _GENERIC_SLUG]
        if words:
            add(" ".join(words), 1.6)
            for w in words:
                if w in tx.TOPICS:
                    for p in tx.TOPICS[w]:
                        add(p, 1.3)
    for key in tx.CATEGORY_TOPICS.get(fact.get("category", ""), []):
        cur[0] = "category:" + key
        # "which pills are you on?" IS the medication question: for these two categories the category is the topic
        w = 2.0 if key in ("medications", "allergies") else 1.0
        for p in tx.TOPICS.get(key, []):
            add(p, w)
    return tuple(out)


_YES_NO = re.compile(r"^(and |so |ok |okay )?(do|does|did|are|is|was|were|have|has|had|any|ever|can|could|would)\b")
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


def is_request_like(text: str) -> bool:
    """The clinician acting ("can I get an ECG", "let me listen to your chest", "order a troponin"), not a question about the
    patient ("what medications do you take?"). The same gate match_requests applies; also used on requests a model proposes."""
    norm = tx.normalize(text)
    if _ABOUT_PATIENT.match(norm):
        return False
    if not (_FIRST_PERSON.search(norm) or _IMPERATIVE.match(norm)):
        return False
    return bool(tx.phrase_in(norm, tx.REQUEST_VERBS))


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


_TEXT_SPEAK = {"u": "you", "ur": "your", "r": "are", "wat": "what", "wht": "what", "wot": "what", "abt": "about", "hav": "have", "pls": "please",
               "plz": "please", "thx": "thanks", "b4": "before", "2day": "today", "cuz": "because", "bc": "because", "hows": "how is", "ya": "you",
               "yr": "your", "wen": "when", "wer": "where"}
_COMMON_SHORT = {"about", "what", "when", "where", "which", "have", "does", "your", "pain", "hurt", "cough", "fever", "chest", "smoke", "drink", "sleep",
                 "work", "take", "long", "start", "worse", "feel", "blood", "heart", "pills", "meds", "dizzy", "sick", "tell", "more", "much", "many"}


@lru_cache(maxsize=1)
def _known_words() -> frozenset[str]:
    """Stems of every word the engine has a use for: topic phrases, requests, conversational cues, generic interview words."""
    from . import conversation as conv
    from .patient import _FILLER, _GENERIC, clinical_lexicon
    words: set[str] = set()
    lists = list(tx.TOPICS.values()) + list(tx.REQUEST_ALIASES.values()) + [
        tx.OPEN_QUESTION, tx.INTRODUCTION, tx.AGENDA, tx.EMPATHY, tx.NORMALISING, tx.JUDGMENTAL, tx.SUMMARISING, tx.CLOSING, tx.EXPLAINING, tx.CONFRONT_CUES,
        tx.JARGON, tx.REQUEST_VERBS, conv.CONTINUATION, conv.ICE, conv.INJECTION, conv.THANKS, conv.PROBE_HIDDEN, conv.GENERIC_PAIN, list(conv.BACKCHANNEL),
        list(conv.BODY_SYNONYMS), [w for v in conv.BODY_SYNONYMS.values() for w in v]]
    for phrases in lists:
        for p in phrases:
            words |= set(tx.tokens(p))
    words |= {tx.stem(w) for w in _GENERIC} | {tx.stem(w) for w in _FILLER} | set(tx.STOPWORDS) | {tx.stem(w) for w in tx.STOPWORDS} | set(clinical_lexicon())
    words |= {tx.stem(w) for w in "doctor nurse hospital clinic today yesterday tonight morning evening week month year hour minute day ago recent recently lately "
              "symptom symptoms problem problems question questions patient mister mrs miss sir madam name old age born bit lot little exactly "
              "happen happened happening notice noticed start started begin began stop stopped change changed bother bothering worry worried "
              "body side left right upper lower front top bottom inside outside usual usually normal normally often sometimes".split()}
    return frozenset(words)


def correct_typos(norm: str, extra: set[str] | None = None) -> str:
    """Replace a misspelt long word with the closest topic word ('medcations' -> 'medications'), expand text-speak
    ('ur' -> 'your') and undo swapped letters in short common words ('abuot' -> 'about')."""
    vocab = _vocabulary() | (extra or set())
    out = []
    for w in norm.split():
        if w in _TEXT_SPEAK:
            out.append(_TEXT_SPEAK[w])
            continue
        if 4 <= len(w) <= 5 and w.isalpha() and w not in _COMMON_SHORT and w not in tx.STOPWORDS:
            swap = next((c for c in _COMMON_SHORT if len(c) == len(w) and sorted(c) == sorted(w) and c[0] == w[0]
                         and sum(a != b for a, b in zip(c, w)) == 2), None)
            if swap and tx.stem(w) not in _known_words():
                out.append(swap)
                continue
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
    from . import conversation as conv
    intent.cues.update(conv.cues(text))
    intent.norm = norm
    intent.topics_asked = conv.question_topics(norm)
    intent.is_question = "?" in (text or "") or bool(_Q_START.match(norm))
    intent.starts_as_question = bool(_Q_START.match(norm))
    from .patient import clinical_lexicon
    intent.clinical_words = bool(set(toks) & clinical_lexicon())
    intent.clinical_yes_no = intent.clinical_words and bool(_YES_NO.match(norm))
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
        if best and "progression" in intent.cues and best_key in ("aggravating", "relieving") \
                and "progression" not in {str(t).lower() for t in f.get("topics") or []}:
            continue                # "has it been getting worse?" asks how it has changed over time, not what brings it on
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
                parts = {f["fact_id"] for f in facts if f.get("complaint_part")}
                for k in [k for k in sc if (cats[k] == "chief_complaint" or k in parts) and k not in dims]:
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
    if not intent.fact_ids and not intent.topics_asked and not intent.clinical_words:
        # N7: a question made of words that belong to neither medicine nor this case ("who will win the election?")
        case_words = {t for f in facts for k in ("statement", "patient_answer", "label") for t in tx.tokens(str(f.get(k) or ""))}
        case_words |= {t for f in facts for tp in (f.get("topics") or []) for t in tx.tokens(str(tp))}
        known = _known_words()
        foreign = [t for t in toks if len(t) >= 3 and not t.isdigit() and t not in known and t not in case_words]
        intent.off_topic = bool(foreign)
    return intent
