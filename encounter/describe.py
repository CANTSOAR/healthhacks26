"""Studio "from a description" path: free text -> an honest DRAFT case.

Rule: the draft contains what the text states and nothing else. The closest condition template is used
only as scaffolding (chart sections, generic objectives, rubric link, and the standard-workup defaults the
encounter can fall back to); none of its symptoms, history, medicines or results are copied in.

How the text is read (offline, pattern-based):
  1. concealed element(s)            "is hiding that ...", "has not told her doctor", "does not want to tell anyone that ..."
  2. who the patient is              name, age ("45M", "74 y/o F", "6-year-old boy", "8-month-old"), sex, occupation
  3. vital signs and lab values      vitals go in the chart from the start; labs are released by the matching order
  4. allergies, medication list      every item, dose and frequency kept as written
  5. presenting complaint            an explicit "presents with ...", else the first clinical clause; split into symptoms
  6. social items, companions, worries, past history, stated negatives
  7. anything left over              each remaining sentence becomes a history fact in the patient's voice
  8. coverage check                  every sentence of the description must be reflected in the finished case
                                     (encounter/coverage.py); what is not is listed verbatim under "missing"

`statement` keeps the author's wording (third person); `patient_answer` is rewritten to first-person lay wording
and flagged `patient_answer_auto` for review. For a young child the answers are the child's own for symptoms and
parent-reported ("My mom says ...") for things a child would not know.

Returns (via templates.from_description) {"case", "notes", "method", "fallback", "template_id", "taken", "scaffolded", "missing"}.
"""
from __future__ import annotations

import hashlib
import re

from . import taxonomy as tx
from .coverage import coverage_report, missing_words_text, split_sentences
from .store import fill_defaults, slugify
from .validate import DRUG_CLASSES

NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "twelve": 12, "several": "several", "few": "a few", "couple": "a couple of"}
_UNIT = r"(?:minutes?|mins?|hours?|hrs?|days?|weeks?|wks?|months?|years?|yrs?)"
_UNIT_FULL = {"min": "minute", "mins": "minutes", "hr": "hour", "hrs": "hours", "wk": "week", "wks": "weeks", "yr": "year", "yrs": "years"}
_N = r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|several|a few|a couple of)"
_END = r"(?=\.(?:\s|$)|;|\n|$)"

_AGE = re.compile(r"\b(\d{1,3})\s*[- ]?\s*(?:year[- ]old|years?[- ]old|yrs?[- ]old|yo|y/o|y\.o\.?)(?![a-z])", re.I)
_AGE_SHORT = re.compile(r"(?<![\w/.])(\d{1,3})\s*(?:yo|y/o|yr|yrs)?\s*([MF])\b")
_AGE_MONTHS = re.compile(r"\b(\d{1,2})[- ]?(month|week|day)s?[- ]old\b", re.I)
_AGE2 = re.compile(r"\b(?:age|aged)\s*(\d{1,3})\b|\bwho is (\d{1,3})(?=\s+and\b|\s*,)|\bis (\d{1,3}) years? old\b|^[^,.]{2,40},\s*(\d{1,3})\s*,", re.I)
_SEX_AFTER_AGE = re.compile(r"(?:year[- ]old|years?[- ]old|yrs?[- ]old|month[- ]old|week[- ]old|yo|y/o|y\.o\.?)\s*,?\s*(?:[a-z\-]+\s+){0,2}?(woman|female|girl|lady|man|male|boy|gentleman|f|m)\b", re.I)
_FEMALE = r"woman|female|girl|lady|she|her|hers|herself|mrs|ms|miss"
_MALE = r"man|male|boy|gentleman|he|his|him|himself|mr"
_OCC3 = re.compile(r",\s*\d{1,3},\s+(?:an?\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|and|presenting|presents|comes|came)\b|[,.;])", re.I)
_NAME_LEAD = re.compile(r"^\s*(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?([A-Z][a-z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2})(?=\s*(?:,|\(|:|\bis\b|\bhas\b|\bcomes\b|\bpresents\b|\bwas\b|\barrives\b|\bcame\b))")
_NAME_SINGLE = re.compile(r"^\s*([A-Z][a-z'\-]{2,})(?=\s+is\s+an?\s+\d|,\s*(?:an?\s+)?\d{1,3}\b)")
_NAME_CHILD = re.compile(r"\b(?:[Mm]y|[Hh]er|[Hh]is|[Tt]heir) (?:son|daughter|child|baby|grandson|granddaughter),? ([A-Z][a-z'\-]{1,})\b")
_NOT_NAME = ("A", "An", "The", "This", "Patient", "She", "He", "I", "Brought", "Presents", "History", "No", "My", "Her", "His", "Blood", "Heart", "Temp", "Temperature",
             "Allergic", "Medications", "On", "Black", "Denies", "Reports", "Lives")
_NAME_ANY = re.compile(r"\b(?:[Nn]amed|[Nn]ame is|[Cc]alled|[Pp]atient:?|Mrs?\.?|Ms\.?|Miss)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)")
_OCC1 = re.compile(r"(?:year[- ]old|years old|yo|y/o),?\s+(?:(?:fe)?male\s+|man\s+|woman\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|presenting|presents|comes|came|complaining|brought|arrives|has|had|in|reports|reporting|c/o|and|was|is)\b|[,.;])", re.I)
_OCC2 = re.compile(r"\b(?:works? as|working as|employed as|job as|is|am)\s+(?:an?\s+)(?:retired\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|and|presenting|presents|comes|came)\b|[,.;]|$)", re.I)
_NOT_JOB = re.compile(r"^(man|woman|male|female|patient|lady|gentleman|boy|girl|person|adult|child|infant|baby|toddler|smoker|non-?smoker|diabetic|\d|presents?|presenting|"
                      r"was|is|who|comes?|came|brought|with|reports?|has|had|complains?|c/o|widow|widower|married|single|divorced|found|seen|woman|known)\b", re.I)

_PRESENT_STRONG = re.compile(
    r"\b(?:comes? in (?:with|for|because of|after)|came in (?:with|for|because of|after)|presents? (?:with|for|after)|presenting (?:with|for|after)|"
    r"presented (?:with|for|after)|complains? of|complaining of|c/o|chief complaint(?: is| of|:)?|brought in (?:by [^,.;]{2,40}? )?(?:with|for|after)|"
    r"brought (?:to [^,.;]{2,30}? )?by [^,.;]{2,40}? (?:with|for|after)|arrives? with|arrived with|has had|have had|i've had|i've got|has been having|"
    r"have been having|i've been having|is having|am having|i'm having|suffering from|is experiencing|has developed|developed|"
    r"(?<!\bhe )(?<!\bshe )reports|reporting|with complaints? of|complaint of)\s+(.+?)" + _END, re.I | re.S)
_PRESENT_WEAK = re.compile(
    r"(?:\b(?:year[- ]old|years?[- ]old|yrs?[- ]old|month[- ]old|yo|y/o)(?:\s+[a-z\-]+){0,5}?\s+with|(?<![\w/.])\d{1,3}\s*[MF]\s+with|\b(?:she|he|i|pt|patient)\s+(?:has|have|reports|describes))\s+(.+?)" + _END, re.I | re.S)
_NOT_COMPLAINT = re.compile(r"^(?:a\s+|an\s+)?(?:known|history|past|medical history|type [12]|diabetes|hypertension|asthma|copd|no\b|not\b|been taking|been on|stopped|"
                            r"allerg|a long|his|her|their|my)\b", re.I)
_DUR_OF = re.compile(rf"^({_N})\s+({_UNIT})\s+of\s+(.+)$", re.I)
_DUR_FOR = re.compile(rf"^(.+?)\s+(?:for|over|during)\s+(?:the\s+(?:last|past)\s+)?({_N})\s+({_UNIT})\b(.*)$", re.I)
_DUR_SINCE = re.compile(r"^(.+?)\s+(since\s+(?:yesterday|this morning|this afternoon|last night|last week|\w+day|\w+ \w+))\b(.*)$", re.I)
_DUR_BARE = re.compile(rf"^(.+?)\s+(?:x\s*)?(\d+)\s*({_UNIT}|h|d)$", re.I)

_SUBJ = r"(?:she|he|i|the patient|patient|pt|the child|the boy|the girl)"
_HIDE = re.compile(
    r"\b(?:is hiding|am hiding|hides|hiding|conceals|concealing|is concealing|will deny|denies(?= that\b)|won'?t (?:admit|mention|say|tell (?:you|anyone))|"
    r"(?:doesn'?t|does not|don'?t|do not|did not|didn'?t) (?:admit|mention|want to (?:say|admit|talk about|mention|tell (?:anyone|anybody|you|the doctor|(?:his|her|my) \w+)))|"
    r"(?:doesn'?t|does not|don'?t|do not) want (?:his|her|my|the) \w+ to (?:know|find out)|is reluctant to (?:admit|discuss|talk about|mention)|reluctant to (?:admit|discuss|talk about|mention)|"
    r"(?:is|am) (?:too )?(?:embarrassed|ashamed|afraid|scared) to (?:say|admit|mention|tell (?:anyone|anybody|us|staff|the staff|(?:his|her|my) \w+))|"
    r"(?:is|am|was)(?: not|n'?t) (?:mentioning|saying|admitting|volunteering)|(?:has|have)(?: not|n'?t) (?:mentioned|admitted|said)|"
    r"(?:has not|have not|hasn'?t|haven'?t) told (?:us|staff|the staff|the team)|(?:will not|won'?t|does not|doesn'?t) volunteer|plays? down|keeps (?:it )?to (?:himself|herself|myself)|"
    r"is embarrassed (?:about|to admit|by)|embarrassed (?:about|to admit|by)|ashamed (?:of|to admit)|secretly|"
    r"avoids? (?:talking about|mentioning|discussing)|minimi[sz]es|downplays|under-?reports|not forthcoming about|"
    r"(?:has not|have not|hasn'?t|haven'?t) told (?:anyone|anybody|(?:his|her|my|the) \w+)|keeps quiet about)\b\s*(?:that\s+|to\s+|about\s+|the fact that\s+)?(.+?)" + _END, re.I | re.S)
_WHOM = r"(?:anyone|anybody|us|staff|the staff|the team|the nurses?|the doctors?|(?:his|her|my) \w+)"
_MARK = (r"(?:(?:is|am|was)(?: not|n'?t) (?:mentioning|saying|telling " + _WHOM + r"|admitting|volunteering|disclosing|reporting)|"
         r"(?:has|have)(?: not|n'?t) (?:mentioned|told " + _WHOM + r"|said|admitted|disclosed|reported)|"
         r"(?:won'?t|will not|doesn'?t|does not|don'?t|do not|did not|didn'?t) (?:mention|say|admit|volunteer|disclose|tell " + _WHOM + r"|want to (?:say|admit|mention|talk about|tell " + _WHOM + r"))|"
         r"(?:is|am) (?:hiding|concealing|keeping quiet about|keeping)|hides|conceals|keeps quiet about|keeps (?:it|this|that) to (?:himself|herself|myself)|"
         r"(?:is|am) (?:too )?(?:embarrassed|ashamed|afraid|scared|frightened|reluctant) to (?:say|admit|mention|talk about|tell " + _WHOM + r")(?: so)?|"
         r"only admits?(?: to)?(?: it| this| that)? (?:if|when) (?:pressed|asked directly|confronted)|plays? (?:it |this |that )?down|minimi[sz]es|downplays|denies|under-?reports)")
_HIDE_POST = re.compile(
    r"(?:^|(?<=[.;]\s))\s*([^.;]{6,220}?),?\s+(?:but|and|though|although|yet|which (?:he|she|i))\s+(?:(?:she|he|i)\s+)?" + _MARK +
    r"(?:\s+(?:it|this|that|any of (?:it|this|that)|about (?:it|this|that)))?(?:\s+(?:to|from)\s+" + _WHOM + r")?(\s+because\s+[^.;]+?)?" + _END, re.I | re.S | re.M)
_HIDE_DENIES_BUT = re.compile(r"\bdenies\s+[^.;]{2,80}?,?\s+but\s+(?:actually|in fact|in truth|really|in reality)\s+(.+?)" + _END, re.I | re.S)
_HIDE_ONLY_IF = re.compile(r"\bonly admits?(?: to)?\s+((?!if\b|when\b)[^.;]{4,160}?)\s+(?:if|when) (?:pressed|asked directly|confronted)" + _END, re.I | re.S)
_HIDE_DENIES = re.compile(r"\bdenies\s+((?:[a-z]+ing)\s+(?:[^\s.;]+\s+){2,}?[^\s.;]+?)" + _END, re.I | re.S)
_HIDE_AFTER = re.compile(
    r"(?:^|(?<=[.;]\s))\s*(?:" + _SUBJ + r"\s+)?((?:has|have|had|is|am|was|takes?|uses?|drinks?|smokes?|stopped|started)\b[^.;]{3,160}?),?\s+(?:but|and|though|although)\s+"
    r"(?:(?:she|he|i)\s+)?(?:(?:has not|have not|hasn'?t|haven'?t|did not|didn'?t|does not|doesn'?t|do not|don'?t|won'?t|will not|never)\s+"
    r"(?:told|tell|mentioned|mention|admitted|admit)\b[^.;]{0,60}?|(?:minimi[sz]es?|downplays?|under-?reports?|hides?|conceals?|denies|deny|plays? down)\s+(?:it|this|that)\b[^.;]{0,40}?)"
    + _END, re.I | re.S | re.M)
_STOPPED = re.compile(r"\b(?:stopped|quit|not|isn'?t|hasn'?t been|skips?|skipping|misses|missing)\s+(?:taking\s+|been taking\s+)?(?:(?:her|his|their|the|my)\s+)?"
                      r"([a-z][a-z\- ]{2,40}?(?:pills?|tablets?|medication|medicine|meds|inhalers?|insulin|injections?|thinners?|drops|patch(?:es)?|statins?|antibiotics?))\b", re.I)
