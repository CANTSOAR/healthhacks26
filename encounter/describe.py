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
_AGE2 = re.compile(r"\b(?:age|aged)\s*(\d{1,3})\b|^[^,.]{2,40},\s*(\d{1,3})\s*,", re.I)
_SEX_AFTER_AGE = re.compile(r"(?:year[- ]old|years?[- ]old|yrs?[- ]old|month[- ]old|week[- ]old|yo|y/o|y\.o\.?)\s*,?\s*(?:[a-z\-]+\s+){0,2}?(woman|female|girl|lady|man|male|boy|gentleman|f|m)\b", re.I)
_FEMALE = r"woman|female|girl|lady|she|her|hers|herself|mrs|ms|miss"
_MALE = r"man|male|boy|gentleman|he|his|him|himself|mr"
_OCC3 = re.compile(r",\s*\d{1,3},\s+(?:an?\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|and|presenting|presents|comes|came)\b|[,.;])", re.I)
_NAME_LEAD = re.compile(r"^\s*(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?([A-Z][a-z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2})(?=\s*(?:,|\(|:|\bis\b|\bhas\b|\bcomes\b|\bpresents\b|\bwas\b|\barrives\b|\bcame\b))")
_NAME_SINGLE = re.compile(r"^\s*([A-Z][a-z'\-]{2,})(?=\s+is\s+an?\s+\d|,\s*(?:an?\s+)?\d{1,3}\b)")
_NAME_ANY = re.compile(r"\b(?:[Nn]amed|[Nn]ame is|[Cc]alled|[Pp]atient:?|Mrs?\.?|Ms\.?|Miss)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)")
_OCC1 = re.compile(r"(?:year[- ]old|years old|yo|y/o),?\s+(?:(?:fe)?male\s+|man\s+|woman\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|presenting|presents|comes|came|complaining|brought|arrives|has|had|in)\b|[,.;])", re.I)
_OCC2 = re.compile(r"\b(?:works? as|working as|employed as|job as|is|am)\s+(?:an?\s+)(?:retired\s+)?([a-z][a-z\- ]{2,40}?)(?=\s+(?:who|with|and|presenting|presents|comes|came)\b|[,.;]|$)", re.I)
_NOT_JOB = re.compile(r"^(man|woman|male|female|patient|lady|gentleman|boy|girl|person|adult|child|infant|baby|toddler|smoker|non-?smoker|diabetic|\d)", re.I)

_PRESENT_STRONG = re.compile(
    r"\b(?:comes? in (?:with|for|because of|after)|came in (?:with|for|because of|after)|presents? (?:with|for|after)|presenting (?:with|for|after)|"
    r"presented (?:with|for|after)|complains? of|complaining of|c/o|chief complaint(?: is| of|:)?|brought in (?:by [^,.;]{2,40}? )?(?:with|for|after)|"
    r"brought (?:to [^,.;]{2,30}? )?by [^,.;]{2,40}? (?:with|for|after)|arrives? with|arrived with|has had|have had|i've had|i've got|has been having|"
    r"have been having|i've been having|is having|am having|i'm having|suffering from|is experiencing|has developed|developed)\s+(.+?)" + _END, re.I | re.S)
_PRESENT_WEAK = re.compile(
    r"(?:\b(?:year[- ]old|years?[- ]old|yrs?[- ]old|month[- ]old|yo|y/o)(?:\s+[a-z\-]+){0,5}?\s+with|(?<![\w/.])\d{1,3}\s*[MF]\s+with|\b(?:has|have))\s+(.+?)" + _END, re.I | re.S)
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
    r"is reluctant to (?:admit|discuss|talk about|mention)|reluctant to (?:admit|discuss|talk about|mention)|"
    r"is embarrassed (?:about|to admit|by)|embarrassed (?:about|to admit|by)|ashamed (?:of|to admit)|secretly|"
    r"avoids? (?:talking about|mentioning|discussing)|minimi[sz]es|downplays|under-?reports|not forthcoming about|"
    r"(?:has not|have not|hasn'?t|haven'?t) told (?:anyone|anybody|(?:his|her|my|the) \w+)|keeps quiet about)\b\s*(?:that\s+|to\s+|about\s+|the fact that\s+)?(.+?)" + _END, re.I | re.S)
