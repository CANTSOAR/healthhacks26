"""Typed checks for statements a clinician makes about the patient (SBAR sentences, answers to the colleague,
stage notes): does the SHARED RECORD hold the thing named?

What is checked, and how (all heuristic, word lists authored here; nothing reads the hidden case):
  medicines        a named medicine (list + common generic-name endings) that the record never mentions
  allergies        "allergic to X" where X is nowhere in the record
  tests / imaging  a result reported for a named test or scan that is not in the record, and "<test> showed <finding>"
                   where none of the finding's words are in the record
  past history     "has / had / history of / previous ... X" where X is a condition, device or procedure word the
                   record never mentions
Free-text reasoning ("I think this is ...") is NOT checked. A statement can be wrong in ways these rules miss.
"""
from __future__ import annotations

import re

from .. import taxonomy as tx
from ..patient import _stems, filler_stems

CHECKED = "medicines, allergies, test and imaging results, past history and figures"
SCOPE_NOTE = (f"Checked against the shared record by fixed rules: {CHECKED}. Free-text reasoning is not checked, "
              "and the rules can miss a statement that is wrong in other ways.")
FLAG = "unsupported — not in the shared record"

MEDICINES = set("""
warfarin coumadin heparin enoxaparin apixaban eliquis rivaroxaban xarelto dabigatran clopidogrel plavix ticagrelor aspirin
insulin lantus metformin glipizide gliclazide semaglutide ozempic empagliflozin sitagliptin
digoxin amiodarone nitroglycerin gtn furosemide lasix spironolactone hydrochlorothiazide bisoprolol metoprolol carvedilol atenolol
propranolol ramipril lisinopril enalapril losartan valsartan amlodipine nifedipine diltiazem verapamil atorvastatin simvastatin
rosuvastatin morphine fentanyl oxycodone hydrocodone codeine tramadol methadone buprenorphine naloxone paracetamol acetaminophen
tylenol ibuprofen advil naproxen diclofenac ketorolac gabapentin pregabalin diazepam lorazepam alprazolam midazolam zopiclone
sertraline fluoxetine citalopram escitalopram venlafaxine amitriptyline mirtazapine lithium quetiapine olanzapine haloperidol
levothyroxine prednisone prednisolone dexamethasone hydrocortisone methotrexate salbutamol albuterol ventolin ipratropium
tiotropium montelukast omeprazole pantoprazole esomeprazole lansoprazole ranitidine famotidine ondansetron metoclopramide
amoxicillin penicillin flucloxacillin doxycycline ceftriaxone cefalexin cephalexin vancomycin gentamicin ciprofloxacin
levofloxacin azithromycin clarithromycin erythromycin metronidazole nitrofurantoin trimethoprim fluconazole acyclovir
oseltamivir allopurinol colchicine tamsulosin finasteride sildenafil viagra tadalafil levetiracetam phenytoin carbamazepine
valproate lamotrigine cetirizine loratadine diphenhydramine benadryl epinephrine adrenaline tranexamic alteplase
""".split())
_MED_ENDING = re.compile(r"(?:olol|sartan|statin|prazole|dipine|mycin|cillin|cycline|floxacin|parin|xaban|gliptin|gliflozin|formin|"
                         r"tidine|setron|azepam|zolam|codone|profen|semide|thiazide|triptan|lukast|terol|oxetine|triptyline|"
                         r"[^a]pril|asone|isone|solone)$")

# name -> how it may be written. Matched against the statement and against the record text.
TESTS: dict[str, str] = {
    "CT": r"\bct\b|\bcat scan\b|computed tomograph",
    "MRI": r"\bmri\b|magnetic resonance",
    "X-ray": r"\bx[\s-]?rays?\b|\bcxr\b|radiograph",
    "ultrasound": r"ultrasound|\buss\b|sonogra|doppler",
    "echocardiogram": r"\becho\b|echocardiogra",
    "ECG": r"\becg\b|\bekg\b|electrocardiogra",
    "angiogram": r"angiogra",
    "troponin": r"troponin",
    "BNP": r"\b(?:nt[\s-]?pro)?bnp\b",
    "D-dimer": r"d[\s-]?dimer",
    "creatinine": r"creatinine",
    "potassium": r"potassium",
    "sodium": r"\bsodium\b",
    "haemoglobin": r"ha?emoglobin|\bhb\b|\bhgb\b",
    "white cell count": r"white (?:cell|blood cell|count)|\bwbc\b|\bwcc\b",
    "platelets": r"platelet",
    "lactate": r"lactate",
    "CRP": r"\bcrp\b|c[\s-]reactive",
    "glucose": r"glucose|blood sugar",
    "INR": r"\binr\b",
    "HbA1c": r"\bhba1c\b|\ba1c\b",
    "lipase": r"lipase",
    "bilirubin": r"bilirubin",
    "urinalysis": r"urinalysis|urine dip|\burine (?:test|result)",
    "blood culture": r"cultures?\b",
    "blood gas": r"blood gas|\babg\b|\bvbg\b",
    "pregnancy test": r"pregnancy test|\bhcg\b",
}
_TESTS = {k: re.compile(v, re.I) for k, v in TESTS.items()}
_RESULT_VERB = re.compile(r"\b(?:show(?:ed|s|ing)?|reveal(?:ed|s)?|demonstrat(?:ed|es)|confirm(?:ed|s)?|found|was|is|were|are|came back|"
                          r"result(?:s|ed)?|normal|abnormal|negative|positive|raised|elevated|high|low|clear|unremarkable)\b|\d", re.I)