_VITALS = [
    ("blood_pressure", "Blood pressure", "mmHg", re.compile(r"\b(?:bp|blood[- ]pressure)\s*(?:is|was|of|at|:|=)?\s*(\d{2,3}\s*(?:/|over)\s*\d{2,3})(?:\s*mm\s*hg)?", re.I)),
    ("heart_rate", "Heart rate", "beats/min", re.compile(r"\b(?:hr|heart[- ]rate|pulse)\s*(?:is|was|of|at|:|=)?\s*(\d{2,3})\b(?:\s*(?:bpm|beats per minute|/min))?", re.I)),
    ("temperature", "Temperature", "", re.compile(r"\b(?:temp(?:erature)?|fever)\s*(?:is|was|of|at|to|:|=)?\s*(\d{2,3}(?:\.\d)?)\s*(?:°|degrees)?\s*([CF])?\b", re.I)),
    ("spo2", "Oxygen saturation", "%", re.compile(r"\b(?:spo2|sp02|o2 sats?|sats?|oxygen saturations?|saturations?)\s*(?:is|are|was|were|of|at|:|=)?\s*(\d{2,3})\s*%?(?:\s*on (?:room air|ra|\d+ ?l(?:itres?)?(?: of)?(?: oxygen)?))?", re.I)),
    ("respiratory_rate", "Respiratory rate", "breaths/min", re.compile(r"\b(?:rr|resp(?:iratory)?[- ]rate)\s*(?:is|was|of|at|:|=)?\s*(\d{1,2})\b", re.I)),
    ("glucose", "Blood glucose", "mg/dL", re.compile(r"\b(?:glucose|blood sugar|sugar)\s*(?:is|was|of|:|=)?\s*(\d{2,3})\b", re.I)),
]
# lab name pattern -> (key, label, the order that releases it)
_LABS = [
    (r"h(?:a)?emoglobin|hgb|hb", "hemoglobin", "Hemoglobin", "order:cbc"), (r"wbc|white (?:blood )?(?:cell )?count|white cells", "wbc", "White cell count", "order:cbc"),
    (r"platelets?|plt", "platelets", "Platelets", "order:cbc"), (r"h(?:a)?ematocrit|hct", "hematocrit", "Hematocrit", "order:cbc"),
    (r"inr", "inr", "INR", "order:coags"), (r"sodium", "sodium", "Sodium", "order:bmp"), (r"potassium", "potassium", "Potassium", "order:bmp"),
    (r"creatinine", "creatinine", "Creatinine", "order:bmp"), (r"bun|urea", "urea", "Urea", "order:bmp"), (r"bicarbonate|bicarb|hco3", "bicarbonate", "Bicarbonate", "order:bmp"),
    (r"troponin(?: [it])?", "troponin", "Troponin", "order:troponin"), (r"lactate", "lactate", "Lactate", "order:lactate"), (r"crp", "crp", "CRP", "order:crp"),
    (r"esr", "esr", "ESR", "order:crp"), (r"(?:nt-?pro)?bnp", "bnp", "BNP", "order:bnp"), (r"d[- ]?dimer", "d_dimer", "D-dimer", "order:d_dimer"),
    (r"hba1c|a1c", "hba1c", "HbA1c", "order:hba1c"), (r"lipase", "lipase", "Lipase", "order:lipase"), (r"tsh", "tsh", "TSH", "order:tsh"),
    (r"bilirubin", "bilirubin", "Bilirubin", "order:lft"), (r"alt", "alt", "ALT", "order:lft"), (r"ast", "ast", "AST", "order:lft"), (r"ph", "ph", "pH", "order:abg"),
]
_LAB_UNIT = r"g/dl|mg/dl|mmol/l|mmol/mol|ng/l|ng/ml|ng/dl|pg/ml|mg/l|x\s?10\^?9/l|k/ul|u/l|iu/l|meq/l|%"
_LAB_RX = [(re.compile(rf"\b(?:{pat})\s*(?:is|was|of|:|=|at|level(?: of| is)?)?\s*([<>]?\s*\d+(?:[.,]\d+)?)\s*({_LAB_UNIT})?(?![\w/])", re.I), key, label, req) for pat, key, label, req in _LABS]
_LAB_TITLES = {"order:cbc": "Blood count", "order:coags": "Clotting tests", "order:bmp": "Basic metabolic panel", "order:lft": "Liver tests", "order:abg": "Blood gas"}

_BODY = "arm|leg|hand|foot|feet|jaw|neck|back|chest|head|shoulder|knee|hip|ankle|wrist|elbow|face|eye|ear|side|flank|groin|abdomen|belly|stomach|thigh|calf|shin"
_ADJ_LIST = "red|hot|warm|swollen|painful|tender|severe|sharp|dull|sudden|mild|constant|itchy|dry|wet|productive|new|worsening|persistent|intermittent|large|small"
_PAIN_SCORE = re.compile(r"(?:,\s*)?\b(?:(?:which |that )?(?:she|he|i) (?:rates?|scores?)(?: it)?(?: as| at)?|rated|rates|scored|scoring|severity(?: of)?|(?:pain )?score(?: of)?)\s*"
                         r"(?:as |at |of )?(?:an? )?(\d{1,2})\s*(?:/|out of)\s*10\b", re.I)
_FUNCTION = set("a an the and or but of with for to in on at by from as which who that whom whose is are was were has have had also both then so than "
                "her his my their she he i it they when while because since if though although until after before".split())


def _tidy(p: str) -> str:
    """Trim what is left when a neighbouring clause was lifted out: dangling articles, conjunctions, prepositions, stray commas.
    Returns "" when nothing but function words remains."""
    p = re.sub(r"\s+", " ", p or "").strip(" ,;:.-")
    p = re.sub(r"\s+,", ",", p)
    p = re.sub(r",\s*(?:and|or|but)?\s*,", ",", p)
    while True:
        q = re.sub(r"(?:,?\s+|^)(?:a|an|the|and|or|but|of|with|for|to|in|on|at|by|from|as|which|who|that|is|are|was|were|has|have|had|also|both|when|while|because|since)$", "", p, flags=re.I).strip(" ,;:-")
        q = re.sub(r"^(?:and|or|but|of|with|for|to|by|from|as|which|who|that|also|both|then|so|,)\s+", "", q, flags=re.I).strip(" ,;:-")
        q = re.sub(r"\b(and|or|but)\s+(?:and|or|but)\b", r"\1", q, flags=re.I)
        q = re.sub(r"\b(?:a|an|the)\s+(and|or|but|of|with|,)\b", r"\1", q, flags=re.I)        # "confusion and a and cough"
        q = re.sub(r"\s+", " ", q)
        if q == p:
            break
        p = q
    if not [w for w in re.findall(r"[A-Za-z]{2,}", p) if w.lower() not in _FUNCTION]:
        return ""
    return p


_DRUG_NAMES = {m for members in DRUG_CLASSES.values() for m in members if " " not in m} - {"contrast", "latex", "nsaid", "nsaids", "sulfa", "opioid", "opioids",
                                                                                           "statin", "macrolide", "fluoroquinolone", "cephalosporin", "asa"}
_DRUG_NAMES |= set(
    "warfarin apixaban rivaroxaban dabigatran heparin enoxaparin clopidogrel ticagrelor metformin insulin glargine lispro gliclazide glipizide sitagliptin empagliflozin "
    "semaglutide liraglutide lisinopril ramipril enalapril losartan valsartan candesartan amlodipine nifedipine diltiazem verapamil metoprolol atenolol bisoprolol "
    "carvedilol propranolol furosemide bumetanide spironolactone hydrochlorothiazide chlorthalidone digoxin amiodarone nitroglycerin isosorbide omeprazole pantoprazole "
    "lansoprazole esomeprazole ranitidine famotidine levothyroxine prednisone prednisolone dexamethasone hydrocortisone salbutamol albuterol budesonide fluticasone "
    "tiotropium montelukast sertraline fluoxetine citalopram escitalopram paroxetine venlafaxine duloxetine amitriptyline mirtazapine bupropion quetiapine olanzapine "
    "risperidone lithium lorazepam diazepam alprazolam clonazepam zolpidem gabapentin pregabalin levetiracetam lamotrigine carbamazepine phenytoin valproate "
    "acetaminophen paracetamol tylenol tramadol methadone buprenorphine allopurinol colchicine methotrexate hydroxychloroquine alendronate tamsulosin finasteride "
    "sildenafil nitrofurantoin trimethoprim doxycycline metronidazole fluconazole acyclovir oseltamivir cetirizine loratadine diphenhydramine ondansetron "
    "metoclopramide loperamide senna lactulose docusate ferrous iron folate multivitamin calcium magnesium melatonin estradiol progesterone levonorgestrel "
    "sumatriptan topiramate aspirin ibuprofen naproxen".split())
_DRUG_SUFFIX = re.compile(r"^[a-z]{3,}(?:pril|olol|statin|sartan|formin|dipine|parin|xaban|cillin|mycin|floxacin|prazole|conazole|tidine|zepam|zolam|oxetine|triptan|"
                          r"gliptin|flozin|glutide|cycline|semide|thiazide|lukast|isone|isolone|codone|morphone|profen|gatran|setron|pidem|mab|nib)$")
_DRUG_GENERIC = re.compile(r"\b(?:pills?|tablets?|inhalers?|puffers?|insulin|blood[- ]thinners?|the pill|birth control|contraceptive|water pills?|vitamins?|supplements?|"
                           r"patch(?:es)?|eye drops|drops|statins?|antibiotics?|painkillers?|steroids?|injections?|antidepressants?|laxatives?|antacids?|nebuli[sz]ers?|sprays?|gtn|folic acid|"
                           r"creams?|ointments?|hrt)\b", re.I)
_DOSE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|micrograms?|g|units?|iu|ml|puffs?)\b", re.I)
_MED_TRIGGER = re.compile(r"\b(?:takes?|taking|is on|am on|i'm on|on|prescribed|uses?|using|started on|(?:regular |current |home )?(?:medications?|meds|medicines)(?: include| are|:)?)\s+", re.I)
_NO_MEDS = re.compile(r"\b(?:(?:takes?|is on|on|uses?)\s+(?:no|nothing)(?:\s+regular(?:ly)?)?(?:\s+(?:medications?|meds|medicines|tablets))?(?:\s+regularly)?|"
                      r"no regular (?:medications?|meds|medicines)|not on any (?:medications?|meds|medicines|regular \w+)|(?:does not|doesn'?t|do not|don'?t) take any (?:medications?|meds|medicines))\b", re.I)
_PREGNANT = re.compile(r"\b(?:is |am )?((?:\d{1,2} weeks(?: and \d days)? )pregnant)\b", re.I)
_ALLERGY = re.compile(r"\ballerg(?:ic|y|ies)\s*(?:to|:)\s*(.+?)" + _END, re.I | re.S)
_NO_ALLERGY = re.compile(r"\bno (?:known )?(?:drug |medication )?allergies\b|\bnkda\b|\bnka\b", re.I)
_RELATIVE = r"mother|father|mom|mum|mummy|mommy|dad|daddy|parents?|grandmother|grandfather|grandma|grandpa|grandparents?|wife|husband|partner|girlfriend|boyfriend|" \
            r"daughter|son|sister|brother|aunt|uncle|friend|neighbou?r|carer|caregiver|guardian|foster (?:mother|father|parents?)"
_ACCOMPANY = re.compile(rf"\b(?:brought (?:in |to [^,.;]{{2,30}}? )?by|accompanied by|comes? (?:in )?with|came (?:in )?with|attends? with|here with|together with)\s+"
                        rf"(?:his|her|their|my|the|a)\s+((?:{_RELATIVE})(?:\s+and\s+(?:{_RELATIVE}))?)\b", re.I)
_ACCOMPANY2 = re.compile(rf"(?:\b[A-Z][a-z]+'s|\b[Hh]is|\b[Hh]er|\b[Mm]y|\b[Tt]he)\s+((?:{_RELATIVE}))\s+(?:has |have )?brought\s+(?:him|her|me|them)(?:\s+in)?\b")
_LIVES = re.compile(r"\b(lives? (?:alone|with (?:(?!\s+(?:and|who|which)\s)[^.;,]){2,40}|in (?:(?!\s+(?:and|who|which)\s)[^.;,]){2,40})|(?:is|am) (?:married|widowed|divorced|single|homeless)|"
                    r"(?<=, )(?:married|widowed|divorced)(?=,)|\b(?:widow|widower)\b)", re.I)
_WORRY = re.compile(r"\b(?:is |am |feels? |feeling )?(worried|anxious|afraid|scared|frightened|concerned|terrified|stressed|embarrassed)\s+(about|that|of|by)\s+([^.;]{3,90})", re.I)
_SMOKES = re.compile(r"\b(non[- ]?smoker|never[- ]smoker|never smoked|(?:ex|former)[- ]?smoker(?:\s*\([^)]{2,40}\))?|(?:quit|stopped|gave up) smoking[^.;,]{0,40}|"
                     r"(?:heavy |lifelong |current |light |long[- ]?term |daily )?smoker(?: of [^.;,]{2,40}| for [^.;,]{2,30})?|(?:smokes?|vapes?)(?:\s+(?:(?!\s+(?:and|but)\s)[^.;,]){0,50})?|"
                     r"\d+[- ]pack[- ]years?(?: smoking)?(?: history)?)", re.I)
_DRINKS = re.compile(r"\b(drinks?\s+(?:(?!\s+(?:and|but)\s)[^.;,]){2,60}|(?:does not|doesn'?t|do not|don'?t) drink(?: alcohol)?|teetotal\w*|no alcohol|(?:social|heavy|occasional|moderate) drinker|"
                     r"alcohol\s*[:\-]\s*(?:none|nil|occasional\w*|social\w*|\d+[^.;,]{0,30}))", re.I)
_DRUG_USE = re.compile(r"\b((?:uses?|smokes?|injects?) (?:cocaine|heroin|cannabis|marijuana|meth\w*|iv drugs|recreational drugs|crack)[^.;,]{0,40}|"
                       r"no (?:illicit |recreational |iv )?drug use|ivdu)", re.I)
_PMH = re.compile(r"\b(?:(?:past |medical )?history of|h/o|hx of|known|long-?standing|diagnosed with|suffers? from|lives? with|past medical history(?: of|:| includes)?|"
                  r"pmhx?(?: of|:)?|background of)\s+([a-z0-9][^.;]{2,90}?)(?=,?\s+(?:takes?|taking|on|and takes|who|brought|presents|comes|came|presenting|is|was|but)\b|"
                  r"\.(?:\s|$)|;|\n|$|\s*,?\s{3,})", re.I)
_PMH_HAS = re.compile(r"\b(?:has|have)\s+((?:type [12] )?(?:diabetes|hypertension|high blood pressure|asthma|copd|heart failure|atrial fibrillation|epilepsy|"
                      r"depression|anxiety|high cholesterol|kidney disease|migraines?|arthritis|cancer|hiv|angina)[^.;]{0,90}?)(?=,?\s+(?:and\s+)?(?:takes?|is on|uses?|for which|who|which)\b|"
                      r"\.(?:\s|$)|;|\n|$|\s*,?\s{3,})", re.I)
_PMH_ADJ = {"diabetic": "diabetes", "hypertensive": "hypertension", "asthmatic": "asthma", "epileptic": "epilepsy"}
_PMH_NONE = re.compile(r"\b(?:no (?:significant |relevant |known )?(?:past )?medical (?:history|problems)|previously (?:fit and )?(?:well|healthy)|otherwise (?:fit and )?(?:healthy|well)|"
                       r"no (?:pmh|pmhx))\b", re.I)
_NEGATIVE = re.compile(r"\b(?:denies|denied|no|without|negative for)\s+([a-z][^.;]{2,90}?)(?=,?\s+(?:but|and (?:she|he|i|has|is|takes))\b|\.(?:\s|$)|;|\n|$)", re.I)
_SEVERITY_HI = re.compile(r"\b(severe|critical|unstable|crushing|worst|collapsed|septic|unresponsive)\b", re.I)
_SEVERITY_LO = re.compile(r"\b(mild|minor|slight|stable)\b", re.I)

_TOPIC_HINTS = [("alcohol", r"alcohol|drink|beer|wine|vodka|whisk|liquor|gin\b"), ("drugs", r"cocaine|heroin|opioid|drug|marijuana|cannabis|meth|stimulant|oxycodone"),
                ("smoking", r"smok|cigarette|vap|tobacco|nicotine"), ("adherence", r"medic|pill|insulin|inhaler|tablet|dose|adheren|complian|prescri|stopped taking|thinner"),
                ("sexual_history", r"\bsex|condom|partner|\bsti\b|\bstd\b"), ("mood", r"depress|mood|sad|anxi|suicid|grief|lonely"),
                ("diet", r"diet|eat|food|salt|sugar|fruit|vegetable"), ("bowel", r"constipat|bowel|stool|diarrh"), ("safety_at_home", r"abuse|violence|unsafe|hit by|hurt by"),
                ("pregnancy", r"pregnan"), ("injury_mechanism", r"\bfell\b|fall|accident")]