_HIDE_DENIES = re.compile(r"\bdenies\s+((?:[a-z]+ing)\s+(?:\S+\s+){2,}?\S+?)" + _END, re.I | re.S)
_HIDE_AFTER = re.compile(
    r"(?:^|(?<=[.;]\s))\s*(?:" + _SUBJ + r"\s+)?((?:has|have|had|is|am|was|takes?|uses?|drinks?|smokes?|stopped|started)\b[^.;]{3,160}?),?\s+(?:but|and|though|although)\s+"
    r"(?:(?:she|he|i)\s+)?(?:(?:has not|have not|hasn'?t|haven'?t|did not|didn'?t|does not|doesn'?t|do not|don'?t|won'?t|will not|never)\s+"
    r"(?:told|tell|mentioned|mention|admitted|admit)\b[^.;]{0,60}?|(?:minimi[sz]es?|downplays?|under-?reports?|hides?|conceals?|denies|deny|plays? down)\s+(?:it|this|that)\b[^.;]{0,40}?)"
    + _END, re.I | re.S | re.M)
_STOPPED = re.compile(r"\b(?:stopped|quit|not|isn'?t|hasn'?t been|skips?|skipping|misses|missing)\s+(?:taking\s+|been taking\s+)?(?:(?:her|his|their|the|my)\s+)?"
                      r"([a-z][a-z\- ]{2,40}?(?:pills?|tablets?|medication|medicine|meds|inhalers?|insulin|injections?|thinners?|drops|patch(?:es)?|statins?|antibiotics?))\b", re.I)
_VITALS = [
    ("blood_pressure", "Blood pressure", "mmHg", re.compile(r"\b(?:bp|blood[- ]pressure)\s*(?:is|was|of|:|=)?\s*(\d{2,3}\s*/\s*\d{2,3})(?:\s*mm\s*hg)?", re.I)),
    ("heart_rate", "Heart rate", "beats/min", re.compile(r"\b(?:hr|heart[- ]rate|pulse)\s*(?:is|was|of|:|=)?\s*(\d{2,3})\b(?:\s*(?:bpm|beats per minute|/min))?", re.I)),
    ("temperature", "Temperature", "", re.compile(r"\b(?:temp(?:erature)?|fever(?: of)?)\s*(?:is|was|of|:|=)?\s*(\d{2,3}(?:\.\d)?)\s*(?:°|degrees)?\s*([CF])?\b", re.I)),
    ("spo2", "Oxygen saturation", "%", re.compile(r"\b(?:spo2|sp02|o2 sats?|sats?|oxygen saturations?|saturations?)\s*(?:is|are|was|of|:|=)?\s*(\d{2,3})\s*%?(?:\s*on (?:room air|ra|\d+ ?l(?:itres?)?(?: of)?(?: oxygen)?))?", re.I)),
    ("respiratory_rate", "Respiratory rate", "breaths/min", re.compile(r"\b(?:rr|resp(?:iratory)?[- ]rate)\s*(?:is|was|of|:|=)?\s*(\d{1,2})\b", re.I)),
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
                           r"patch(?:es)?|eye drops|drops|statins?|antibiotics?|painkillers?|steroids?|injections?|antidepressants?|laxatives?|antacids?|nebuli[sz]ers?)\b", re.I)
_DOSE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|micrograms?|g|units?|iu|ml|puffs?)\b", re.I)
_MED_TRIGGER = re.compile(r"\b(?:takes?|taking|is on|am on|i'm on|on|prescribed|uses?|using|started on|(?:regular |current |home )?(?:medications?|meds|medicines)(?: include| are|:)?)\s+", re.I)
_ALLERGY = re.compile(r"\ballerg(?:ic|y|ies)\s*(?:to|:)\s*(.+?)" + _END, re.I | re.S)
_NO_ALLERGY = re.compile(r"\bno (?:known )?(?:drug |medication )?allergies\b|\bnkda\b|\bnka\b", re.I)
_RELATIVE = r"mother|father|mom|mum|mummy|mommy|dad|daddy|parents?|grandmother|grandfather|grandma|grandpa|grandparents?|wife|husband|partner|girlfriend|boyfriend|" \
            r"daughter|son|sister|brother|aunt|uncle|friend|neighbou?r|carer|caregiver|guardian|foster (?:mother|father|parents?)"
