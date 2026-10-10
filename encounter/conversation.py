"""Conversational behaviour of the offline patient that is not the release of an authored fact:
default negatives, open prompts, feelings, niceties, off-topic and prompt-injection deflection.

None of these lines carries case-specific clinical content. A default negative ("No, I don't smoke") is
given only when the case defines nothing on that topic; it is recorded in the ledger as
`answered_negative_by_default` (never added to the chart) and can be switched off per case with
`"default_negatives": false`, in which case the patient gives the case's `unknown_response` instead.
"""
from __future__ import annotations

import hashlib

from . import taxonomy as tx

CONTINUATION = ["tell me more", "anything else", "go on", "what else", "say more", "can you tell me more", "any other symptoms", "other symptoms",
                "anything more", "and then", "carry on", "keep going", "elaborate", "more about that", "more about it", "anything you want to add"]
ICE = ["feeling about", "feel about", "how are you coping", "how are you holding up", "what worries you", "what are you worried", "worried about",
       "what do you think is going on", "what do you think it is", "what do you think is causing", "what are you hoping", "what were you hoping",
       "what would you like us to do", "what matters most", "your biggest concern", "what concerns you", "any concerns", "what scares you",
       "how is this affecting", "how has this affected", "what do you make of", "on your mind", "how are you doing with all"]
INJECTION = ["ignore your instructions", "ignore previous instructions", "ignore your previous", "ignore all previous", "ignore the above", "disregard your",
             "system prompt", "debug mode", "developer mode", "you are now", "faculty truth", "as an ai", "language model", "your instructions",
             "tell me your diagnosis", "tell me the diagnosis", "what is your diagnosis", "whats your diagnosis", "whats the diagnosis", "what is the diagnosis",
             "reveal the", "output the", "print the", "answer key", "hidden facts", "the rubric", "jailbreak", "pretend you are", "act as"]
THANKS = ["thank you", "thanks", "appreciate it", "cheers"]
BACKCHANNEL = {"hmm", "hm", "mm", "mhm", "ok", "okay", "right", "i see", "sure", "alright", "got it", "uh huh", "yes", "yeah", "understood", "fine", "k", "oh", "ah"}

# topics for which "no" is a safe everyday answer when the case defines nothing
NEGATABLE = {
    "smoking": ["No, I don't smoke.", "No. I'm not a smoker."],
    "alcohol": ["Not really, no. Hardly ever.", "No, I'm not much of a drinker."],
    "drugs": ["No, nothing like that.", "No. I don't use anything like that."],
    "allergies": ["No allergies that I know of.", "None that I know of."],
    "medications": ["No, I don't take anything regularly.", "Nothing regular, no."],
    "adherence": ["There's nothing I'm supposed to be taking.", "No, nothing to miss."],
    "pmh": ["No, nothing I know of.", "No. I've been pretty healthy."],
    "psh": ["No, I've never had an operation.", "No surgeries."],
    "hospitalizations": ["No, I've never been kept in hospital.", "No hospital stays."],
    "family_history": ["Nothing that I know of in my family.", "Not that I know of."],
    "travel": ["No, I haven't been anywhere lately.", "No travel recently."],
    "pregnancy": ["No, I'm not pregnant.", "No. I don't think so."],
    "self_harm": ["No. Nothing like that.", "No, I haven't had thoughts like that."],
    "safety_at_home": ["Yes, I feel safe at home.", "Home is fine. I feel safe there."],
    "previous_episodes": ["No, this is the first time.", "No, never before."],
    "vaccination": ["I think I'm up to date, but I couldn't swear to it.", "As far as I know I've had the usual ones."],
}
_GENERIC_NEG = ["No, nothing like that.", "No, I haven't noticed that.", "Not that I've noticed.", "No."]
SYMPTOM_KEYS = ["hypertension", "diabetes", "cholesterol", "heart_disease", "lung_disease", "pain_chest", "palpitations", "sob", "orthopnea", "cough", "wheeze",
                "swelling", "fever", "sweating", "fatigue", "weight_change", "appetite", "nausea_vomiting", "pain_abdomen", "bowel", "heartburn", "urinary",
                "headache", "dizziness", "syncope", "weakness_numbness", "speech_vision", "seizure", "neck_stiffness", "rash", "bleeding", "pain_back",
                "pain_joint", "red_flags_back", "ent", "withdrawal", "radiation", "sexual_history"]