_REQUESTING = re.compile(r"\b(?:needs?|order(?:ed|ing)?|request(?:ed)?|await(?:ing)?|plan(?:ned)?|will|should|please|consider|get|arrange|"
                         r"pending|chase|not back|not yet|outstanding|waiting)\b", re.I)
_FINDING = re.compile(r"\b(?:show(?:ed|s|ing)?|reveal(?:ed|s)?|demonstrat(?:ed|es)|confirm(?:ed|s)?)\s+(?:that\s+)?(.+)$", re.I)
_ALLERGY = re.compile(r"\b(?:allergic|allergy|allergies|anaphyla\w+|reacts?|reaction)\s+(?:to|with)\s+(.+)$", re.I)
_PAST_STRONG = re.compile(r"\b(?:had|history of|hx of|h/o|previous(?:ly)?|prior|past|diagnosed|suffered|underwent|status post|s/p|"
                          r"last (?:year|month|week)|(?:years?|months?|weeks?) ago|since \d{4}|fitted)\b", re.I)
_PAST_WEAK = re.compile(r"\b(?:has|have|having|known|with a|is (?:a |an )?(?:diabetic|asthmatic|epileptic|hypertensive))\b", re.I)
_HEDGE = re.compile(r"\b(?:i think|i suspect|i believe|impression|likely|probably|possibl[ey]|may be|might|could be|consistent with|"
                    r"suggests?|concern(?:ed)? for|worried about|query|looks like|seems)\b", re.I)
HISTORY_WORDS = set("""
pacemaker defibrillator stent bypass cabg valve stroke tia infarction diabetes diabetic hypertension hypertensive asthma asthmatic
copd emphysema epilepsy epileptic seizure seizures cancer tumour tumor chemotherapy radiotherapy dialysis transplant hiv hepatitis
cirrhosis dementia depression schizophrenia bipolar dvt embolism thrombosis fibrillation arrhythmia angina aneurysm ulcer surgery
operation appendectomy appendicectomy cholecystectomy hysterectomy mastectomy amputation pregnant pregnancy gout arthritis lupus
sickle thyroid hypothyroidism hyperthyroidism tuberculosis migraine anaemia anemia haemophilia hemophilia cardiomyopathy
pancreatitis diverticulitis crohn colitis sclerosis parkinson alzheimer osteoporosis fracture replacement prosthesis implant
pneumonia sepsis clot bleed haemorrhage hemorrhage kidney liver failure attack overdose alcoholism smoker
""".split())
_history_stems: set[str] | None = None


def history_stems() -> set[str]:
    global _history_stems
    if _history_stems is None:
        _history_stems = {tx.stem(w) for w in HISTORY_WORDS}
    return _history_stems


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z]+", (text or "").lower())


def _missing(words: list[str], record_text: str, r_stems: set[str]) -> list[str]:
    low = record_text.lower()
    out = []
    for w in words:
        if tx.stem(w) not in r_stems and not re.search(rf"\b{re.escape(w)}", low) and w not in out:
            out.append(w)
    return out


def _content_words(text: str) -> list[str]:
    fill = filler_stems()
    return [w for w in _words(text) if len(w) >= 4 and w not in fill and tx.stem(w) not in fill]


def is_medicine(word: str) -> bool:
    w = word.lower()
    return w in MEDICINES or (len(w) >= 7 and bool(_MED_ENDING.search(w)))


def claim_reason(clause: str, element: str, record_text: str, context: str | None = None) -> str | None:
    """Why this clause names something the record does not hold, or None. `context` is the whole sentence the clause
    was cut from (so "had a stroke and a bypass" keeps its "had" for the second half)."""
    ctx = context or clause
    r_stems = _stems(record_text)
    # a recommendation asks for things ("start heparin"): naming a medicine there is a request, not a claim about the patient
    meds = [] if element == "R" else _missing([w for w in _words(clause) if is_medicine(w)], record_text, r_stems)
    if meds:
        return f"no medicine called {', '.join(meds[:3])} is in the shared record"
    m = _ALLERGY.search(clause)
    if m:
        gone = _missing(_content_words(m.group(1)), record_text, r_stems)
        if gone:
            return f"no allergy to {', '.join(gone[:3])} is in the shared record"
    if element != "R":
        reports = bool(_RESULT_VERB.search(clause)) and not _REQUESTING.search(clause)
        for name, pat in _TESTS.items():
            if pat.search(clause) and reports and not pat.search(record_text):
                return f"no {name} result is in the shared record"
        f = _FINDING.search(clause)
        if f:
            said = _content_words(f.group(1))
            if said and len(_missing(said, record_text, r_stems)) == len(said):
                return f"the finding \"{f.group(1).strip().rstrip('.')}\" is not in the shared record"
        strong = bool(_PAST_STRONG.search(ctx))
        weak = bool(_PAST_WEAK.search(ctx)) and not _HEDGE.search(ctx)
        if strong or weak:
            hist = history_stems()
            gone = _missing([w for w in _content_words(clause) if tx.stem(w) in hist], record_text, r_stems)
            if gone:
                return f"no entry in the shared record mentions {', '.join(gone[:3])}"
    return None