COVERS = {"alcohol": "I drink socially, like anyone.", "drugs": "No, nothing like that.", "smoking": "Not really, no.",
          "adherence": "I take what I'm supposed to.", "sexual_history": "I'd rather not get into that.", "mood": "I'm fine. Just tired.",
          "diet": "I eat okay, I guess.", "bowel": "Everything's fine there.", "safety_at_home": "Everything is fine at home.",
          "pregnancy": "No, I don't think so.", "injury_mechanism": "I just slipped. It was nothing."}
COVER_SYMPTOM = "I'm fine, really. Nothing worth mentioning."
COVER_CHILD = "Um... no."
COVER_GENERIC = "I'd rather not get into that."
# what a student might actually say when asking about a hidden thing: (pattern on the concealed sentence, trigger phrases)
_CONCEAL_SYNONYMS = [
    (r"cough\w* (?:up )?blood|blood\w* (?:in|when|with)\w* .{0,12}(?:cough|sputum|phlegm)|h(?:a)?emoptysis",
     ["blood", "coughing up blood", "cough up blood", "coughed up blood", "blood when you cough", "bringing up blood", "cough", "spit", "spitting", "sputum", "phlegm",
      "hemoptysis", "haemoptysis"]),
    (r"swallow", ["swallow", "swallowed", "swallow anything", "swallowed anything", "ate", "eat anything", "eaten anything", "put in your mouth", "put anything in your mouth",
                  "in your mouth", "choke", "choked", "toy", "toys"]),
    (r"vomit\w* blood|blood\w* .{0,10}vomit|h(?:a)?ematemesis", ["blood", "vomiting blood", "blood in your vomit", "throwing up blood", "vomit"]),
    (r"black (?:tarry )?stool|blood\w* .{0,12}stool|rectal bleed|mel(?:a)?ena", ["blood", "blood in your stool", "black stools", "bleeding", "stool", "bowel"]),
    (r"overdos|took (?:too many|extra)|suicid|self[- ]harm|end (?:his|her|my) life", ["overdose", "too many", "harm yourself", "hurt yourself", "suicide", "self harm"]),
    (r"pregnan", ["pregnant", "pregnancy", "period", "last period"]),
    (r"\bfell\b|\bfall\b|\bfalls\b|fallen", ["fall", "fell", "fallen", "trip", "tripped"]),
    (r"hit (?:him|her|me)|hits (?:him|her|me)|abus|violen|assault", ["feel safe", "safe at home", "anyone hurt", "hurting you", "hit you", "violence"]),
    (r"chest pain", ["chest pain", "pain in your chest"]),
    (r"urinat|\bpee|passing (?:urine|water)|urine", ["burning when you pee", "pee", "peeing", "urinate", "passing urine", "passing water", "waterworks", "urine", "sting"]),
    (r"harm\w* (?:her|him|my)self|hurt\w* (?:her|him|my)self", ["harm yourself", "hurt yourself", "hurting yourself", "suicide", "self harm", "end your life"]),
    (r"faint|pass(?:ed|ing)? out|black(?:ed|ing)? out|collaps|knocked out|lost consciousness", ["faint", "fainted", "passed out", "pass out", "blacked out", "black out",
                                                                                             "collapse", "collapsed", "knocked out", "lose consciousness", "lost consciousness"]),
    (r"\b(?:hit|hits|banged|bumped|struck|knocked) (?:his|her|my) head|head injury", ["hit your head", "bang your head", "banged your head", "bump your head", "head injury",
                                                                                     "hurt your head", "your head", "head"]),
    (r"weight", ["weight", "lost weight", "losing weight"]),
    (r"\bsex\b|sexual|unprotected", ["sex", "sexually active", "partners", "condoms", "protection"]),
]
_PAINKILLER_WORDS = ["painkillers", "painkiller", "pain killers", "pain relief", "pain pills", "pain medication", "anti-inflammatory", "anti-inflammatories",
                     "over the counter", "anything for the pain", "take for the pain"]
_OBJECT_VERBS = r"(made|makes|make|gave|gives|give|told|tells|tell|helped|helps|help|let|lets|kept|keeps|keep|left|leaves|leave|caused|causes|hit|hits|scared|scares|worried|worries|bothers?|woke|wakes|brought|took|takes|stopped|stops)"
_ADV = r"(?:also|still|sometimes|often|usually|never|always|occasionally|recently|now|currently|only|rarely|regularly|just|already|really|no longer|normally|probably)"
_AUX = {"is": "am", "was": "was", "has": "have", "does": "do", "isn't": "am not", "isnt": "am not", "hasn't": "haven't", "hasnt": "haven't",
        "doesn't": "don't", "doesnt": "don't", "wasn't": "wasn't", "were": "was"}
_V3 = set("has is takes drinks smokes uses feels works lives gets needs wants vapes eats sleeps walks does denies reports says thinks keeps gives finds wakes coughs vomits "
          "goes stands sits lies tries stops starts was describes notices complains struggles avoids worries misses skips plays attends sees hears wears runs".split())
_BASE_VERBS = set("hit fell cut drank ate lost swallowed banged bumped blacked passed fainted collapsed injured hurt smoke drink take live work use vape have am feel get need want eat sleep walk cough stopped started noticed used tried took had got".split())
_ADJ_ED = set("worried embarrassed retired married divorced widowed scared frightened concerned stressed depressed tired exhausted terrified confused ashamed "
              "constipated nauseated bloated winded".split())
_ADJ = set("allergic anxious afraid unable short lightheaded light-headed dizzy nauseous breathless diabetic asthmatic unwell weak sick sore hungry thirsty sleepy "
           "pregnant homeless single reluctant unsteady itchy feverish drowsy irritable tearful".split())
_GERUND = {"feeling": "I feel", "having": "I have", "getting": "I get", "experiencing": "I get", "struggling": "I struggle", "finding": "I find"}
_VERB_ING = set("coughing vomiting taking drinking using smoking passing losing waking urinating sleeping eating seeing hearing falling walking struggling "
                "skipping missing avoiding hiding injecting buying stealing gambling cutting starving purging bingeing binging sweating shaking bleeding wetting "
                "throwing bringing spitting peeing going doing working living putting drinking snorting vaping running being".split())
_NOUN_ING = set("swelling burning tingling itching wheezing ringing cramping bloating spotting retching crushing stabbing throbbing pounding aching shooting "
                "gnawing splitting worsening morning evening something nothing".split())
_LAY = [(r"\bSOB\b", "shortness of breath"), (r"\bCP\b", "chest pain"), (r"\bN/V\b", "nausea and vomiting"), (r"\bHTN\b", "high blood pressure"),
        (r"\bT2DM\b", "type 2 diabetes"), (r"\bDM\b", "diabetes"), (r"\bCHF\b", "heart failure"), (r"\bMI\b", "a heart attack"), (r"\bCVA\b", "a stroke"),
        (r"\bA-?[Ff]ib\b|\bAF\b", "atrial fibrillation"), (r"\bUTI\b", "a urine infection"), (r"\bDVT\b", "a blood clot in the leg"), (r"\bPE\b", "a clot on the lung"),
        (r"\bGERD\b", "acid reflux"), (r"\bCKD\b", "kidney disease"), (r"\bCAD\b", "heart disease"), (r"\babd\b\.?", "belly"), (r"\bHA\b", "headache"),
        (r"\b[Hh]ypertension\b", "high blood pressure"), (r"\b[Dd]yspn(?:o)?ea\b", "shortness of breath"), (r"\b[Ss]yncope\b", "fainting"),
        (r"\b[Hh](?:a)?emoptysis\b", "coughing up blood"), (r"\b[Hh](?:a)?ematemesis\b", "vomiting blood"), (r"\b[Mm]el(?:a)?ena\b", "black stools"),
        (r"\b[Ee]mesis\b", "vomiting"), (r"\b[Pp]yrexia\b", "a fever"), (r"\bx\s*(?=\d)", "for ")]


def lay(s: str) -> str:
    """Clinical shorthand a patient would not say -> plain words (patient_answer only; the statement keeps the author's wording)."""
    for pat, repl in _LAY:
        s = re.sub(pat, repl, s)
    return s


_PAST_TIME = re.compile(r"\b(?:that (?:evening|night|morning|day)|last (?:night|week)|yesterday|earlier|ago|the night before|before (?:coming|arriving))\b", re.I)
_TIME_WORDS = set("day days week weeks month months year years hour hours minute minutes yesterday today tonight morning evening night nights ago since last past "
                  "right left small large little piece pieces most every each daily twice once time times few couple several one two three four five six seven eight nine ten "
                  "older younger elder old new high low bad good much many more less".split())


def _conj(v: str) -> str:
    low = v.lower()
    if low in _AUX:
        return _AUX[low]
    if low.endswith("ies") and len(low) > 4:
        return low[:-3] + "y"
    if low.endswith(("sses", "shes", "ches", "xes", "zes", "oes")):
        return low[:-2]
    if low.endswith("s") and not low.endswith(("ss", "us", "is")) and len(low) > 3:
        return low[:-1]
    return v


def _pronouns(s: str, name: str = "") -> str:
    """Third-person references to the patient -> first person (subject and verb agreement, possessives, objects)."""
    subj = ["she", "he", "the patient", "the child", "the boy", "the girl", "patient", "pt"]
    if name:
        parts = name.split()
        subj = [re.escape(name), re.escape(parts[0])] + ([r"(?:mr|mrs|ms|miss)\.?\s+" + re.escape(parts[-1])] if len(parts) > 1 else []) + subj
        s = re.sub(rf"\b(?:{re.escape(name)}|{re.escape(parts[0])})'s\b", "my", s)
    sub = "(?:" + "|".join(subj) + ")"
    s = re.sub(r"\b(?:she|he)\s+(?:says|states|reports|notes|thinks|feels|describes)\s+(?:that\s+)?(?=(?:it|she|he|the|this|her|his)\b)", "", s, flags=re.I)

    def verb(m):
        adv = m.group(1) or ""
        return "I " + adv + _conj(m.group(2))
    s = re.sub(rf"\b{sub}\s+((?:{_ADV}\s+)*)([a-z']+)", verb, s, flags=re.I)
    s = re.sub(rf"\b(and|but|or|then|,)\s+((?:{_ADV}\s+)*)({'|'.join(sorted(_V3))})\b", lambda m: f"{m.group(1)} {m.group(2) or ''}{_conj(m.group(3))}", s)
    s = re.sub(r"\bhis\b", "my", s, flags=re.I)
    s = re.sub(r"\bher\b(?=\s*(?:$|[,.;:)]|(?:to|that|and|about|with|for|in|on|at|from|when|if|because|but|so|or|by|before|after|until|up|down|out|off|again|feel|cough|vomit|sick|dizzy|tired|sleepy|anxious|nauseous|ill|worse|better|faint|itch|wheeze)\b))", "me", s, flags=re.I)
    s = re.sub(r"\bher\b", "my", s, flags=re.I)
    s = re.sub(r"\bhim\b", "me", s, flags=re.I)
    s = re.sub(r"\b(?:herself|himself)\b", "myself", s, flags=re.I)
    s = re.sub(r"\bhers\b", "mine", s, flags=re.I)
    s = re.sub(r"\bI am not\b", "I'm not", s)
    s = re.sub(r"\bI am\b", "I'm", s)
    s = re.sub(r"\bI have (been|had|not|never|got)\b", r"I've \1", s)
    s = re.sub(r"\bi\b", "I", s)
    return s


def _cap(s: str) -> str:
    s = s.strip()
    return s[0].upper() + s[1:] if s else s


_FINITE = re.compile(r"^(?:the|this|these|those|a|an|one|some|several|both|his|her|their|[a-z]+'s)\s+(?:[a-z'\-]+\s+){0,4}?(?:is|are|was|were|goes|gets|has|have|had|comes|came|"
                     r"spreads|moves|radiates|started|began|feels|hurts|wakes|keeps|makes|died|does|did|can|cannot|will|brought|gave|said|says|told)\b")


def _lead(s: str, past: bool = False) -> str:
    """Give a clause with no subject one: "feeling lightheaded" -> "I feel lightheaded", "black stools" -> "I've had black stools"."""
    low = s.lower()
    w = low.split(" ", 1)
    first, rest = w[0], (" " + s.split(" ", 1)[1] if len(w) > 1 else "")
    if re.match(r"^(i|i'm|i've|i'd|i'll|my|yes|there|it|it's|that|nobody|no one|we)\b", low):
        return s
    if _FINITE.match(low):              # already a sentence with its own subject ("the pain goes down my left leg")
        return s
    if re.match(r"^(no|not|never)\b", low):
        return "No, " + s[0].lower() + s[1:] if first == "no" else "I " + ("have " if first == "never" else "do ") + s[0].lower() + s[1:]
    if first in _GERUND:
        return _GERUND[first] + rest
    if first in _V3 or first in _AUX:
        return "I " + _conj(first) + rest
    if first in _ADJ_ED or first in _ADJ:
        return "I'm " + s[0].lower() + s[1:]
    if first in _BASE_VERBS or re.match(r"^(might|may|could|can|cannot|can't|will|would|should|must|did|didn't|won't)$", first):
        return "I " + s[0].lower() + s[1:]
    if first.endswith("ing") and first not in _NOUN_ING and rest.strip() and (
            first in _VERB_ING or re.match(r"^\s*(?:at|on|up|out|to|my|a|an|the|with|from|off|down|over|into|more|less|too)\b", rest)):
        return ("I was " if past or _PAST_TIME.search(s) and "since" not in low else "I've been ") + s[0].lower() + s[1:]
    if re.match(r"^[a-z]+ed$", first) and len(first) > 4 and first not in ("blurred", "slurred", "raised", "swelled", "reduced", "increased", "decreased", "coloured", "colored", "red"):
        return "I " + s[0].lower() + s[1:]
    return "I've had " + s[0].lower() + s[1:]


def first_person(clause: str, name: str = "", past: bool = False) -> str:
    """Third-person clause from a description -> what the patient would say. Conservative, flagged for review."""
    s = re.sub(r"\s+", " ", (clause or "").strip().rstrip(".").strip())
    if not s:
        return ""
    s = re.sub(rf"^(?:{_SUBJ}\s+)?(?:reports?|states?|notes?|endorses?|describes?|complains? of|admits? to|says?)\s+(?:that\s+)?(?=(?:an?|the|some|having|feeling|\w+ing|[a-z]+\s))",
               "", s, count=1, flags=re.I) if re.match(rf"^(?:{_SUBJ}\s+)?(?:reports?|states?|notes?|endorses?|complains? of|admits? to)\b", s, re.I) else s
    s = _lead(_pronouns(s, name), past)
    s = re.sub(r"\bI've had (?:a )?history of\b", "I have a history of", s)
    s = re.sub(r"\bI have (been|had|not|never|got)\b", r"I've \1", s)
    s = re.sub(r"\bI've had (.+\b(?:in (?:19|20)\d\d|ago|last (?:year|month|week))\b)", r"I had \1", s)
    return lay(s[0].upper() + s[1:] + ".")