_ACCOMPANY = re.compile(rf"\b(?:brought (?:in |to [^,.;]{{2,30}}? )?by|accompanied by|comes? (?:in )?with|came (?:in )?with|attends? with|here with|together with)\s+"
                        rf"(?:his|her|their|my|the|a)\s+((?:{_RELATIVE})(?:\s+and\s+(?:{_RELATIVE}))?)\b", re.I)
_LIVES = re.compile(r"\b(lives? (?:alone|with [^.;,]{2,40}|in [^.;,]{2,40})|(?:is|am) (?:married|widowed|divorced|single|homeless)[^.;,]{0,30})", re.I)
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
                      r"depression|anxiety|high cholesterol|kidney disease|migraines?|arthritis|cancer|hiv|angina)[^.;,]{0,50})", re.I)
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
COVER_SYMPTOM = "No... not really. Nothing worth mentioning."
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
    (r"faint|pass(?:ed|ing)? out|black(?:ed|ing)? out|collaps", ["faint", "fainted", "passed out", "blacked out", "collapse", "collapsed"]),
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
_BASE_VERBS = set("smoke drink take live work use vape have am feel get need want eat sleep walk cough stopped started noticed used tried took had got".split())
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


def _lead(s: str, past: bool = False) -> str:
    """Give a clause with no subject one: "feeling lightheaded" -> "I feel lightheaded", "black stools" -> "I've had black stools"."""
    low = s.lower()
    w = low.split(" ", 1)
    first, rest = w[0], (" " + s.split(" ", 1)[1] if len(w) > 1 else "")
    if re.match(r"^(i|i'm|i've|i'd|i'll|my|yes|there|it|it's|that|nobody|no one|we)\b", low):
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
    s = _lead(_pronouns(s, name), past)
    s = re.sub(r"\bI've had (?:a )?history of\b", "I have a history of", s)
    s = re.sub(r"\bI have (been|had|not|never|got)\b", r"I've \1", s)
    s = re.sub(r"\bI've had (.+\b(?:in (?:19|20)\d\d|ago|last (?:year|month|week))\b)", r"I had \1", s)
    return lay(s[0].upper() + s[1:] + ".")


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
            self.work = self.work[:a] + re.sub(r"[^.;\n]", " ", self.work[a:b]) + self.work[b:]