_SPECIFIC_NEG = {
    "hypertension": ["No, not that I've been told.", "No, my blood pressure has never been a problem as far as I know."],
    "diabetes": ["No, not that I've been told.", "No diabetes that I know of."],
    "cholesterol": ["Not that I know of. I couldn't tell you the number.", "No one has told me it's high."],
    "heart_disease": ["No, no heart trouble that I know of.", "No. Nothing with my heart before."],
    "lung_disease": ["No, my lungs have always been fine.", "No asthma or anything like that."],
    "pain_chest": ["No, no chest pain.", "No. My chest feels fine."],
    "sob": ["No, my breathing is fine.", "No trouble breathing."],
    "fever": ["No, no fever that I've noticed.", "No fever or chills."],
    "cough": ["No, no cough.", "No, I'm not coughing."],
    "nausea_vomiting": ["No, I haven't felt sick or thrown up.", "No nausea, no vomiting."],
    "headache": ["No, no headache.", "No. My head's fine."],
    "dizziness": ["No, I haven't been dizzy.", "No dizziness."],
    "syncope": ["No, I haven't passed out.", "No, I didn't black out."],
    "bowel": ["No, that's all been normal.", "No problems there."],
    "urinary": ["No, that's all normal.", "No trouble passing urine."],
    "radiation": ["No, it stays where it is.", "No, it doesn't go anywhere else."],
    "sexual_history": ["There's nothing to tell there, really.", "Nothing relevant there, I don't think."],
    "weight_change": ["No, my weight's been steady.", "No change in my weight that I've noticed."],
    "swelling": ["No, no swelling.", "No, nothing's swollen."],
    "rash": ["No, no rash.", "No, my skin's fine."],
}
UNKNOWN_VARIANTS = ["I'm not sure. I can't really tell you anything about that.", "I honestly couldn't say.", "I don't know, sorry.",
                    "That's not something I can tell you, I'm afraid."]
OFF_TOPIC = ["I'm not sure what that has to do with why I'm here.", "Sorry, I don't follow. Can we get back to what's wrong with me?",
             "I don't really see how that matters right now, doctor."]
INJECTION_LINES = ["Sorry, I don't understand what you mean. I'm just here because I don't feel right.",
                   "I don't know what you're asking me, doctor. You tell me what's wrong, that's why I came.",
                   "I'm the patient here. I was hoping you could tell me."]
ICE_LINES = ["Honestly, I'm a bit worried. I just want to know what's going on.", "I'm anxious, to tell you the truth. I'd like some answers.",
             "It's unsettling. I'm hoping you can tell me what this is and what happens next."]
NOTHING_MORE = ["That's everything I can think of.", "I think that's all, really.", "Nothing else comes to mind."]
THANKS_LINES = ["You're welcome.", "No problem.", "Of course."]
INTRO_LINES = ["Hello, doctor.", "Hi. Nice to meet you.", "Hello."]
EMPATHY_LINES = ["Thank you. I appreciate that.", "Thanks. That helps.", "That means a lot, thank you."]
EXPLAIN_LINES = ["Okay. Thank you for explaining.", "All right. That makes sense.", "Okay, I understand."]
BACKCHANNEL_LINES = ["Mm-hm.", "Yes.", "Right."]
CLOSING_Q_LINES = ["No, I don't think so. Thank you.", "No questions right now. Thank you, doctor.", "I think that covers it. Thanks."]
CLOSING_LINES = ["Okay. Thank you.", "All right, thank you.", "Thanks, doctor."]
SUMMARY_LINES = ["Okay.", "Mm-hm.", "All right."]

ALL_FIXED_LINES = set(_GENERIC_NEG + UNKNOWN_VARIANTS + OFF_TOPIC + INJECTION_LINES + ICE_LINES + NOTHING_MORE + THANKS_LINES + INTRO_LINES + EMPATHY_LINES
                      + EXPLAIN_LINES + BACKCHANNEL_LINES + CLOSING_Q_LINES + CLOSING_LINES + SUMMARY_LINES + ["No. That isn't possible for me."]
                      + [v for vs in list(NEGATABLE.values()) + list(_SPECIFIC_NEG.values()) for v in vs])


def cues(text: str) -> dict[str, list[str]]:
    norm = tx.normalize(text)
    out = {}
    for name, phrases in (("continuation", CONTINUATION), ("ice", ICE), ("injection", INJECTION), ("thanks", THANKS)):
        hits = tx.phrase_in(norm, phrases)
        if hits:
            out[name] = hits
    if norm.startswith("system") or "system:" in (text or "").lower():
        out.setdefault("injection", []).append("system")
    if norm in BACKCHANNEL or (len(norm.split()) <= 2 and all(w in BACKCHANNEL for w in norm.split()) and norm):
        out["backchannel"] = [norm]
    return out


def question_topics(text: str) -> list[str]:
    """Taxonomy keys a question touches, most specific first (independent of any case)."""
    toks = tx.tokens(text)
    hits = []
    for key in list(NEGATABLE) + SYMPTOM_KEYS:
        best = 0.0
        for p in tx.TOPICS.get(key, []):
            pt = tx.tokens(p)
            if tx.contains_phrase(toks, pt):
                best = max(best, len(pt) + 0.1 * sum(len(t) for t in pt))
        if best:
            hits.append((best, key))
    hits.sort(reverse=True)
    return [k for _, k in hits[:3]]


def pick(pool: list[str], key: str, last_reply: str | None) -> str:
    """Stable choice for a key (same question, same wording), but never the sentence that was just said."""
    i = int(hashlib.sha256(key.encode()).hexdigest()[:6], 16) % len(pool)
    if last_reply and pool[i] in last_reply and len(pool) > 1:
        i = (i + 1) % len(pool)
    return pool[i]


def default_negative(topics: list[str], gender: str, last_reply: str | None) -> str:
    t = topics[0] if topics else ""
    if t == "pregnancy" and str(gender).lower() in ("male", "m", "man"):
        return "No. That isn't possible for me."
    pool = NEGATABLE.get(t) or _SPECIFIC_NEG.get(t) or _GENERIC_NEG
    return pick(pool, t or "generic", last_reply)