_PAST = {"falling": "fell", "tripping": "tripped", "slipping": "slipped", "lifting": "lifted", "twisting": "twisted", "hitting": "hit", "crashing": "crashed",
         "cutting": "cut", "burning": "burned", "eating": "ate", "drinking": "drank", "taking": "took", "running": "ran", "playing": "was playing", "jumping": "jumped",
         "landing": "landed", "bending": "bent", "being": "was", "getting": "got", "coming": "came", "banging": "banged", "rolling": "rolled", "catching": "caught",
         "dropping": "dropped", "stepping": "stepped", "spilling": "spilled", "swallowing": "swallowed", "colliding": "collided", "diving": "dived", "riding": "was riding"}


def _mechanism(raw: str, name: str) -> str:
    """ "falling off his bicycle an hour ago" -> "I fell off my bicycle about an hour ago." (the event that brought the patient in) """
    s = _pronouns(re.sub(r"^(?:the)\s+", "", raw.strip()), name)
    first = s.split(" ", 1)[0].lower()
    if first not in _PAST:
        return ""
    s = "I " + _PAST[first] + s[len(first):]
    s = re.sub(r"(?<!about )(?<!around )\b((?:an?|\d+|one|two|three|four|five|six|a few|several) (?:minutes?|hours?|days?|weeks?) ago)", r"about \1", s)
    return s.rstrip(".") + "."


def _smoking_voice(p: str, name: str) -> tuple[str, str]:
    low = p.lower()
    if re.match(r"non[- ]?smoker|never[- ]smoker", low):
        return "No, I don't smoke.", "negative"
    if low.startswith("never smoked"):
        return "No, I've never smoked.", "negative"
    if re.match(r"(?:ex|former)[- ]?smoker", low):
        extra = re.search(r"\(([^)]+)\)", p)
        return "I used to smoke, but I gave it up" + (f" ({extra.group(1)})." if extra else "."), "positive"
    if re.match(r"(?:quit|stopped|gave up) smoking", low):
        return _cap(first_person(p, name)), "positive"
    if re.match(r"(?:smokes?|vapes?)\b", low):
        ans = first_person(re.sub(r"^(smoke|vape)\b", r"\1s", p, flags=re.I), name)
        return ("Yes, I smoke." if low.strip() in ("smokes", "smoke") else ans), "positive"
    if "pack" in low and "smoker" not in low:
        return "Yes, I smoke.", "positive"
    if low.strip() == "smoker":
        return "Yes, I smoke.", "positive"
    return "Yes, I'm a " + p[0].lower() + p[1:].rstrip(".") + ".", "positive"


def _alcohol_voice(p: str, name: str) -> tuple[str, str]:
    low = p.lower()
    if re.match(r"(?:does not|doesn'?t|do not|don'?t) drink|teetotal|no alcohol|alcohol\s*[:\-]\s*(?:none|nil)", low):
        return "No, I don't drink.", "negative"
    m = re.match(r"(social|heavy|occasional|moderate) drinker", low)
    if m:
        return {"social": "I drink socially.", "heavy": "Yes, I drink quite heavily.", "occasional": "Only occasionally.", "moderate": "I drink moderately."}[m.group(1)], "positive"
    if low.startswith("alcohol"):
        return _cap(re.sub(r"^alcohol\s*[:\-]\s*", "", p)) + ".", "positive"
    return first_person(re.sub(r"^drink\b", "drinks", p, flags=re.I), name), "positive"


def _generic_words() -> set[str]:
    from .patient import _GENERIC      # lazy: patient imports the engine
    return set(_GENERIC) | _TIME_WORDS | tx.STOPWORDS | {"she", "he", "his", "her", "him", "they", "their", "taking", "takes", "been", "has", "had", "have", "because",
                                                         "since", "when", "afraid", "anyone", "tell", "told", "want", "does", "not", "losing", "made", "stopped",
                                                         "pain", "pains", "small", "week", "weeks", "after", "before", "during", "while", "whenever",
                                                         "sudden", "suddenly", "started", "feels", "feeling", "says", "said", "describes", "also", "very",
                                                         "severe", "mild", "moderate", "about", "with", "without", "from", "into", "over", "under", "that",
                                                         "this", "which", "were", "them", "then", "than", "date", "anything", "something", "someone"}


def content_words(text: str, limit: int = 8) -> list[str]:
    """Distinctive words of a clause, as trigger phrases for the offline matcher."""
    generic = _generic_words()
    out = []
    for w in re.findall(r"[a-z][a-z\-]{3,}", (text or "").lower()):
        if w not in generic and w not in out:
            out.append(w)
    return out[:limit]


def _topic_keys(text: str, limit: int = 4) -> list[str]:
    toks = tx.tokens(text)
    hits = []
    for key, phrases in tx.TOPICS.items():
        if key in ("chief_complaint", "duration", "onset", "character", "location", "severity", "identity", "associated_symptoms", "patient_concerns", "radiation",
                   "aggravating", "relieving", "previous_episodes", "delay", "health_understanding", "healthcare_trust"):
            continue
        best = max((len(tx.tokens(p)) for p in phrases if tx.contains_phrase(toks, tx.tokens(p))), default=0)
        if best:
            hits.append((best, key))
    hits.sort(reverse=True)
    return [k for _, k in hits[:limit]]


def _dur_words(n: str, unit: str) -> str:
    n = n.lower()
    unit = _UNIT_FULL.get(unit.lower(), {"h": "hour", "d": "day"}.get(unit.lower(), unit.lower()))
    val = NUM_WORDS.get(n, n)
    if val in (1, "1"):
        return f"a{'n' if unit.startswith('hour') else ''} {unit.rstrip('s')}"
    return f"{n} {unit if unit.endswith('s') else unit + 's'}"