def extract(text: str) -> dict:
    """Pull out only what the description states."""
    t = re.sub(r"[ \t]+", " ", (text or "").strip())
    T = _Text(t)
    out: dict = {"vitals": [], "labs": [], "concealed": [], "pmh": [], "meds": [], "allergies": [], "social": [], "concerns": [], "symptoms": [], "negatives": [],
                 "leftover": [], "unplaced": [], "text": t}
    low = t.lower()

    # ---- 1. concealed elements first, so their text is not re-read as ordinary history
    for rx in (_HIDE_AFTER, _HIDE, _HIDE_DENIES):
        for m in rx.finditer(T.work):
            phrase = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")
            if len(phrase) < 4 or not re.search(r"[a-z]{3}", phrase):
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
    m = _NAME_LEAD.search(t) or _NAME_ANY.search(t) or _NAME_SINGLE.search(t)
    if m and m.group(1).split()[0] not in ("A", "An", "The", "This", "Patient", "She", "He", "I", "Brought", "Presents", "History", "No"):
        out["name"] = m.group(1).strip()
        demo_spans.append((m.start(), m.end()))
    for rx in (_OCC1, _OCC3, _OCC2):
        m = rx.search(t)
        if m:
            job = m.group(1).strip()
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
            val = m.group(1).replace(" ", "")
            u = unit
            if key == "temperature":
                if not 30 <= float(val) <= 110:
                    continue
                u = (m.group(2) or ("F" if float(val) > 45 else "C")).upper()
            out["vitals"].append({"key": key, "label": label, "value": val, "unit": u, "source": m.group(0).strip()})
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
                if not sub or re.match(rf"^(?:{_SUBJ}|takes?|is|has|on)\b", sub, re.I) or len(sub.split()) > 6:
                    items = items if items else []
                    break
                items.append(re.sub(r"^(?:to|and)\s+", "", sub))
            else:
                end = m.start(1) + piece.end()
                continue
            break
        if items:
            out["allergies"] += [i for i in items if i not in out["allergies"]]
            T.claim(m.start(), end)
    for m in list(_MED_TRIGGER.finditer(T.work)):
        tail = re.match(r"(.+?)" + _END, T.work[m.end():], re.S)
        if not tail or not T.work[m.start():m.end()].strip():
            continue
        items, end = [], m.end()
        for piece in re.finditer(r"[^,]+", tail.group(1)):
            ok = True
            for sub in re.split(r"\s+and\s+|\s*\+\s*", piece.group(0)):
                sub = re.sub(r"^(?:and|also|his|her|my|their)\s+", "", sub.strip(), flags=re.I)
                if sub and _is_drug(sub):
                    items.append(sub)
                elif sub:
                    ok = False
                    break
            if not ok:
                break
            end = m.end() + piece.end()
        if items:
            for it in items:
                ind = re.search(r"\s+for\s+(?:his |her |my |the )?([a-z][a-z0-9 \-]{3,40})$", it, re.I)
                if ind and not re.search(r"pain|ache|sleep|cough|cold|fever|nausea|days?|weeks?|months?|years?|a while", ind.group(1), re.I):
                    out.setdefault("indications", []).append(ind.group(1).strip())
                if it not in out["meds"]:
                    out["meds"].append(it)
            T.claim(m.start(), end)

    # ---- 5. who came with the patient; presenting complaint
    m = _ACCOMPANY.search(T.work)
    if m:
        out["accompanied_by"] = {"who": m.group(1).lower(), "source": re.sub(r"\s+", " ", m.group(0)).strip()}

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
        out["complaint"] = comp
        if dur:
            out["duration"] = dur
        parts = [p.strip() for p in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+(?:also\s+)?", comp) if p.strip()]
        merged: list[str] = []
        for p in parts:                 # "pain and swelling in his right calf" is one thing, not two
            if merged and len(merged[-1].split()) <= 2 and not re.search(r"\b(?:in|of|on|when|with|after)\b", merged[-1]) and re.search(r"\b(?:in|of|on)\b", p) \
                    and len(parts) == 2:
                merged[-1] = merged[-1] + " and " + p
            else:
                merged.append(p)
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
            if len(words) >= 2 or (len(words) == 1 and len(words[0]) >= 6):
                (out["leftover"] if (whole or len(words) >= 3) and not demo.search(p) else out["unplaced"]).append(p)
    hi, lo = _SEVERITY_HI.search(low), _SEVERITY_LO.search(low)
    out["severity"] = "severe" if hi else ("mild" if lo else "moderate")
    if hi or lo:
        out["severity_word"] = (hi or lo).group(1)
    return out


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
    who = (ex.get("accompanied_by") or {}).get("who")
    adult_with = who and re.search(r"mother|father|mom|mum|dad|parent|grand|guardian|carer|caregiver|aunt|uncle|foster", who)
    facts: list[dict] = []
    used: set[str] = set()
    nm = name or ""

    def fid(cat: str, slug: str) -> str:
        base = f"f.{cat}.{slugify(slug, 'item').replace('-', '_')[:30].strip('_')}"
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
        if lead == "after" and not sents:
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
            ans = first_person(phrase, nm)
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
        ans = f"I have {_pronouns(p, nm)}." if not re.match(r"^(a|an)\b", p) else f"I{' ' if re.search(r'(?:19|20)[0-9][0-9]|ago', p) else chr(39) + 've '}had {_pronouns(p, nm)}."
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
        said = re.sub(r"\s*,\s*(?:or\s+|and\s+)?|\s+and\s+", " or ", _pronouns(items, nm))
        facts.append({"fact_id": fid("ros", "no " + items), "category": "ros", "statement": _cap(neg["source"]), "patient_knows": True,
                      "patient_answer": f"No, no {said}.", "topics": topics_for(items, 5), "disclosure": {"rule": "if_asked"}, "chart_section": "ros",
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
            f["topics"] += [s for s in syn if s not in f["topics"]]
            symptomish = bool(syn) and not keys and not drugs_named
            f["cover_answer"] = COVER_CHILD if young else (COVERS[keys[0]] if keys else ("No, nothing like that." if drugs_named else (COVER_SYMPTOM if symptomish else COVER_GENERIC)))
            f["disclosure"] = {"rule": "after_rapport", "rapport_needed": 3}
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
    else:
        missing.append("medications (none stated: the patient will say they are not sure unless you add them)")
    if ex.get("allergies"):
        items = ex["allergies"]
        said = []
        for a in items:
            r = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", a)
            if r:
                react = r.group(2).strip()
                how = {"rash": "it gives me a rash", "hives": "it gives me hives", "vomiting": "it makes me vomit", "nausea": "it makes me feel sick",
                       "swelling": "it makes me swell up", "anaphylaxis": "I had a very bad reaction", "itching": "it makes me itch"}.get(react.lower(), f"I get {react}")
                said.append(f"{r.group(1).strip()}, {how}")
            else:
                said.append(a)
        ans = "I'm allergic to " + (said[0] if len(said) == 1 else ", ".join(said[:-1]) + ", and " + said[-1]) + "."
        facts.append({"fact_id": fid("allergies", items[0]), "category": "allergies", "statement": ("Allergy: " if len(items) == 1 else "Allergies: ") + "; ".join(items),
                      "patient_knows": True, "patient_answer": told(_pronouns(ans, nm)), "topics": ["allergies"] + content_words(" ".join(items), 6),
                      "disclosure": {"rule": "if_asked"}, "chart_section": "allergies", "polarity": "positive", "critical": True, "patient_answer_auto": True})
        for a in items:
            taken.append(f"allergy: {a}")
    elif ex.get("allergy_none"):
        facts.append({"fact_id": fid("allergies", "nkda"), "category": "allergies", "statement": "No known drug allergies", "patient_knows": True,
                      "patient_answer": told("No allergies that I know of."), "topics": ["allergies"], "disclosure": {"rule": "if_asked"}, "chart_section": "allergies",
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
        if cat in ("pmh",):
            ans = told(ans)
        # the family category already answers to "any family history?"; the companion's own word ("mother") must not pull this fact into
        # "is your mum here with you?"
        topics = [w for w in content_words(s, 6) if rel_rx.fullmatch(w) and w not in (who or "")] if cat == "family" else topics_for(s, 3)
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

    if child:
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
    prof.update({k: v for k, v in (profile_extra or {}).items() if isinstance(v, str) and v.strip()})
    sections = [dict(s) for s in (template.get("chart_sections") or [])]
    who_text = f"{age_text} {noun}".strip() if age_text else noun
    art_a = "an" if who_text[:1] in "8" or who_text[:2] in ("11", "18") else "a"
    if comp:
        tc = _cap(re.sub(r"^(?:a|an|the)\s+", "", comp, flags=re.I))
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
        # a patient drafted from free text never answers "no" by default: what the text did not say is unknown, not absent
        "default_negatives": False,
        "unknown_response": "I'm not sure about that, to be honest.",
    }
    case = fill_defaults(case)
    for f in case["facts"]:                 # clinical shorthand never reaches the patient's mouth
        if f.get("patient_answer_auto") and f.get("patient_answer"):
            f["patient_answer"] = lay(f["patient_answer"])
    # ---- completeness guarantee: every sentence of the description is in the case, or named here
    for p in ex.get("unplaced", []):
        missing.append(f"not placed anywhere in the draft, add it by hand: \"{p}\"")
    cov = coverage_report(case, text[:2000])
    for item in cov["uncovered"]:
        missing.append("not fully captured, check this sentence: " + missing_words_text(item))
    case["review"]["coverage"] = {"sentences": cov["sentences"], "covered": cov["covered"], "uncovered": cov["uncovered"], "unplaced": list(ex.get("unplaced", []))}
    case["review"]["missing"] = missing
    return case, taken, scaffolded, missing