def _split_list(s: str) -> list[str]:
    return [p.strip(" ,") for p in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+|\s*\+\s*|\s+plus\s+", s) if p.strip(" ,")]


def _is_drug(item: str) -> bool:
    low = item.lower().strip()
    words = re.findall(r"[a-z][a-z\-]+", low)
    if not words or re.match(r"^(?:arrival|admission|examination|exam|the way|and off|room air|oxygen|a walker|a stick|a cane|a wheelchair|crutches)\b", low):
        return False
    return bool(_DOSE.search(item)) or any(w in _DRUG_NAMES or _DRUG_SUFFIX.match(w) for w in words[:5]) or bool(_DRUG_GENERIC.search(item))


class _Text:
    """The description plus the spans already placed, so that later readers only see what is left."""

    def __init__(self, text: str):
        self.t = text
        self.work = text

    def claim(self, a: int, b: int) -> None:
        if b > a:
            seg = "".join(ch if ch in ";\n" or (ch == "." and (a + i + 1 >= len(self.work) or self.work[a + i + 1].isspace())) else " "
                          for i, ch in enumerate(self.work[a:b]))
            self.work = self.work[:a] + seg + self.work[b:]


def extract(text: str) -> dict:
    """Pull out only what the description states."""
    t = re.sub(r"[ \t]+", " ", (text or "").strip())
    T = _Text(t)
    out: dict = {"vitals": [], "labs": [], "concealed": [], "pmh": [], "meds": [], "allergies": [], "social": [], "concerns": [], "symptoms": [], "negatives": [],
                 "leftover": [], "unplaced": [], "text": t}
    low = t.lower()

    # ---- 1. concealed elements first, so their text is not re-read as ordinary history
    for rx in (_HIDE_DENIES_BUT, _HIDE_ONLY_IF, _HIDE_POST, _HIDE_AFTER, _HIDE, _HIDE_DENIES):
        for m in rx.finditer(T.work):
            phrase = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")
            if len(phrase) < 4 or not re.search(r"[a-z]{3}", phrase) or not T.work[m.start():m.end()].strip():
                continue
            if rx is _HIDE_POST:
                if re.search(r"\b(?:presents?|comes? in|came in|brought in|year[- ]old)\b", phrase, re.I) and "," not in phrase:
                    continue            # the whole opening sentence is not the secret
                lead_cut = re.search(r"^.*\b(?:presents? with|comes? in with|came in with|year[- ]old [a-z ]{0,30}?with)\s+[^,]+,\s*(?:and\s+)?", phrase, re.I)
                if lead_cut:
                    phrase = phrase[lead_cut.end():]
                out["concealed"].append({"phrase": phrase, "reason": re.sub(r"^\s*because\s+", "", re.sub(r"\s+", " ", m.group(2) or ""), flags=re.I).strip(),
                                         "source": re.sub(r"\s+", " ", m.group(0)).strip()})
                T.claim(m.end() - len(m.group(0).lstrip()) + (len(m.group(0).lstrip()) - len(phrase)) if False else m.start(1) + (len(m.group(1)) - len(m.group(1).lstrip())), m.end())
                continue
            reason = ""
            r = re.search(r"\s+because\s+(.+)$", phrase, re.I)
            if r and not _STOPPED.search(phrase):
                reason, phrase = r.group(1).strip(), phrase[: r.start()].strip()
            out["concealed"].append({"phrase": phrase, "reason": reason, "source": re.sub(r"\s+", " ", m.group(0)).strip()})
            T.claim(m.start(), m.end())

    # ---- 2. who the patient is (claimed only after the complaint has been read: "a 52-year-old driver with ..." needs the age in place)
    demo_spans: list[tuple[int, int]] = []
    m = _AGE_MONTHS.search(t)
    if m:
        out["age"], out["age_text"] = 0, f"{m.group(1)}-{m.group(2).lower()}-old"
        demo_spans.append((m.start(), m.end()))
    else:
        m = _AGE.search(t) or _AGE_SHORT.search(t) or _AGE2.search(t)
        if m:
            n = int(next(g for g in m.groups() if g and g.isdigit()))
            if 0 < n < 121:
                out["age"] = n
                demo_spans.append((m.start(), m.end()))
    sx = _AGE_SHORT.search(t)
    sa = _SEX_AFTER_AGE.search(t)
    if sx:
        out["gender"] = "female" if sx.group(2) == "F" else "male"
    elif sa:
        out["gender"] = "female" if sa.group(1).lower() in ("woman", "female", "girl", "lady", "f") else "male"
        demo_spans.append((sa.start(1), sa.end(1)))
    else:                                   # the first gendered word wins ("his mother ... she" is still a boy)
        f, ma = re.search(rf"\b(?:{_FEMALE})\b", low), re.search(rf"\b(?:{_MALE})\b", low)
        if f and (not ma or f.start() < ma.start()):
            out["gender"] = "female"
        elif ma:
            out["gender"] = "male"
    m = _NAME_LEAD.search(t) or _NAME_ANY.search(t) or _NAME_SINGLE.search(t) or _NAME_CHILD.search(t)
    if not m:                           # the name may open a later sentence ("Oliver's mother brought him in. Oliver Grant is a 9-year-old ...")
        for a0, b0 in split_sentences(t)[1:3]:
            lead_ws = len(t[a0:b0]) - len(t[a0:b0].lstrip())
            m2 = _NAME_LEAD.search(t[a0 + lead_ws:b0]) or _NAME_SINGLE.search(t[a0 + lead_ws:b0])
            if m2 and m2.group(1).split()[0] not in _NOT_NAME:
                out["name"] = m2.group(1).strip()
                demo_spans.append((a0 + lead_ws + m2.start(), a0 + lead_ws + m2.end()))
                break
    if m and m.group(1).split()[0] not in _NOT_NAME:
        out["name"] = m.group(1).strip()
        demo_spans.append((m.start(1), m.end(1)) if m.re is _NAME_CHILD else (m.start(), m.end()))
    for rx in (_OCC1, _OCC3, _OCC2):
        m = rx.search(t)
        if m:
            job = re.sub(r"\s+(?:and|who|which|that)\b.*$", "", m.group(1).strip())
            if 1 <= len(job.split()) <= 4 and not _NOT_JOB.match(job) and not re.search(r"\b(old|year|with|pain|history|smoker|hiding|allergic|worried|anxious|afraid|on)\b", job):
                out["occupation"] = job
                demo_spans.append((m.start(1), m.end(1)))
                break
    child_word = re.search(r"\b(boy|girl|child|toddler|infant|baby|kid)\b", low)
    out["child"] = (out.get("age") is not None and out["age"] < 13) or (out.get("age") is None and bool(child_word))

    # ---- 3. vital signs and lab values
    for key, label, unit, rx in _VITALS:
        m = rx.search(T.work)
        if m:
            val = m.group(1).replace(" ", "").replace("over", "/")
            u = unit
            start = m.start()
            if key == "temperature":
                if not 30 <= float(val) <= 110:
                    continue
                u = (m.group(2) or ("F" if float(val) > 45 else "C")).upper()
                if m.group(0).lower().startswith("fever"):
                    start += len("fever")       # "a fever of 38.9" is a symptom AND a reading: only the number is lifted out
            out["vitals"].append({"key": key, "label": label, "value": val, "unit": u, "source": m.group(0).strip()})
            T.claim(start, m.end())
    m = _PAIN_SCORE.search(T.work)
    if m:
        out["pain_score"] = {"score": m.group(1), "source": re.sub(r"\s+", " ", m.group(0)).strip()}
        T.claim(m.start(), m.end())
    for rx, key, label, req in _LAB_RX:
        m = rx.search(T.work)
        if m:
            out["labs"].append({"key": key, "label": label, "value": m.group(1).replace(" ", "").replace(",", "."), "unit": m.group(2) or "", "request": req, "source": m.group(0).strip()})
            T.claim(m.start(), m.end())

    # ---- 4. allergies and medicines
    m = _NO_ALLERGY.search(T.work)
    if m:
        out["allergy_none"] = True
        T.claim(m.start(), m.end())
    for m in _ALLERGY.finditer(T.work):
        items, end = [], m.start(1)
        for piece in re.finditer(r"[^,]+", m.group(1)):
            for sub in re.split(r"\s+and\s+", piece.group(0)):
                sub = sub.strip()
                rc = re.match(r"^(?:which|that|it|they|this|these)\s+(?:gives?|gave|causes?|caused|makes?|made|brings?|brought)\s+(?:her|him|me|them)?\s*"
                              r"(?:out in |come out in |to |feel )?(?:an?\s+)?(.+)$", sub, re.I) or re.match(r"^(?:causing|with|giving (?:her|him|me))\s+(?:an?\s+)?(.+)$", sub, re.I)
                if rc and items and "(" not in items[-1]:
                    items[-1] += f" ({rc.group(1).strip()})"       # "sulfa drugs, which give her a rash" -> sulfa drugs (rash)
                    continue
                inline = re.match(r"^(.+?)\s+(?:which|that)\s+(?:gives?|gave|causes?|caused|makes?|made)\s+(?:her|him|me|them)?\s*(?:an?\s+)?(.+)$", sub, re.I) \
                    or re.match(r"^(.+?)(?:\s+[-–]\s+|:\s*)(?:an?\s+)?([a-z][a-z ]{2,30})$", sub, re.I) or re.match(r"^(.+?)\s+(?:causes?|caused|gives? (?:her|him|me))\s+(?:an?\s+)?(.+)$", sub, re.I)
                if inline and "(" not in sub:
                    sub = f"{inline.group(1).strip()} ({inline.group(2).strip()})"
                if not sub or re.match(rf"^(?:{_SUBJ}|takes?|is|has|on)\b", sub, re.I) or len(sub.split()) > 6:
                    items = items if items else []
                    break
                items.append(re.sub(r"^(?:to|and)\s+", "", sub))
            else:
                end = m.start(1) + piece.end()
                continue
            break
        items = [i for i in (_tidy(x) for x in items) if i]
        if items:
            out["allergies"] += [i for i in items if i not in out["allergies"]]
            out["allergy_source"] = (out.get("allergy_source", "") + " " + re.sub(r"\s+", " ", T.t[m.start():end])).strip()
            T.claim(m.start(), end)
    m = _NO_MEDS.search(T.work)
    if m:
        out["meds_none"] = re.sub(r"\s+", " ", m.group(0)).strip()
        T.claim(m.start(), m.end())
    m = _PREGNANT.search(T.work)
    if m:
        out["pregnant"] = re.sub(r"\s+", " ", m.group(1)).strip()
        T.claim(m.start(1), m.end(1))
    for m in list(_MED_TRIGGER.finditer(T.work)):
        tail = re.match(r"(.+?)" + _END, T.work[m.end():], re.S)
        if not tail or not T.work[m.start():m.end()].strip():
            continue
        items, end = [], m.end()
        for piece in re.finditer(r"[^,]+", tail.group(1)):
            ok = True
            pos = piece.start()
            for sm in re.finditer(r"(?:(?!\s+and\s+|\s*\+\s*).)+", piece.group(0), re.S):
                sub = re.sub(r"^(?:(?:and|also|occasionally|sometimes|then)\s+)*(?:(?:takes?|uses?|using|is on)\s+)?(?:(?:his|her|my|their)\s+)?", "", sm.group(0).strip(), flags=re.I)
                sub = re.sub(r"^and\s+", "", sub)
                if sub and _is_drug(sub):
                    items.append(sm.group(0).strip() if re.match(r"^(?:occasionally|sometimes)\b", sm.group(0).strip(), re.I) else sub)
                    end = m.end() + piece.start() + sm.end()
                elif sub:
                    ok = False
                    break
            if not ok:
                break
        if items:
            for it in items:
                ind = re.search(r"\s+for\s+(?:his |her |my |the )?([a-z][a-z0-9 \-]{3,40})$", it, re.I)
                if ind and not re.search(r"pain|ache|sleep|cough|cold|fever|nausea|days?|weeks?|months?|years?|a while", ind.group(1), re.I):
                    out.setdefault("indications", []).append(ind.group(1).strip())
                if it not in out["meds"]:
                    out["meds"].append(it)
            T.claim(m.start(), end)

    # ---- 5. who came with the patient; presenting complaint
    m = _ACCOMPANY.search(T.work) or _ACCOMPANY2.search(T.work)
    if m:
        out["accompanied_by"] = {"who": m.group(1).lower(), "source": re.sub(r"\s+", " ", m.group(0)).strip()}
        if m.re is _ACCOMPANY2:
            T.claim(m.start(), m.end())
    elif _NAME_CHILD.search(t):         # a parent is the one writing ("My son Leo is 2 ...")
        out["accompanied_by"] = {"who": "parent", "source": "Brought in by a parent"}
        out["parent_narrator"] = True

    def take_complaint(m) -> bool:
        comp = re.sub(r"\s+", " ", m.group(1)).strip(" ,")
        lead = re.sub(r"\s+", " ", T.work[m.start():m.start(1)]).strip().lower()
        comp = re.sub(r",?\s*\b(?:critical|critically ill|unstable|stable)\s*$", "", comp, flags=re.I).strip(" ,")
        if not comp or len(comp) > 220 or _NOT_COMPLAINT.match(comp) or not re.search(r"[a-z]{3}", comp):
            return False
        out["complaint_lead"] = "after" if lead.endswith("after") else ("article" if re.match(r"^(?:a|an)\s", comp, re.I) else "")
        out["complaint_raw"] = comp
        T.claim(m.start(1), m.end(1))
        return True

    for rx in (_PRESENT_STRONG, _PRESENT_WEAK):
        if "complaint_raw" in out:
            break
        for m in rx.finditer(T.work):
            if take_complaint(m):
                break
    a = _ACCOMPANY.search(T.work)
    if a:
        T.claim(a.start(), a.end())
    for a_, b_ in demo_spans:
        T.claim(a_, b_)

    # ---- 6. social items, worries, past history, stated negatives
    for m in _LIVES.finditer(T.work):
        out["social"].append(("living_situation", m.group(1).strip()))
        T.claim(m.start(), m.end())
    for rx, topic in ((_SMOKES, "smoking"), (_DRINKS, "alcohol"), (_DRUG_USE, "drugs")):
        m = rx.search(T.work)
        if m and m.group(1).strip():
            out["social"].append((topic, re.sub(r"\s+", " ", m.group(1)).strip()))
            T.claim(m.start(), m.end())
    for m in _WORRY.finditer(T.work):
        before = T.work[max(0, m.start() - 30): m.start()].lower()
        if re.search(rf"\b(?:{_RELATIVE})\s*(?:is|was|are|feels?|seems?)?\s*$", before):
            continue                    # someone else's worry: kept as its own sentence below
        out["concerns"].append(f"{m.group(1).lower()} {m.group(2).lower()} {re.sub(r'\s+', ' ', m.group(3)).strip()}")
        T.claim(m.start(), m.end())
    m = _PMH_NONE.search(T.work)
    if m:
        out["pmh_none"] = re.sub(r"\s+", " ", m.group(0)).strip()
        T.claim(m.start(), m.end())
    for rx in (_PMH, _PMH_HAS):
        for m in rx.finditer(T.work):
            for item in _split_list(re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")):
                item = re.sub(r"^(?:a|an)\s+(?=history)", "", item)
                if item and len(item) > 2 and all(item.lower() not in x.lower() for x in out["pmh"]):
                    out["pmh"].append(item)
            T.claim(m.start(), m.end())
    for adj, noun in _PMH_ADJ.items():
        m = re.search(rf"\b{adj}\b", T.work, re.I)
        if m and all(noun not in x.lower() for x in out["pmh"]):
            out["pmh"].append(noun)
            out.setdefault("pmh_source", {})[noun] = adj
            T.claim(m.start(), m.end())
    for ind in out.get("indications", []):
        if all(ind.lower() not in x.lower() for x in out["pmh"]):
            out["pmh"].append(ind)
            out.setdefault("pmh_implied", []).append(ind)
    for m in _NEGATIVE.finditer(T.work):
        items = re.sub(r"\s+", " ", m.group(1)).strip()
        if re.match(r"^(?:known|longer|one|other|more|further|significant)\b", items, re.I):
            continue
        out["negatives"].append({"items": items, "source": re.sub(r"\s+", " ", m.group(0)).strip()})
        T.claim(m.start(), m.end())

    # ---- 5b. no explicit "presents with": the first clinical clause that nothing else has claimed
    spans = split_sentences(t)
    demo = re.compile(r"\b\d{1,3}\s*[- ]?(?:year|yr|month|week)s?[- ]old\b|\b\d{1,3}\s*(?:yo|y/o)\b|(?<![\w/.])\d{1,3}\s*[MF]\b|\b(?:man|woman|male|female|boy|girl|gentleman|lady)\b", re.I)
    if "complaint_raw" not in out:
        for a, b in spans:
            pos = a
            for seg in re.split(r"(,)", T.work[a:b]):
                start, pos = pos, pos + len(seg)
                orig = t[start:pos]
                clean = seg.strip(" .;!?\n")
                words = [w for w in re.findall(r"[a-z]{3,}", clean.lower()) if w not in tx.STOPWORDS and w not in ("she", "he", "the", "patient")]
                if not words or demo.search(orig) or clean != orig.strip(" .;!?\n"):
                    continue                # empty, demographic, or partly claimed by something else
                out["complaint_raw"], out["complaint_lead"] = re.sub(r"\s+", " ", clean), ""
                out["complaint_fallback"] = True
                lead_ws = len(seg) - len(seg.lstrip())
                T.claim(start + lead_ws, start + lead_ws + len(seg.strip()))
                break
            if "complaint_raw" in out:
                break
    if "complaint_raw" in out:
        comp = re.sub(r"^(?:the)\s+", "", out["complaint_raw"])
        dur = None
        d = _DUR_OF.match(comp)
        if d:
            dur, comp = _dur_words(d.group(1), d.group(2)), d.group(3)
        else:
            d = _DUR_FOR.match(comp)
            if d:
                dur, comp = _dur_words(d.group(2), d.group(3)), (d.group(1) + d.group(4)).strip()
            else:
                d = _DUR_SINCE.match(comp)
                if d:
                    dur, comp = d.group(2), (d.group(1) + d.group(3)).strip()
                else:
                    d = _DUR_BARE.match(comp)
                    if d:
                        dur, comp = _dur_words(d.group(2), d.group(3)), d.group(1).strip(" ,")
        tail = re.search(r"\s+(?:that|which)\s+((?:started|began|came on|comes on|woke)\b.*)$", comp)
        if tail:
            out["onset_tail"] = tail.group(1).strip()
            comp = comp[: tail.start()].strip(" ,")
        rel = re.search(r",?\s+(?:which|that)\s+(?=(?:she|he|i|is|are|was|has|have|had|gets?|got|goes|went|comes?|came|feels?|hurts?|wakes?|keeps?|makes?|does|did|will|"
                        r"spreads?|radiates?|moves?|improves?|started|began)\b)(.+)$", comp, re.I)
        if rel:                         # "..., which gets worse when he climbs stairs and which is still there": said after the complaint, not inside it
            out["complaint_tail"] = [x.strip(" ,") for x in re.split(r"\s*,?\s+and\s+(?:which|that)\s+", rel.group(1)) if x.strip(" ,")]
            comp = comp[: rel.start()].strip(" ,")
        if comp[:1].isupper() and comp[1:2].islower() and comp.split()[0] not in (out.get("name") or ""):
            comp = comp[0].lower() + comp[1:]
        out["complaint"] = comp
        if dur:
            out["duration"] = dur
        parts = [p.strip() for p in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+(?:also\s+)?", comp) if p.strip()]
        merged: list[str] = []
        pending_adj = False
        for p in parts:                 # "pain and swelling in his right calf" is one thing, not two
            if merged and len(merged[-1].split()) <= 2 and not re.search(r"\b(?:in|of|on|when|with|after)\b", merged[-1]) and re.search(r"\b(?:in|of|on)\b", p) \
                    and len(parts) == 2:
                merged[-1] = merged[-1] + " and " + p
            elif merged and re.fullmatch(rf"(?:(?:his|her|my|the|left|right|both|upper|lower)\s+)*(?:{_BODY})s?", p, re.I):
                merged[-1] = merged[-1] + " and " + p                       # "pain in her jaw | left arm"
            elif merged and re.match(r"^(?:after|before|worse|better|while|when|since|with|on|especially|mainly|mostly|but|then|x\b|\d)", p, re.I):
                merged[-1] = merged[-1] + ", " + p                          # a modifier of the previous symptom, not a symptom
            elif merged and pending_adj:
                merged[-1] = merged[-1] + ", " + p
            else:
                merged.append(p)
            pending_adj = bool(re.search(rf"\b(?:{_ADJ_LIST})$", p, re.I))  # "a red | hot | swollen area ..."
        out["symptoms"] = merged

    # ---- 7. whatever is left: one fact per remaining sentence, or reported as not placed
    for a, b in spans:
        rest = T.work[a:b]
        orig = t[a:b].strip()
        pieces = [re.sub(r"\s+", " ", p).strip(" ,.;!?\n") for p in re.split(r" {3,}", rest)]
        whole = re.sub(r"\s+", " ", rest).strip() == re.sub(r"\s+", " ", t[a:b]).strip()
        for p in ([orig.strip(" .;!?\n")] if whole else pieces):
            p = re.sub(r"^(?:and|but|who|which|also|,)\s+", "", p, flags=re.I).strip(" ,")
            words = [w for w in re.findall(r"[a-z]{3,}", p.lower()) if w not in tx.STOPWORDS and w not in
                     ("she", "he", "his", "her", "the", "patient", "has", "had", "takes", "presents", "with", "who", "old", "year", "brought", "comes", "came", "also")]
            words = [w for w in words if w not in ("reports", "report", "presents", "comes", "came", "brought", "student", "states", "says", "then", "now")]
            if re.match(r"^(?:one of )?(?:whom|who|which|where|that|whose)\b", p, re.I):
                if words:
                    out["unplaced"].append(p)
                continue
            if len(words) >= 2 or (len(words) == 1 and len(words[0]) >= 6):
                finding = re.match(r"^(?:an?|some|several|two|three|multiple)\s+[a-z\- ]{3,40}?\s+(?:on|in|over|to|of|across|above|below|behind)\s+(?:his|her|my|the|both)\s+[a-z ]{3,30}$", p, re.I)
                (out["leftover"] if (whole or len(words) >= 3 or finding) and not demo.search(p) else out["unplaced"]).append(p)
    # ---- 8. nothing leaves here with a dangling article or conjunction where a neighbour was lifted out
    out["pmh"] = list(dict.fromkeys(x for x in (_tidy(p) for p in out["pmh"]) if x))
    out["meds"] = [x for x in (_tidy(p) for p in out["meds"]) if x]
    out["social"] = [(k, x) for k, x in ((k, _tidy(p)) for k, p in out["social"]) if x]
    out["concerns"] = [x for x in (_tidy(p) for p in out["concerns"]) if x]
    out["leftover"] = [x for x in (_tidy(p) for p in out["leftover"]) if len(x.split()) >= 2]
    out["unplaced"] = [x for x in (_tidy(p) for p in out["unplaced"]) if x]
    out["negatives"] = [n for n in ({**n, "items": _tidy(n["items"])} for n in out["negatives"]) if n["items"]]
    out["concealed"] = [c for c in ({**c, "phrase": _tidy(c["phrase"]), "reason": _tidy(c.get("reason") or "")} for c in out["concealed"]) if c["phrase"]]
    if "complaint" in out:
        out["symptoms"] = [x for x in (_tidy(s) for s in out["symptoms"]) if x]
        out["complaint"] = _tidy(out["complaint"])
        out["complaint_raw"] = _tidy(out["complaint_raw"]) or out["complaint"]
        if not out["complaint"] or not out["symptoms"]:
            for k in ("complaint", "complaint_raw", "symptoms", "duration", "complaint_lead"):
                out.pop(k, None)
            out["symptoms"] = []
    hi, lo = _SEVERITY_HI.search(low), _SEVERITY_LO.search(low)
    out["severity"] = "severe" if hi else ("mild" if lo else "moderate")
    if hi or lo:
        out["severity_word"] = (hi or lo).group(1)
    return out


_BAD_END = re.compile(r"(?:^|[\s,])(?:a|an|the|and|or|but|of|for|by|from|as|which|who|is|are|was|were|has|have|had|because|when|while|my)\s*[.,;:!?]*$|(?<!\bhere)(?<!\bme)\s+with\s*[.,;:!?]*$", re.I)
_BAD_MID = re.compile(r"\b(?:a|an|the|and|or|but|of|with)\s*[.,;:!?]|\b(?:a|an|the)\s+(?:for|since|and|or|but|of|with|in|on|at|to|is|was|has|a|an|the)\b|,\s*,|\b(and|or|but)\s+(?:and|or|but|which|who)\b|,\s*(?:and|or|but)?\s*[.!?]|\bmy\s+(?:a|an|the|me|my|I)\b|\bme\s+(?:a\s+)?my\b|"
                      r"\bI\s+(?:is|has|does|takes|drinks|smokes|was not|were)\b|\b(?:give|gives|make|makes)\s+my\s+(?:a|an)\b|\(|\)|\s{2,}|\.\.(?!\.)|^\W", re.I)
_THIRD_PERSON = re.compile(r"\b(?:she|he|her|his|him|hers|herself|himself)\b", re.I)


def text_problems(s: str, kind: str = "answer") -> list[str]:
    """What is visibly wrong with a drafted sentence: leftovers of the cut-and-paste that built it."""
    out = []
    s = s or ""
    words = re.findall(r"[A-Za-z']+", s)
    if not words:
        return ["empty"]
    if _BAD_END.search(s.strip()) and not (kind == "cover" and s.strip().lower().endswith(("no.", "no"))):
        out.append("ends in a function word")
    m = _BAD_MID.search(re.sub(r"\.\.\.\s*", "", s)) or (_BAD_PHRASE.search(s) if kind in ("answer", "parent") else None)
    if m and not (kind == "title" and m.group(0) in ("(", ")")):
        out.append(f"dangling or doubled word near '{m.group(0).strip() or 'spaces'}'")
    if kind == "title" and (len(s) > 110 or re.search(r"\b(?:he|she)\b", s)):
        out.append("title too long or contains a clause")
    if kind == "answer" and _THIRD_PERSON.search(s):
        out.append("third-person pronoun")
    if kind == "statement" and (len(words) < 2 and len(s) < 4):
        out.append("one-word statement")
    return out


def wording_problems(case: dict) -> list[str]:
    """Every drafted title, statement, answer, cover answer and fact id that shows a cut mark. Empty for a clean draft."""
    out = []
    for p in text_problems(case.get("title") or "", "title"):
        out.append(f"title \"{case.get('title')}\": {p}")
    for f in case.get("facts") or []:
        fid = f.get("fact_id", "")
        if re.search(r"(?:^|[._])(?:a|an|the|and|or|of|with|item)$", fid.split(".")[-1]) or fid.endswith("."):
            out.append(f"{fid}: fact id built from a function word")
        st = f.get("statement") or ""
        if not st.strip() or (len(st.split()) == 1 and len(st) < 3) or _BAD_END.search(st.strip()):
            out.append(f"{fid} statement \"{st}\": empty, one letter or cut off")
        if f.get("patient_knows") is not False and f.get("patient_answer_auto"):
            kind = "parent" if case.get("answers_by") else (
                "answer" if f.get("category") != "family" and not re.search(rf"\b(?:{_RELATIVE})\b", f.get("patient_answer") or "", re.I) else "other")
            for p in text_problems(f.get("patient_answer") or "", kind):
                out.append(f"{fid} answer \"{f.get('patient_answer')}\": {p}")
        if f.get("cover_answer"):
            for p in text_problems(f["cover_answer"], "cover"):
                out.append(f"{fid} cover answer \"{f['cover_answer']}\": {p}")
    return out


_KEEP_VERB = set("had was did got went took can cannot could will would should may might must".split())


def _to_parent(ans: str, gender: str, who: str) -> str:
    """A first-person answer -> the same thing said by the adult with a child too young to speak for themselves."""
    he, his, him = {"male": ("He", "his", "him"), "female": ("She", "her", "her")}.get(gender, ("They", "their", "them"))
    s = ans
    s = re.sub(r"\bI've\b", f"{he}'s", s)
    s = re.sub(r"\bI'm\b", f"{he}'s", s)
    s = re.sub(r"\bI have\b", f"{he} has", s)
    s = re.sub(r"\bI don't\b", f"{he} doesn't", s)
    s = re.sub(r"\bI do not\b", f"{he} does not", s)
    s = re.sub(r"\bI am\b", f"{he} is", s)

    def verb(m):
        v = m.group(1)
        if v.lower() in _KEEP_VERB or v.endswith("ed") or v.endswith("n't"):
            return f"{he} {v}"
        return f"{he} {v}es" if v.endswith(("s", "sh", "ch", "x", "o")) else (f"{he} {v[:-1]}ies" if v.endswith("y") and v[-2:-1] not in "aeiou" else f"{he} {v}s")
    s = re.sub(r"\bI ([a-z']+)\b", verb, s)
    s = re.sub(r"\b(and|but|or) have\b", r"\1 has", s)
    s = re.sub(r"\bmy\b", his, s)
    s = re.sub(r"\bMy\b", his.capitalize(), s)
    s = re.sub(r"\bme\b", him, s)
    s = re.sub(r"\bmyself\b", him + "self", s)
    s = re.sub(r"(?<=[a-z,] )(?:He|She|They)(?='s| )", lambda m_: m_.group(0).lower(), s)
    return s


_BAD_PHRASE = re.compile(
    r"\bI(?:'ve| have) had (?:the|this|that|he|she|his|her|was|is|has|after|before|worse|better|with|when|student)\b|\bI(?:'ve| have) had (?:hot|a red|left arm|right arm|worse[^.]*)\.|\bI have (?:was|is|has|had been)\b|"
    r"\bI'm an? (?:was|is|presents|comes|has|who|and)\b|\bgives? me vomit\b|\bI've had [A-Z][a-z]|(?<=[a-z]\. )[a-z]|\b(?:he|she)\.$|\bI've been (?:hitting|the|a)\b|"
    r"\bfor \d\.$|\band (?:he|she)\.|\bI (?:say|report|describe)\b")


def _parent(who: str) -> tuple[str, str]:
    w = who.split(" and ")[0]
    word = {"mother": "mom", "mum": "mum", "mummy": "mum", "mommy": "mom", "father": "dad", "daddy": "dad", "grandmother": "grandma", "grandfather": "grandpa"}.get(w, w)
    plural = " and " in who or w.endswith("s")
    if " and " in who:
        word = "parents" if {"mother", "father", "mom", "dad", "mum"} >= set(who.split(" and ")) else who
    return f"My {word}", ("say" if plural else "says")


def build_case(text: str, ex: dict, template: dict, model_extra: list[dict] | None = None, profile_extra: dict | None = None) -> tuple[dict, list[str], list[str], list[str]]:
    """Assemble the draft. Returns (case, taken, scaffolded, missing)."""
    taken, scaffolded, missing = [], [], []
    name = ex.get("name")
    age = ex.get("age")
    gender = ex.get("gender")
    child = bool(ex.get("child"))
    young = child and (age is None or age < 10)
    # too young to give a history: the adult with the child answers, about the child ("He's had a fever since last night.")
    infant = bool(ex.get("parent_narrator")) or (age is not None and age < 4) or bool(ex.get("age_text"))
    if infant:
        young = False
    who = (ex.get("accompanied_by") or {}).get("who")
    adult_with = who and re.search(r"mother|father|mom|mum|dad|parent|grand|guardian|carer|caregiver|aunt|uncle|foster", who)
    facts: list[dict] = []
    used: set[str] = set()
    nm = name or ""

    def fid(cat: str, slug: str) -> str:
        sl = slugify(slug, "item").replace("-", "_")[:30].strip("_")
        while sl != "accompanied_by" and re.search(r"(?:^|_)(?:a|an|the|and|or|of|with|in|on|at|to|for|by|her|his|my|that|which|is|has|was|it|he|she)$", sl) and "_" in sl:
            sl = sl.rsplit("_", 1)[0]
        sl = re.sub(r"^(?:a|an|the|he|she|his|her)_(?=.)", "", sl)
        base = f"f.{cat}.{sl or 'item'}"
        o, n = base, 2
        while o in used:
            o, n = f"{base}_{n}", n + 1
        used.add(o)
        return o

    def told(answer: str) -> str:
        """Things a young child would not know come out as reported by the adult with them."""
        if not (young and adult_with) or not answer:
            return answer
        p, v = _parent(who)
        body = re.sub(r"^(?:Yes|No),\s+", "", answer)
        return f"{p} {v} " + (body if body.startswith("I ") or body.startswith("I'") else body[0].lower() + body[1:])

    def topics_for(textv: str, keys_limit: int = 3, extra: list[str] | None = None) -> list[str]:
        out = list(extra or [])
        for k in _topic_keys(textv, keys_limit) + content_words(textv, 6):
            if k not in out:
                out.append(k)
        return out

    if name:
        taken.append(f"name: {name}")
    else:
        missing.append("patient name (a placeholder is used)")
    if age is not None:
        taken.append(f"age: {ex.get('age_text') or age}")
    else:
        missing.append("age (a placeholder of 40 is used)")
    if gender:
        taken.append(f"sex: {gender}")
    else:
        missing.append("sex")

    # ---- presenting complaint
    comp = ex.get("complaint")
    cc_statement = ""
    if comp:
        dur = ex.get("duration")
        symptoms = ex.get("symptoms") or [comp]
        raw = ex.get("complaint_raw", comp)
        cc_statement = _cap(raw)
        lead = ex.get("complaint_lead")
        dur_tail = (f" for {dur}" if dur and not dur.startswith("since") else (f" {dur}" if dur else ""))
        nps, sents = [], []
        for s in symptoms:
            fp = _pronouns(s, nm)
            voiced = _lead(fp)
            if voiced.startswith("I've had "):
                nps.append(fp)
            else:
                sents.append(_cap(voiced) + ".")
        mech = lead == "after" and _mechanism(raw, nm)
        if mech:
            ans, sents = mech, []
            hurt = next((re.search(r"\bpain in (?:his|her|my|the) ([a-z ]{3,30})$", x, re.I) for x in ex.get("leftover", []) if re.search(r"\bpain in (?:his|her|my|the) [a-z ]{3,30}$", x, re.I)), None)
            if hurt:                    # "came in after X. He has pain in Y" is one presenting story
                ans = ans.rstrip(".") + f" and my {hurt.group(1).strip()} hurts."
        elif lead == "after" and not sents:
            ans = f"I had {_pronouns(re.sub(r'^(?:the)\s+', '', raw), nm)}."
        elif nps:
            first_np = " and ".join(nps) if len(nps) <= 2 else ", ".join(nps[:-1]) + " and " + nps[-1]
            ans = (f"I've got {first_np}" if lead == "article" and not dur else f"I've had {first_np}") + dur_tail + "."
        else:
            ans = sents.pop(0)
            if dur:
                ans = ans.rstrip(".") + dur_tail + "."
        ans = " ".join([ans] + sents)
        facts.append({"fact_id": fid("chief_complaint", symptoms[0]), "category": "chief_complaint", "statement": cc_statement, "patient_knows": True,
                      "patient_answer": ans, "topics": ["chief_complaint"] + topics_for(comp, 4, [s for s in symptoms if len(s.split()) <= 5]),
                      "disclosure": {"rule": "volunteered"}, "critical": True, "chart_section": "hpi", "polarity": "positive", "patient_answer_auto": True})
        taken.append(f"presenting complaint: {cc_statement}" + (" (no 'presents with' phrase: the first clinical clause of the text was used)" if ex.get("complaint_fallback") else ""))
        if dur:
            facts.append({"fact_id": fid("hpi", "duration"), "category": "hpi", "statement": f"Symptoms present {('for ' + dur) if not dur.startswith('since') else dur}",
                          "patient_knows": True, "patient_answer": f"It's been {dur}." if not dur.startswith("since") else f"It started {dur[6:]}.",
                          "topics": ["onset", "duration"], "disclosure": {"rule": "if_asked"}, "chart_section": "hpi", "patient_answer_auto": True})
            taken.append(f"duration: {dur}")
        else:
            missing.append("how long the complaint has been present")
        for tail in ex.get("complaint_tail") or []:
            said = _pronouns(tail, nm)
            said = re.sub(r"^I ([a-z']+) (?!it\b)", r"I \1 it ", said) if said.startswith("I ") and re.match(r"^I (?:got|get|had|have|noticed|felt|feel)\b", said) else \
                (said if said.startswith("I ") else "It " + said)
            facts.append({"fact_id": fid("hpi", " ".join(content_words(tail, 3)) or "detail"), "category": "hpi", "statement": _cap(tail), "patient_knows": True,
                          "patient_answer": said + ".", "topics": topics_for(tail, 2), "disclosure": {"rule": "volunteered"}, "chart_section": "hpi",
                          "patient_answer_auto": True})
            taken.append(f"about the complaint: {tail}")
        if ex.get("pain_score"):
            ps = ex["pain_score"]
            facts.append({"fact_id": fid("hpi", "severity"), "category": "hpi", "statement": f"Pain {ps['score']}/10", "patient_knows": True,
                          "patient_answer": f"It's about {'an' if ps['score'] in ('8', '11', '18') else 'a'} {ps['score']} out of 10.", "topics": ["severity"],
                          "disclosure": {"rule": "if_asked"}, "chart_section": "hpi", "patient_answer_auto": True, "source_text": ps["source"]})
            taken.append(f"pain score: {ps['score']}/10")
        if ex.get("onset_tail"):
            facts.append({"fact_id": fid("hpi", "onset"), "category": "hpi", "statement": _cap(ex["onset_tail"]), "patient_knows": True,
                          "patient_answer": "It " + _pronouns(ex["onset_tail"], nm) + ".", "topics": ["onset"] + content_words(ex["onset_tail"], 4),
                          "disclosure": {"rule": "volunteered"}, "chart_section": "hpi", "patient_answer_auto": True})
            taken.append(f"onset: {ex['onset_tail']}")
        if len(symptoms) > 1:
            for s in symptoms:
                fp = _pronouns(s, nm)
                voiced = _lead(fp)
                a = ("Yes, I've had " + fp + ".") if voiced.startswith("I've had ") else ("Yes. " + _cap(voiced) + ".")
                facts.append({"fact_id": fid("hpi", "symptom " + s), "category": "hpi", "statement": _cap(s), "patient_knows": True, "patient_answer": a,
                              "topics": topics_for(s, 3, [s] if len(s.split()) <= 5 else []), "disclosure": {"rule": "if_asked"}, "chart_section": "hpi",
                              "polarity": "positive", "patient_answer_auto": True, "complaint_part": True})
            taken.append("symptoms, one fact each: " + "; ".join(symptoms))
    else:
        missing.append("presenting complaint (none could be read from the text: add a chief_complaint fact; the case cannot be approved without one)")

    if who:
        p, _v = _parent(who)
        src = ex["accompanied_by"]["source"]
        facts.append({"fact_id": fid("social", "accompanied by"), "category": "social", "statement": _cap(src), "patient_knows": True,
                      "patient_answer": f"{p} {'are' if _v == 'say' else 'is'} here with me.",
                      "topics": ["who is with you", "who came with you", "who brought you", "here with you", "anyone with you", "come alone", "by yourself", "on your own",
                                 "accompanied", "brought you in"] + who.replace(" and ", " ").split() + [{"mother": "mum", "father": "dad"}.get(who, who)],
                      "disclosure": {"rule": "if_asked"}, "chart_section": "social", "patient_answer_auto": True})
        taken.append(f"accompanied by: {who}")

    if ex.get("occupation"):
        job = ex["occupation"]
        art = "an" if job[0].lower() in "aeiou" else "a"
        facts.append({"fact_id": fid("social", "occupation"), "category": "social", "statement": f"Occupation: {job}", "patient_knows": True,
                      "patient_answer": f"I'm {art} {job}.", "topics": ["occupation"], "disclosure": {"rule": "if_asked"}, "chart_section": "social"})
        taken.append(f"occupation: {job}")
    for topic, phrase in ex.get("social", []):
        polarity = None
        if topic == "smoking":
            ans, polarity = _smoking_voice(phrase, nm)
        elif topic == "alcohol":
            ans, polarity = _alcohol_voice(phrase, nm)
        elif topic == "drugs":
            neg = re.match(r"no\b", phrase, re.I)
            ans, polarity = ("No, I don't use drugs." if neg else first_person(phrase, nm)), ("negative" if neg else "positive")
        else:
            ans = f"I'm a {phrase.lower()}." if phrase.lower() in ("widow", "widower") else first_person(phrase, nm)
        f = {"fact_id": fid("social", topic), "category": "social", "statement": _cap(phrase), "patient_knows": True, "patient_answer": ans, "topics": [topic],
             "disclosure": {"rule": "if_asked"}, "chart_section": "social", "patient_answer_auto": True}
        if polarity:
            f["polarity"] = polarity
        facts.append(f)
        taken.append(f"{topic.replace('_', ' ')}: {phrase}")
    for c in ex.get("concerns", []):
        mine = _pronouns(c, nm)
        facts.append({"fact_id": fid("hpi", "concern"), "category": "hpi", "statement": "Patient is " + c, "patient_knows": True,
                      "patient_answer": f"Honestly, I'm {mine}.", "topics": ["patient_concerns", "mood"], "disclosure": {"rule": "if_asked"},
                      "chart_section": "hpi", "patient_answer_auto": True})
        taken.append(f"concern: {c}")
    implied = set(ex.get("pmh_implied") or [])
    for p in ex.get("pmh", []):
        ans = first_person(p, nm) if re.match(r"^(?:was|is|had|has|been|were|underwent|needed|got)\b", p, re.I) else f"I have {_pronouns(p, nm)}." if not re.match(r"^(a|an)\b", p) else f"I{' ' if re.search(r'(?:19|20)[0-9][0-9]|ago', p) else chr(39) + 've '}had {_pronouns(p, nm)}."
        facts.append({"fact_id": fid("pmh", p), "category": "pmh", "statement": _cap(p), "patient_knows": True, "patient_answer": told(ans),
                      "topics": ["pmh"] + topics_for(p, 2), "disclosure": {"rule": "if_asked"}, "chart_section": "pmh", "polarity": "positive", "patient_answer_auto": True})
        (scaffolded if p in implied else taken).append(f"history: {p}" + (" (stated as the reason for a medicine)" if p in implied else ""))
    if ex.get("pmh_none"):
        facts.append({"fact_id": fid("pmh", "none"), "category": "pmh", "statement": _cap(ex["pmh_none"]), "patient_knows": True,
                      "patient_answer": told("No, I've been healthy apart from this."), "topics": ["pmh"], "disclosure": {"rule": "if_asked"}, "chart_section": "pmh",
                      "polarity": "negative", "patient_answer_auto": True})
        taken.append(f"history: {ex['pmh_none']}")
    for neg in ex.get("negatives", []):
        items = neg["items"]
        said = re.sub(r"\s+and\s+", " or ", _pronouns(items, nm))
        low_i = items.lower().strip()
        g = re.match(r"^([a-z]+ing)\s+(.+)$", low_i)
        base = {"hitting": "hit", "drinking": "drink", "smoking": "smoke", "using": "use", "taking": "take", "losing": "lose", "having": "have", "feeling": "feel",
                "falling": "fall", "injuring": "injure", "striking": "strike", "banging": "bang"}
        if low_i in ("alcohol", "drinking", "drinking alcohol", "alcohol use"):
            neg_ans = "No, I don't drink."
        elif low_i in ("smoking", "tobacco", "tobacco use"):
            neg_ans = "No, I don't smoke."
        elif low_i in ("drugs", "drug use", "illicit drugs", "recreational drugs"):
            neg_ans = "No, I don't use drugs."
        elif g and g.group(1) in base and not re.search(r",|\bor\b|\band\b", low_i):
            neg_ans = f"No, I didn't {base[g.group(1)]} {_pronouns(g.group(2), nm)}."
        else:
            neg_ans = f"No, no {said}."
        facts.append({"fact_id": fid("ros", "no " + items), "category": "ros", "statement": _cap(neg["source"]), "patient_knows": True,
                      "patient_answer": neg_ans, "topics": topics_for(items, 5), "disclosure": {"rule": "if_asked"}, "chart_section": "ros",
                      "polarity": "negative", "patient_answer_auto": True})
        taken.append(f"stated negative: {neg['source']}")
    med_items = list(ex.get("meds", []))
    stopped_items: list[str] = []

    artifacts = []
    for v in ex.get("vitals", []):
        f_id = fid("vitals", v["key"])
        num = v["value"] if "/" in v["value"] else (float(v["value"]) if "." in v["value"] else int(v["value"]))
        facts.append({"fact_id": f_id, "category": "vitals", "label": v["label"], "statement": f"{v['label']} {v['value']}{(' ' + v['unit']) if v['unit'] else ''}".strip(),
                      "value": num, "unit": v["unit"], "patient_knows": False, "topics": [v["label"].lower()], "disclosure": {"rule": "chart_initial"},
                      "chart_section": "vitals", "source_text": v.get("source", "")})
        taken.append(f"vital sign: {v['label']} {v['value']} {v['unit']}".strip())
    if not ex.get("vitals"):
        missing.append("vital signs (none in the text)")
    by_req: dict[str, list[dict]] = {}
    for lab in ex.get("labs", []):
        f_id = fid("lab", lab["key"])
        raw_v = lab["value"]
        num = raw_v if raw_v[0] in "<>" else (float(raw_v) if "." in raw_v else int(raw_v))
        facts.append({"fact_id": f_id, "category": "lab", "label": lab["label"], "statement": f"{lab['label']} {raw_v}{(' ' + lab['unit']) if lab['unit'] else ''}",
                      "value": num, "unit": lab["unit"], "patient_knows": False, "topics": [lab["label"].lower()],
                      "disclosure": {"rule": "on_request", "request": lab["request"]}, "chart_section": "labs", "critical": True, "source_text": lab.get("source", "")})
        by_req.setdefault(lab["request"], []).append({"test": lab["label"], "value": num, "unit": lab["unit"], "fact_id": f_id})
        taken.append(f"lab value: {lab['label']} {raw_v}" + (f" {lab['unit']}" if lab["unit"] else " (no unit stated: add one)"))
    for req, rows in by_req.items():
        label = _LAB_TITLES.get(req, rows[0]["test"])
        artifacts.append({"artifact_id": "art.lab_" + req.split(":")[1], "kind": "lab_report", "title": label, "section_id": "labs",
                          "release": {"rule": "on_request", "request": req}, "synthetic": True, "needs_review": True, "content": rows,
                          "linked_fact_ids": [r["fact_id"] for r in rows]})
        scaffolded.append(f"lab report '{label}' holding the stated value(s), released when the learner requests {req} (no reference ranges were invented)")

    # ---- concealed elements
    concealed_ids = []
    for i, c in enumerate(ex.get("concealed", [])):
        if isinstance(c, str):
            c = {"phrase": c, "reason": "", "source": c}
        phrase, reason = c["phrase"], c.get("reason") or ""
        low = phrase.lower()
        keys = [k for k, pat in _TOPIC_HINTS if re.search(pat, low)]
        stopped = _STOPPED.search(phrase)
        ans = first_person(phrase, nm, past=bool(_PAST_TIME.search(phrase)))
        if reason:
            why = _lead(_pronouns(reason, nm))
            ans = ans + " I didn't say because " + why[0].lower() * (not why.startswith("I")) + why[(0 if why.startswith("I") else 1):] + "."
        f_id = fid("concealed", (keys[0] if keys else " ".join(content_words(phrase, 2)) or "hidden") + ("_stopped" if stopped else ""))
        statement = _cap(re.sub(rf"^{_SUBJ}\s+", "", phrase, flags=re.I).strip()) + (f" (because {reason})" if reason else "")
        opener = "Okay... " if young else "All right. "
        f = {"fact_id": f_id, "category": "concealed", "statement": statement, "patient_knows": True, "patient_answer": opener + ans, "topics": list(keys),
             "critical": True, "chart_section": "medications" if stopped else "social", "polarity": "positive", "patient_answer_auto": True, "needs_review": True,
             "source_text": c.get("source") or phrase}
        if stopped:
            drug = re.sub(r"\s+", " ", stopped.group(1).strip())
            if not any(drug.lower() in m.lower() for m in med_items):
                stopped_items.append(drug)
                scaffolded.append(f"medication list: '{drug}' added because the concealed item says the patient stopped it")
            aid = "art.pharmacy_record" if not any(a["artifact_id"] == "art.pharmacy_record" for a in artifacts) else f"art.pharmacy_record_{i + 1}"
            artifacts.append({"artifact_id": aid, "kind": "medication_list", "title": "Pharmacy dispensing record", "section_id": "medications",
                              "release": {"rule": "on_request", "request": "order:medication_list"}, "synthetic": True, "needs_review": True,
                              "content": [{"medicine": drug[0].upper() + drug[1:], "last_dispensed": "EDIT: date of last supply", "note": "no refill collected since (placeholder: edit to match your case)"}],
                              "interpretation": f"A gap in collecting {drug}; a gap does not prove the medicine was not taken, so ask.", "linked_fact_ids": []})
            f["cover_answer"] = "I take my pills like I'm supposed to." if re.search(r"pill|tablet|med", drug) else COVERS["adherence"]
            f["disclosure"] = {"rule": "denied_until_confronted", "confront_with": [aid]}
            f["topics"] += [drug, "adherence", "are you taking your medicines", "stopped taking", "did you stop", "stop taking", "still taking", "taking your " + drug.split()[-1]]
            scaffolded.append(f"evidence path for the concealed item: a pharmacy dispensing record ({aid}, released by 'order:medication_list') with placeholder content to edit")
        else:
            syn: list[str] = []
            for pat, phrases in _CONCEAL_SYNONYMS:
                if re.search(pat, low):
                    syn += [p for p in phrases if p not in syn]
            words = set(re.findall(r"[a-z][a-z\-]+", low))
            drugs_named = sorted(w for w in words if w in _DRUG_NAMES or _DRUG_SUFFIX.match(w))
            for d in drugs_named:
                syn.append(d)
                for cls, members in DRUG_CLASSES.items():
                    if d in members and cls in ("nsaid", "opioid", "aspirin"):
                        syn += [p for p in _PAINKILLER_WORDS if p not in syn]
            for w in content_words(phrase, 6):
                if w not in syn:
                    syn.append(w)
            if not keys and not drugs_named:        # a hidden symptom also answers to the shared paraphrases for it
                syn += [k for k in _topic_keys(phrase, 2) if k not in syn]
            f["topics"] += [s for s in syn if s not in f["topics"]]
            symptomish = bool(syn) and not keys and not drugs_named
            # a deflection, not an invented flat lie: "I'm fine. It's just my wrist."
            part = re.search(rf"\b(?:left |right )?(?:{_BODY})\b", " ".join(x for x in ([ex.get("complaint") or ""] + list(ex.get("leftover") or [])) if re.search(r"pain|hurt|ache|sore|swollen|swelling", x)), re.I)
            deflect = f"I'm fine. It's just my {part.group(0).lower().replace('left ', '').replace('right ', '')}." if part and part.group(0).lower() not in phrase.lower() else COVER_SYMPTOM
            f["cover_answer"] = COVER_CHILD if young else (COVERS[keys[0]] if keys else ("No, nothing like that." if drugs_named else (deflect if symptomish else COVER_GENERIC)))
            # an introduction, an agenda and one open question already make rapport 3: a secret also needs one turn of real
            # empathy or normalising before it opens (QA: it came out on the first direct ask)
            f["disclosure"] = {"rule": "after_rapport", "rapport_needed": 3, "empathy_needed": 1}
            if drugs_named:
                f["chart_section"] = "medications"
            missing.append(f"evidence in the chart for the concealed item '{phrase[:50]}' (it opens up after rapport only; add an artifact and switch the rule to denied_until_confronted if you want a confrontation)")
        scaffolded.append(f"cover answer for the concealed item: \"{f['cover_answer']}\" (generic wording: edit)")
        scaffolded.append("questions that reach the concealed item were derived from its wording: " + ", ".join(str(x) for x in f["topics"][:10]))
        facts.append(f)
        concealed_ids.append(f_id)
        taken.append(f"concealed: {phrase}" + (f" (because {reason})" if reason else ""))

    # ---- medicines: one list fact holding every item, dose and frequency as written
    all_meds = med_items + stopped_items
    if all_meds:
        said = [("a " if re.search(r"(inhaler|patch|puffer|nebuli[sz]er)$", m) and not re.match(r"^(?:a|an|the|my)\b", m) else "") + lay(_pronouns(m, nm)) for m in med_items]
        join = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]    # noqa: E731
        parts = []
        if said:
            parts.append(told(f"I take {join(said)}."))
        if stopped_items:
            art = lambda mi: "a " if re.search(r"(inhaler|thinner|patch|statin|antibiotic)$", mi) else ""    # noqa: E731
            parts.append(("I'm also prescribed " if said else "I'm prescribed ") + join([art(m) + m for m in stopped_items]) + ".")
        drug_words = [w for m in all_meds for w in re.findall(r"[a-z][a-z\-]{3,}", m.lower()) if w in _DRUG_NAMES or _DRUG_SUFFIX.match(w)]
        slug = all_meds[0] if len(all_meds) == 1 and not med_items else "current"
        facts.append({"fact_id": fid("medications", slug), "category": "medications",
                      "statement": ("Prescribed " + all_meds[0]) if len(all_meds) == 1 and not med_items else "Medications: " + "; ".join(all_meds),
                      "patient_knows": True, "patient_answer": " ".join(parts), "topics": ["medications"] + list(dict.fromkeys(drug_words + _topic_keys(" ".join(all_meds), 2))),
                      "disclosure": {"rule": "if_asked"}, "chart_section": "medications", "critical": True, "patient_answer_auto": True})
        for m in med_items:
            taken.append(f"medication: {m}")
        if med_items and not any(a["kind"] == "medication_list" for a in artifacts):
            artifacts.append({"artifact_id": "art.medication_list", "kind": "medication_list", "title": "Medication list", "section_id": "medications",
                              "release": {"rule": "on_request", "request": "order:medication_list"}, "synthetic": True,
                              "content": [{"medicine": _cap(m)} for m in med_items], "linked_fact_ids": []})
            scaffolded.append("a medication list document holding the stated medicines, released by 'order:medication_list'")
    elif ex.get("meds_none"):
        facts.append({"fact_id": fid("medications", "none"), "category": "medications", "statement": _cap(ex["meds_none"]), "patient_knows": True,
                      "patient_answer": "No, I don't take any regular medicines.", "topics": ["medications"], "disclosure": {"rule": "if_asked"},
                      "chart_section": "medications", "polarity": "negative", "critical": True, "patient_answer_auto": True})
        taken.append(f"medication: {ex['meds_none']}")
    else:
        missing.append("medications (none stated: the patient will say they are not sure unless you add them)")
    if ex.get("pregnant"):
        facts.append({"fact_id": fid("pmh", "pregnant"), "category": "pmh", "statement": _cap(ex["pregnant"]), "patient_knows": True,
                      "patient_answer": f"I'm {ex['pregnant']}.", "topics": ["pregnancy", "pmh"], "disclosure": {"rule": "if_asked"}, "chart_section": "pmh",
                      "polarity": "positive", "critical": True, "patient_answer_auto": True})
        taken.append(f"pregnancy: {ex['pregnant']}")
    if ex.get("allergies"):
        items = ex["allergies"]
        names, reactions = [], []
        for a in items:
            r = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", a)
            nm_a = (r.group(1) if r else a).strip()
            names.append(nm_a)
            if r:
                react = re.sub(r"^(?:an?|the)\s+", "", r.group(2).strip())
                plural = nm_a.lower().endswith("s") and not nm_a.lower().endswith(("ss", "us", "is"))
                g, mk = ("give", "make") if plural else ("gives", "makes")
                how = {"rash": f"{g} me a rash", "hives": f"{g} me hives", "vomiting": f"{mk} me vomit", "nausea": f"{mk} me feel sick", "swelling": f"{mk} me swell up",
                       "anaphylaxis": f"{g} me a very bad reaction", "itching": f"{mk} me itch", "vomit": f"{mk} me vomit", "itch": f"{mk} me itch", "sick": f"{mk} me sick", "swell": f"{mk} me swell up",
                       "swell up": f"{mk} me swell up", "feel sick": f"{mk} me feel sick", "wheeze": f"{mk} me wheeze", "wheezing": f"{mk} me wheeze",
                       "diarrhea": f"{g} me diarrhea", "diarrhoea": f"{g} me diarrhoea"}.get(react.lower(), f"{g} me {_pronouns(react, nm)}")
                subj = ("They" if plural else "It") if len(items) == 1 else _cap(nm_a)
                reactions.append(f"{subj} {how}.")
        ans = "I'm allergic to " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]) + "." + "".join(" " + x for x in reactions)
        facts.append({"fact_id": fid("allergies", items[0]), "category": "allergies", "statement": ("Allergy: " if len(items) == 1 else "Allergies: ") + "; ".join(items),
                      "patient_knows": True, "patient_answer": told(_pronouns(ans, nm)), "topics": ["allergies"] + content_words(" ".join(items), 6),
                      "disclosure": {"rule": "if_asked"}, "chart_section": "allergies", "polarity": "positive", "critical": True, "patient_answer_auto": True,
                      "source_text": ex.get("allergy_source", "")})
        for a in items:
            taken.append(f"allergy: {a}")
    elif ex.get("allergy_none"):
        facts.append({"fact_id": fid("allergies", "nkda"), "category": "allergies", "statement": "No known drug allergies", "patient_knows": True,
                      "patient_answer": told("No allergies, as far as I know."), "topics": ["allergies"], "disclosure": {"rule": "if_asked"}, "chart_section": "allergies",
                      "polarity": "negative", "critical": True, "source_text": "NKDA no known drug allergies"})
        taken.append("allergy: none known")
    else:
        missing.append("allergies")
    if not ex.get("pmh") and not ex.get("pmh_none"):
        missing.append("past medical history")

    # ---- every remaining sentence, in the patient's voice
    rel_rx = re.compile(rf"\b(?:{_RELATIVE})\b", re.I)
    for s in ex.get("leftover", []):
        keys = _topic_keys(s, 3)
        about_other = bool(rel_rx.search(s))
        cat = "family" if about_other and (set(keys) & {"lung_disease", "heart_disease", "diabetes", "hypertension", "hospitalizations", "pmh", "mood"} or
                                           re.search(r"died|history|hospitali[sz]ed|diagnosed|has |had ", s, re.I)) else (
            "pmh" if set(keys) & {"vaccination", "psh", "hospitalizations", "pmh", "pregnancy"} else (
                "social" if set(keys) & {"occupation", "living_situation", "diet", "exercise", "sleep", "travel", "smoking", "alcohol", "drugs", "insurance_access"} else "hpi"))
        ans = first_person(s, nm)
        ans = re.sub(r"^I've had (an? )", r"I've got \1", ans)
        if cat in ("pmh",):
            ans = told(ans)
        # the family category already answers to "any family history?"; the companion's own word ("mother") must not pull this fact into
        # "is your mum here with you?"
        topics = [w for w in content_words(s, 6) if rel_rx.fullmatch(w) and w not in (who or "")] if cat == "family" else topics_for(s, 3)
        if cat == "hpi" and re.search(rf"\b(?:{_BODY})\b", s, re.I) and re.search(r"pain|hurts?|ache|sore|tender", s, re.I):
            topics = ["location"] + topics
        f = {"fact_id": fid(cat, " ".join(content_words(s, 3)) or "detail"), "category": cat, "statement": s if s[0].isupper() else _cap(s), "patient_knows": True,
             "patient_answer": ans, "topics": topics, "disclosure": {"rule": "if_asked"}, "chart_section": tx.CATEGORY_SECTION.get(cat, ("hpi", ""))[0],
             "patient_answer_auto": True}
        if re.search(r"\b(?:she|he|his|him|her)\b", ans) and not about_other:
            f["needs_review"] = True
        facts.append(f)
        taken.append(f"other detail, kept as its own {cat} fact: {s}")
    missing.append("diagnosis, differential and expected disposition in the faculty truth")
    missing.append("examination findings and test results beyond those stated (none are invented; undefined standard tests fall back to the template's normal result during the encounter)")

    for i, ef in enumerate(model_extra or []):
        if any(tx.normalize(ef["statement"]) == tx.normalize(f["statement"]) for f in facts):
            continue
        ef = dict(ef)
        while ef["fact_id"] in used:
            ef["fact_id"] += "_x"
        used.add(ef["fact_id"])
        facts.append(ef)
        if ef.get("cover_answer"):
            concealed_ids.append(ef["fact_id"])

    if child or (age is not None and age < 18):
        noun = {"female": "girl", "male": "boy"}.get(gender or "", "child")
    else:
        noun = {"female": "woman", "male": "man"}.get(gender or "", "patient")
    age_text = ex.get("age_text") or (f"{age}-year-old" if age is not None else "")
    triage = f"{age_text} {noun}." if age_text else f"{'Child' if child else 'Adult'} {noun if noun != 'child' else 'patient'}."
    triage = _cap(triage)
    if who:
        triage += f" {_cap(ex['accompanied_by']['source'])}."
    if comp:
        triage += f" {cc_statement}."
    for v in ex.get("vitals", []):
        triage += f" {v['label']} {v['value']}{(' ' + v['unit']) if v['unit'] else ''}."
    artifacts.insert(0, {"artifact_id": "art.triage_note", "kind": "document", "title": "Triage note", "section_id": "triage", "release": {"rule": "initial"},
                         "content": triage, "synthetic": True, "linked_fact_ids": []})
    scaffolded.append("triage note assembled from the stated age, sex, complaint and vital signs")

    objectives = []
    cc_ids = [f["fact_id"] for f in facts if f["category"] in ("chief_complaint", "hpi") and f["disclosure"]["rule"] != "chart_initial"][:4]
    if cc_ids:
        objectives.append({"objective_id": "obj.complaint", "criterion": "Establishes the presenting complaint and how long it has been going on", "kind": "elicit_fact",
                           "linked_fact_ids": cc_ids, "evidence_rule": "met when the linked facts are elicited", "critical": True, "rubric_domain": "gathering"})
    meds_ids = [f["fact_id"] for f in facts if f["category"] in ("medications", "allergies")]
    if meds_ids:
        objectives.append({"objective_id": "obj.medicines", "criterion": "Asks what medicines the patient takes and about allergies", "kind": "safety",
                           "linked_fact_ids": meds_ids, "evidence_rule": "met when asked", "rubric_domain": "gathering"})
    lab_ids = [f["fact_id"] for f in facts if f["category"] == "lab"]
    if lab_ids:
        objectives.append({"objective_id": "obj.tests", "criterion": "Requests the tests whose results the description gives", "kind": "action",
                           "linked_fact_ids": lab_ids, "linked_requests": sorted(by_req), "evidence_rule": "met when the tests are requested", "rubric_domain": "reasoning"})
    for k, cid in enumerate(concealed_ids):
        f = next(x for x in facts if x["fact_id"] == cid)
        objectives.append({"objective_id": f"obj.uncovers_{k + 1}", "criterion": "Uncovers what the patient holds back: " + f["statement"][:90], "kind": "elicit_fact",
                           "linked_fact_ids": [cid], "evidence_rule": "met when the patient discloses it", "critical": True, "rubric_domain": "listening"})
    objectives += [o for o in (template.get("objectives") or []) if o.get("objective_id") in ("obj.rapport", "obj.structure")]
    scaffolded.append(f"chart sections, the rapport and structure objectives and the rubric link from the '{template['id']}' template (no symptoms, history, medicines or results were copied from it)")

    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    sev = {"mild": 0.2, "moderate": 0.5, "severe": 0.85}[ex.get("severity", "moderate")]
    prof = {"name": name or "Unnamed patient", "age": age if age is not None else 40, "gender": gender or "unspecified"}
    bg = []
    if ex.get("occupation"):
        bg.append(f"Occupation: {ex['occupation']}.")
    bg += [p[0].upper() + p[1:] + "." for _, p in ex.get("social", []) if _ == "living_situation"]
    if who:
        bg.append(_cap(ex["accompanied_by"]["source"]) + ".")
    if bg:
        prof["background"] = " ".join(bg)
    if young:
        prof["speech_style"] = "A young child: short, simple sentences."
    if infant:
        prof["speech_style"] = f"Too young to give a history: the {who or 'adult with the child'} answers for the child."
    prof.update({k: v for k, v in (profile_extra or {}).items() if isinstance(v, str) and v.strip()})
    sections = [dict(s) for s in (template.get("chart_sections") or [])]
    who_text = f"{age_text} {noun}".strip() if age_text else noun
    art_a = "an" if who_text[:1] in "8" or who_text[:2] in ("11", "18") else "a"
    if comp:
        nps = [s for s in (ex.get("symptoms") or []) if _lead(_pronouns(s, nm)).startswith("I've had ") and len(s.split()) <= 9][:3]
        short = (nps[0] if len(nps) == 1 else ", ".join(nps[:-1]) + " and " + nps[-1]) if nps else re.split(r",|\s+and\s+(?:he|she|i)\b", comp)[0]
        short = re.sub(r"^(?:he|she|i)\s+(?:was|is|has|had)\s+", "", short, flags=re.I)
        tc = _cap(re.sub(r"^(?:a|an|the)\s+", "", _tidy(short) or comp, flags=re.I))
        if ex.get("complaint_lead") == "after":
            tc = re.sub(r",?\s*(?:about |around )?(?:an?|\d+|one|two|three|four|five|six|a few|several) (?:minutes?|hours?|days?|weeks?) (?:ago|earlier|before)$", "", tc, flags=re.I)
            tc = re.sub(r"^Falling (?:off|from|down|out of) (?:his|her|my|the|an?) ", "Fall from a ", tc)
            tc = re.sub(r"^Falling\b", "Fall", tc)
        title = f"{tc} in {art_a} {who_text}" if age_text else tc
    else:
        title = f"{_cap(who_text)} (presenting complaint not stated)"
    case = {
        "schema_version": 1, "case_id": "draft-" + slugify(name or template["id"]) + "-" + format(seed % 0xFFFFFF, "06x"), "version": 1, "status": "draft",
        "title": title,
        "origin": {"kind": "from_template", "condition_template": template["id"], "sim_seed": seed},
        "review": {"author": "Drafted from a free-text description (offline pattern extraction)", "needs_faculty_review": True, "synthetic": True,
                   "source_description": text[:2000], "taken_from_text": taken, "scaffolded": scaffolded, "missing": missing},
        "intended_learner": "Medical students and first-year emergency medicine residents",
        "learner_role": "Emergency medicine resident", "setting": "Emergency department treatment bay",
        "prebrief": f"You are the emergency medicine resident. {prof['name']}, {ex.get('age_text') or prof['age']}, has come in" + (f" with {comp}." if comp else ".") +
                    (f" {_cap(ex['accompanied_by']['source'])}." if who else "") + " Take a focused history, request what you need, and decide on a disposition.",
        "profile": prof,
        "faculty_truth": {"severity": sev, "teaching_points": [], **({"severity_basis": ex["severity_word"]} if ex.get("severity_word") else {})},
        "facts": facts,
        "chart": {"sections": sections, "artifacts": artifacts},
        "objectives": objectives,
        "rubric_id": (template.get("rubric_links") or {}).get("rubric_id", "default"),
        "sources": [{"source_id": "description", "title": "Faculty free-text description (see review.source_description)", "role": "teaching_artifact"},
                    {"source_id": "template", "title": f"Condition template catalog/conditions/{template['id']}.yaml, used for structure only", "role": "template"}],
        "default_negatives": False,         # decided below, once the coverage check has run
        "unknown_response": "I'm not sure about that, to be honest.",
    }
    case = fill_defaults(case)
    for f in case["facts"]:                 # clinical shorthand never reaches the patient's mouth
        if f.get("patient_answer_auto") and f.get("patient_answer"):
            f["patient_answer"] = lay(f["patient_answer"])
            if infant:
                f["patient_answer"] = _to_parent(f["patient_answer"], gender or "", who or "parent") if f["fact_id"] != "f.social.accompanied_by" else \
                    ("We're " if (who or "").endswith("s") else "I'm ") + {"male": "his", "female": "her"}.get(gender or "", "their") + " " + (who or "parent") + "."
            f["patient_answer"] = re.sub(r"(?<=[.!?] )([a-z])", lambda m_: m_.group(1).upper(), f["patient_answer"])
    if infant:
        case["answers_by"] = "accompanying adult"
        scaffolded.append("the child is too young to give a history, so every answer is worded as the accompanying adult speaking about the child")
    # ---- completeness guarantee: every sentence of the description is in the case, or named here
    for p in ex.get("unplaced", []):
        missing.append(f"not placed anywhere in the draft, add it by hand: \"{p}\"")
    cov = coverage_report(case, text[:2000])
    for item in cov["uncovered"]:
        missing.append("not fully captured, check this sentence: " + missing_words_text(item))
    case["review"]["coverage"] = {"sentences": cov["sentences"], "covered": cov["covered"], "uncovered": cov["uncovered"], "unplaced": list(ex.get("unplaced", []))}
    # A person knows whether they smoke. When every sentence of the description was placed, questions on topics the text never
    # touches get the ordinary "no" (the engine still refuses it wherever a fact or the source text overlaps the question). When
    # something was not placed, a flat "no" could contradict it, so the patient gives a softer "not that I've noticed" instead.
    complete = not cov["uncovered"] and not ex.get("unplaced")
    case["default_negatives"] = bool(complete)
    case["soft_negatives"] = not complete
    scaffolded.append("default answers: " + ("a plain \"no\" to yes/no questions on topics your text never mentions (everything in the text was placed)" if complete
                                             else "\"Not that I've noticed\" to yes/no questions on topics the draft does not hold, because part of your text was not placed"))
    problems = wording_problems(case)
    for pr in problems:
        missing.append("wording to review: " + pr)
    case["review"]["missing"] = missing
    return case, taken, scaffolded, missing
