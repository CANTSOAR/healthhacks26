"""Shared topic taxonomy for the offline intent matcher.

A fact's `topics` may hold taxonomy keys from TOPICS (expanded to the phrases below) and/or
free trigger phrases written by the case author. Because the taxonomy is shared, a case authored
by faculty through the API works with no code change: tag a fact `smoking` or simply name it
`f.social.smoking` and every paraphrase below counts as asking about it.

All wording here is authored for this project (synthetic, not validated).
"""
from __future__ import annotations

import re

# topic key -> trigger phrases (lower case, no apostrophes)
TOPICS: dict[str, list[str]] = {
    # ---- opening / chief complaint / HPI dimensions
    "chief_complaint": [
        "what brings you", "what brought you", "brings you in", "brought you in", "why are you here",
        "why did you come", "what happened", "whats going on", "what is going on", "whats wrong",
        "what seems to be the problem", "what seems to be the trouble", "how can i help",
        "what can i do for you", "main concern", "main problem", "chief complaint", "reason for your visit",
        "reason for coming", "tell me what happened", "whats been going on", "what has been going on",
        "how are you feeling", "how do you feel", "whats bothering you", "what is bothering you",
        "tell me about your symptoms", "what symptoms",
    ],
    "onset": [
        "when did it start", "when did this start", "when did that start", "when did the", "when did your",
        "how did it start", "how did this start", "when did it begin", "when did you first notice",
        "first notice", "started when", "how long ago", "since when", "what were you doing when",
        "come on suddenly", "sudden or gradual", "suddenly or gradually", "onset", "when did it happen",
        "when did this happen", "what time did",
    ],
    "duration": [
        "how long", "how long has", "how long have", "how many days", "how many hours", "how many weeks",
        "constant or", "come and go", "comes and goes", "all the time", "intermittent", "how often",
        "how long does it last", "duration", "every day",
    ],
    "character": [
        "what does it feel like", "what does the pain feel like", "feel like", "describe the pain",
        "describe it", "describe the", "what kind of pain", "type of pain", "sharp or dull", "sharp", "dull",
        "pressure", "burning", "stabbing", "crushing", "tightness", "aching", "character", "quality of the pain",
        "what is the pain like", "whats the pain like", "throbbing", "cramping",
    ],
    "location": [
        "where is the pain", "where does it hurt", "where exactly", "point to", "show me where",
        "which side", "where do you feel", "location", "whereabouts", "where is it",
    ],
    "severity": [
        "how bad", "how severe", "scale of", "out of ten", "out of 10", "one to ten", "1 to 10", "rate the pain",
        "rate your pain", "how much does it hurt", "how painful", "severity", "worst pain", "how intense",
    ],
    "radiation": [
        "does it go anywhere", "go anywhere else", "does it spread", "spread anywhere", "radiate", "radiation",
        "move anywhere", "travel anywhere", "shoot down", "into your arm", "into your jaw", "to your back",
        "down your leg", "anywhere else", "go anywhere", "to your arm", "to your jaw", "to your shoulder", "travel to", "spread to",
        "move to", "goes to", "go to your",
    ],
    "aggravating": [
        "what makes it worse", "anything make it worse", "makes it worse", "make it worse", "worse when",
        "worse with", "bring it on", "brings it on", "trigger", "triggers", "aggravate", "worse on exertion",
        "worse when you breathe", "worse lying", "worse after eating", "worse with movement", "pain worse", "it worse",
        "worse when you move", "worse when you", "symptoms worse",
    ],
    "relieving": [
        "what makes it better", "anything make it better", "makes it better", "make it better", "better when",
        "better with", "anything help", "does anything help", "relieve", "relief", "ease it", "eases it",
        "tried anything", "taken anything for it", "did you take anything", "what have you tried", "pain better", "it better",
        "take for the pain", "take for it", "taking for the pain", "anything for the pain", "what did you take",
    ],
    "associated_symptoms": [
        "any other symptoms", "other symptoms", "anything else going on", "anything else with it",
        "anything else bothering", "along with", "associated symptoms", "anything else you noticed",
        "what else", "anything else",
    ],
    "previous_episodes": [
        "happened before", "had this before", "ever had this", "first time", "previous episodes", "similar episode",
        "like this before", "ever happen before", "is this new",
    ],
    "delay": [
        "why did you wait", "wait so long", "waited so long", "come in sooner", "come sooner", "didnt you come", "why now",
        "what made you come in today", "put off coming", "took you so long", "why today",
    ],
    "patient_concerns": [
        "what are you worried", "worried about", "what do you think is going on", "what do you think it is",
        "what concerns you", "biggest concern", "what scares you", "afraid of", "what are you hoping",
        "what would you like", "your expectations", "what matters most", "what do you think caused",
    ],
    # ---- background
    "pmh": [
        "medical history", "medical problems", "medical conditions", "health problems", "health conditions",
        "past medical", "any conditions", "chronic conditions", "chronic illness", "diagnosed with",
        "ever been diagnosed", "any illnesses", "other health issues", "underlying conditions", "see a doctor for",
        "health history", "been told you have",
    ],
    "hypertension": ["high blood pressure", "hypertension", "blood pressure problems"],
    "diabetes": ["diabetes", "diabetic", "blood sugar", "sugar problems", "sugars"],
    "cholesterol": ["cholesterol", "lipids", "high cholesterol"],
    "heart_disease": ["heart problems", "heart disease", "heart attack", "heart condition", "heart trouble",
                      "stent", "angina", "heart failure"],
    "lung_disease": ["asthma", "copd", "emphysema", "lung problems", "lung disease", "breathing problems"],
    "psh": [
        "surgeries", "surgery", "operations", "operation", "operated", "surgical history", "ever had surgery",
        "been under anesthesia", "procedures", "appendix out", "gallbladder out",
    ],
    "hospitalizations": ["hospitalized", "hospitalised", "admitted to hospital", "been in the hospital",
                         "stay in hospital", "hospital stays", "emergency room before", "er visits"],
    "medications": [
        "medications", "medication", "medicines", "medicine", "meds", "pills", "tablets", "prescriptions",
        "prescription", "prescribed", "what do you take", "are you taking any", "what are you taking", "taking anything", "take anything",
        "on any", "drugs do you take", "over the counter", "supplements", "vitamins", "herbal", "inhaler",
        "blood thinners", "blood thinner", "birth control",
    ],
    "adherence": [
        "taking them", "take them every day", "miss doses", "missed doses", "miss any", "skip", "skipped",
        "taking it as prescribed", "as prescribed", "run out", "ran out", "stopped taking", "adherence",
        "remember to take", "how often do you actually take", "take them regularly", "taking them regularly",
        "take it regularly", "taking it regularly",
    ],
    "progression": [
        "getting worse", "got worse", "gotten worse", "getting better", "got better", "gotten better",
        "changed since", "worse since", "better since", "improving", "progressing", "stayed the same", "staying the same", "worse over time",
    ],
    "allergies": [
        "allergies", "allergy", "allergic", "reactions to", "reaction to any", "bad reaction", "drug allergies", "drug allergy",
        "medication allergies", "allergic to any medications", "allergic to any drugs", "allergic to any medicines",
        "penicillin", "latex", "drug allergies", "food allergies",
    ],
    "family_history": [
        "family history", "run in your family", "runs in your family", "run in the family", "runs in the family",
        "your parents", "your father", "your mother", "your dad", "your mom", "siblings", "brothers or sisters",
        "anyone in your family", "family members", "relatives", "in the family", "your family health", "in your family",
        "your family history", "family medical", "family have", "family had", "family has",
        "parents still alive", "died young",
    ],
    # ---- social
    "social_history": ["social history", "tell me about yourself", "tell me a bit about yourself",
                       "about your life", "your lifestyle", "lifestyle", "habits", "about your home life"],
    "smoking": [
        "smoke", "smoker", "smoking", "cigarettes", "cigarette", "tobacco", "vape", "vaping", "e-cigarettes",
        "nicotine", "packs a day", "pack a day", "cigars", "chew tobacco",
    ],
    "alcohol": [
        "alcohol", "drink", "drinking", "drinks", "drinker", "beer", "wine", "liquor", "spirits", "booze",
        "how much do you drink", "how many drinks", "drink alcohol", "last drink", "drunk", "binge",
        "whiskey", "vodka", "cocktails",
    ],
    "drugs": [
        "drugs", "recreational", "substances", "substance use", "street drugs", "illicit", "illegal drugs",
        "marijuana", "cannabis", "weed", "cocaine", "heroin", "opioids", "meth", "pills not prescribed",
        "use anything else", "injected", "inject", "party drugs", "edibles", "get high",
    ],
    "sexual_history": [
        "sexually active", "sexual history", "sexual partners", "partners", "sex", "condom", "condoms",
        "protection", "sti", "std", "sexually transmitted", "contraception", "sexual health", "hiv test",
        "men women or both", "intercourse",
    ],
    "pregnancy": ["pregnant", "pregnancy", "last period", "last menstrual", "periods", "menstrual", "lmp"],
    "occupation": [
        "for work", "do you work", "your work", "at work", "kind of work", "work as", "where do you work", "your job",
        "a job", "occupation", "what do you do for a living", "do for a living", "employed", "employment",
        "your career", "profession", "are you working", "are you retired", "in school", "what do you do", "study", "studying",
        "your major", "your studies",
    ],
    "living_situation": [
        "who do you live with", "live with", "live alone", "living situation", "where do you live", "at home",
        "home situation", "housing", "who is at home", "whos at home", "anyone at home", "support at home",
        "married", "partner", "spouse", "kids", "children", "family nearby", "who helps you", "support system",
        "do you have support", "stairs at home",
    ],
    "diet": [
        "diet", "what do you eat", "eating habits", "typical day of eating", "meals", "food", "salt",
        "sodium", "fruits and vegetables", "vegetables", "fast food", "what you eat", "nutrition", "caffeine",
        "coffee", "energy drinks", "snacks", "fluid intake", "how much water",
    ],
    "exercise": ["exercise", "physical activity", "active", "work out", "workout", "gym", "sports", "walk",
                 "walking", "how far can you walk", "stairs", "activity level"],
    "mood": [
        "mood", "depressed", "depression", "feeling down", "sad", "hopeless", "anxious", "anxiety", "stress",
        "stressed", "how are you coping", "coping", "how have you been feeling emotionally", "emotionally",
        "your spirits", "little interest", "overwhelmed", "worried", "nervous", "mental health",
    ],
    "self_harm": ["hurting yourself", "harm yourself", "suicide", "suicidal", "end your life", "kill yourself",
                  "thoughts of death", "better off dead", "self harm", "hurt yourself"],
    "safety_at_home": ["feel safe", "safe at home", "anyone hurting you", "violence", "afraid of anyone",
                       "threatened", "abuse"],
    "sleep": ["sleep", "sleeping", "insomnia", "trouble sleeping", "wake up at night", "waking at night",
              "how many pillows", "pillows", "tired in the morning", "snore", "snoring"],
    "travel": ["travel", "travelled", "traveled", "trip", "abroad", "out of the country", "long flight",
               "flights", "long car ride", "sick contacts", "anyone sick around you", "been around anyone sick",
               "exposure", "exposed"],
    "vaccination": ["vaccine", "vaccines", "vaccinated", "vaccination", "flu shot", "immunizations",
                    "immunisations", "tetanus", "covid shot", "boosters"],
    "health_understanding": [
        "what do you understand", "your understanding", "what have you been told", "what did your doctor tell you",
        "what do you know about", "do you know what", "explain to me what", "make sense to you",
        "understand your condition", "understand your diagnosis", "what does that mean to you",
    ],
    "healthcare_trust": ["trust", "previous experiences with doctors", "experience with doctors",
                         "experience with hospitals", "treated badly", "how have doctors treated you",
                         "feel about being here", "feel about hospitals", "comfortable with", "bad experience"],
    "insurance_access": ["insurance", "afford", "cost of", "pay for", "pharmacy", "transportation",
                         "get to appointments", "primary care doctor", "regular doctor", "family doctor", "pcp"],
    # ---- symptoms / review of systems
    "pain_chest": ["chest pain", "chest pains", "pain in your chest", "chest discomfort", "chest tightness",
                   "chest pressure", "tight chest", "chest hurt", "chest hurts", "your chest"],
    "palpitations": ["palpitations", "heart racing", "racing heart", "heart pounding", "skipping beats",
                     "skipped beats", "fluttering", "heartbeat", "heart beating fast"],
    "sob": ["short of breath", "shortness of breath", "trouble breathing", "difficulty breathing", "breathless",
            "breathlessness", "hard to breathe", "catch your breath", "out of breath", "winded", "your breathing",
            "breathing okay", "dyspnea"],
    "orthopnea": ["lying flat", "lie flat", "lying down", "prop yourself", "wake up gasping", "wake up short of breath"],
    "cough": ["cough", "coughing", "phlegm", "sputum", "mucus", "coughing up", "bringing anything up",
              "coughing up blood", "blood when you cough"],
    "wheeze": ["wheeze", "wheezing", "whistling", "chest tight"],
    "swelling": ["swelling", "swollen", "puffy", "ankles", "legs swollen", "leg swelling", "edema",
                 "calf pain", "calf", "shoes tight", "fluid"],
    "fever": ["fever", "fevers", "temperature", "feverish", "chills", "shivering", "shakes", "night sweats",
              "sweats", "rigors", "hot and cold", "felt hot"],
    "sweating": ["sweating", "sweaty", "clammy", "diaphoresis", "break out in a sweat", "cold sweat"],
    "fatigue": ["tired", "fatigue", "fatigued", "exhausted", "no energy", "energy level", "energy levels",
                "weak all over", "worn out", "run down", "lethargic"],
    "weight_change": ["weight loss", "lost weight", "losing weight", "weight gain", "gained weight",
                      "weight change", "your weight", "clothes fit", "weigh"],
    "appetite": ["appetite", "eating okay", "eating normally", "hungry", "eating less", "able to eat",
                 "full quickly", "fill up fast", "early satiety", "feel full"],
    "nausea_vomiting": ["nausea", "nauseous", "nauseated", "sick to your stomach", "vomit", "vomiting",
                        "vomited", "throw up", "throwing up", "threw up", "queasy", "keep food down",
                        "keep anything down", "blood in your vomit"],
    "pain_abdomen": ["belly pain", "stomach pain", "abdominal pain", "tummy pain", "stomach ache",
                     "pain in your belly", "pain in your stomach", "pain in your abdomen", "stomach hurt",
                     "belly hurt", "your stomach", "your belly", "your abdomen", "cramps"],
    "bowel": ["bowel", "bowels", "bowel movements", "bowel movement", "stool", "stools", "poop", "pooping",
              "diarrhea", "diarrhoea", "loose stools", "constipation", "constipated", "blood in your stool",
              "black stools", "tarry", "going to the bathroom", "bathroom habits", "passing gas", "pass gas",
              "regular bowel", "bowels regular", "regular with your bowels", "toilet"],
    "heartburn": ["heartburn", "reflux", "indigestion", "acid", "sour taste", "burping", "trouble swallowing",
                  "difficulty swallowing", "swallowing"],
    "urinary": ["urinate", "urinating", "urination", "urine", "pee", "peeing", "burning when you", "passing water",
                "how often do you go", "frequency", "urgency", "blood in your urine", "waterworks",
                "getting up at night to", "flank", "discharge", "bladder"],
    "headache": ["headache", "headaches", "head hurt", "head hurts", "migraine", "migraines", "pain in your head",
                 "worst headache", "your head"],
    "dizziness": ["dizzy", "dizziness", "lightheaded", "light headed", "lightheadedness", "room spinning",
                  "spinning", "vertigo", "off balance", "unsteady", "balance", "woozy", "faint"],
    "syncope": ["pass out", "passed out", "passing out", "black out", "blacked out", "blackout", "fainted",
                "faint", "lose consciousness", "lost consciousness", "knocked out", "collapse", "collapsed"],
    "weakness_numbness": ["weakness", "weak", "numb", "numbness", "tingling", "pins and needles", "cant feel",
                          "lost feeling", "heavy arm", "heavy leg", "arm weak", "leg weak", "drooping", "droop",
                          "dropping things", "clumsy", "paralysis", "cant move"],
    "speech_vision": ["speech", "slurred", "slurring", "trouble speaking", "trouble talking", "finding words",
                      "vision", "blurry", "blurred", "double vision", "seeing double", "lost vision", "eyesight",
                      "trouble seeing", "confused", "confusion", "memory", "trouble understanding"],
    "seizure": ["seizure", "seizures", "convulsion", "convulsions", "fit", "shaking episode", "tongue biting",
                "bit your tongue", "lost control of your bladder"],
    "neck_stiffness": ["stiff neck", "neck stiffness", "neck pain", "light bother", "lights bother",
                       "sensitive to light", "photophobia"],
    "rash": ["rash", "rashes", "skin changes", "itching", "itchy", "hives", "skin", "bruising", "bruises",
             "redness", "sores", "wound", "wounds"],
    "bleeding": ["bleeding", "bleed", "blood", "bled", "bruise easily", "nosebleeds"],
    "pain_back": ["back pain", "pain in your back", "your back", "lower back", "low back", "back hurt",
                  "back hurts", "spine"],
    "pain_joint": ["joint pain", "joints", "knee", "ankle", "wrist", "shoulder", "hip", "elbow", "stiffness",
                   "morning stiffness", "swollen joint", "bear weight", "put weight on", "walk on it",
                   "range of motion", "move it"],
    "injury_mechanism": ["how did it happen", "how did you fall", "how did you hurt", "how did you injure",
                         "what happened exactly", "mechanism", "did you fall", "fall", "fell", "twist", "twisted",
                         "hit your head", "accident", "how fast", "seatbelt", "helmet", "land", "landed",
                         "heard a pop", "pop or crack"],
    "red_flags_back": ["saddle", "numbness between your legs", "lose control of your bowels",
                       "lose control of your bladder", "trouble urinating", "incontinence", "foot drop",
                       "numbness in your groin", "groin numb"],
    "ent": ["sore throat", "throat", "ear pain", "ears", "runny nose", "congestion", "stuffy", "sinus",
            "sneezing", "hoarse", "swollen glands"],
    "withdrawal": ["shaky", "shakes", "tremor", "tremors", "trembling", "hands shake", "jittery", "sweats when you stop",
                   "withdrawal", "when you stop drinking", "seeing things", "hearing things", "hallucinations"],
    "hand_dominance": ["right handed", "left handed", "dominant hand", "which hand do you write"],
    "last_meal": ["last eat", "last ate", "last meal", "anything to eat today", "eaten today", "last had anything to eat"],
    "identity": ["your name", "what should i call you", "how old are you", "your age", "date of birth",
                 "confirm your name", "full name", "birthday", "what do you like to be called"],
}

# Fact category -> taxonomy keys every fact in that category implicitly answers to (weak weight),
# so a broad question ("any medical problems?") reaches facts the author did not tag.
CATEGORY_TOPICS: dict[str, list[str]] = {
    "identity": ["identity"],
    "chief_complaint": ["chief_complaint"],
    "pmh": ["pmh"],
    "medications": ["medications"],
    "allergies": ["allergies"],
    "family": ["family_history"],
    "social": ["social_history"],
}

# Default chart section per fact category (used when a fact names no chart_section).
CATEGORY_SECTION: dict[str, tuple[str, str]] = {
    "identity": ("identity", "Patient details"),
    "chief_complaint": ("hpi", "History of present illness"),
    "hpi": ("hpi", "History of present illness"),
    "pmh": ("pmh", "Past medical history"),
    "medications": ("medications", "Medications"),
    "allergies": ("allergies", "Allergies"),
    "social": ("social", "Social history"),
    "family": ("family", "Family history"),
    "ros": ("ros", "Review of systems"),
    "exam": ("exam", "Physical examination"),
    "vitals": ("vitals", "Vital signs"),
    "lab": ("labs", "Laboratory results"),
    "imaging": ("imaging", "Imaging and ECG"),
    "diagnosis": ("assessment", "Assessment"),
    "risk": ("risk", "Risk factors"),
    "concealed": ("social", "Social history"),
}

# Orders / exams a learner can request by name. Free-text turns are matched against these too
# ("can I get an ECG?", "let me listen to your chest"). Key = canonical request string.
REQUEST_ALIASES: dict[str, list[str]] = {
    "order:ecg": ["ecg", "ekg", "electrocardiogram", "12 lead", "heart tracing"],
    "order:troponin": ["troponin", "trop", "cardiac enzymes", "cardiac markers", "heart enzymes"],
    "order:cbc": ["cbc", "complete blood count", "full blood count", "fbc", "blood count", "white count", "hemoglobin"],
    "order:bmp": ["bmp", "basic metabolic", "metabolic panel", "electrolytes", "chem 7", "chemistry", "kidney function",
                  "creatinine", "renal function", "u and e", "cmp", "comprehensive metabolic"],
    "order:lft": ["lft", "lfts", "liver function", "liver panel", "liver enzymes", "hepatic panel", "ggt", "ast", "alt"],
    "order:lipase": ["lipase", "amylase", "pancreatic enzymes"],
    "order:lactate": ["lactate", "lactic acid"],
    "order:glucose": ["glucose", "blood sugar", "fingerstick", "finger stick", "sugar check", "poc glucose"],
    "order:hba1c": ["hba1c", "a1c", "glycated"],
    "order:lipid_panel": ["lipid panel", "lipids", "cholesterol panel", "cholesterol test", "lipid profile"],
    "order:d_dimer": ["d dimer", "d-dimer", "ddimer"],
    "order:bnp": ["bnp", "nt-probnp", "probnp", "natriuretic"],
    "order:crp": ["crp", "c reactive", "esr", "inflammatory markers"],
    "order:blood_cultures": ["blood cultures", "blood culture", "cultures"],
    "order:urinalysis": ["urinalysis", "urine dip", "urine test", "urine sample", "ua", "urine analysis", "dipstick"],
    "order:urine_culture": ["urine culture"],
    "order:pregnancy_test": ["pregnancy test", "hcg", "beta hcg"],
    "order:tox_screen": ["tox screen", "toxicology", "drug screen", "urine drug", "uds", "urine tox"],
    "order:ethanol": ["ethanol level", "alcohol level", "blood alcohol", "etoh level", "breathalyzer", "breathalyser"],
    "order:coags": ["coags", "inr", "pt inr", "coagulation", "clotting"],
    "order:abg": ["abg", "blood gas", "vbg", "arterial blood gas", "venous gas"],
    "order:tsh": ["tsh", "thyroid"],
    "order:chest_xray": ["chest x-ray", "chest xray", "chest x ray", "cxr", "chest film", "chest radiograph"],
    "order:xray": ["x-ray", "xray", "x ray", "radiograph", "plain film", "films"],
    "order:ct_head": ["ct head", "head ct", "ct of the head", "ct brain", "brain scan", "ct scan of your head", "cat scan of the head"],
    "order:ct_abdomen": ["ct abdomen", "abdominal ct", "ct of the abdomen", "ct belly", "ct abdomen pelvis", "ct scan of your belly",
                         "ct scan of your abdomen"],
    "order:ct_chest": ["ct chest", "ctpa", "ct angiogram", "ct pulmonary", "chest ct"],
    "order:ultrasound": ["ultrasound", "sonogram", "us abdomen", "pocus", "echo", "echocardiogram"],
    "order:mri": ["mri", "magnetic resonance"],
    "order:peak_flow": ["peak flow", "spirometry"],
    "order:covid_flu_swab": ["covid test", "flu test", "flu swab", "covid swab", "viral swab", "respiratory panel", "strep test"],
    "order:prior_records": ["old records", "prior records", "previous notes", "prior notes", "old notes", "past records",
                            "previous visits", "last visit note", "discharge summary", "old chart", "outside records"],
    "order:medication_list": ["medication list", "pharmacy records", "med list", "pharmacy fill", "dispensing record"],
    "exam:general": ["general exam", "general appearance", "look at you", "general inspection"],
    "exam:cardiac": ["listen to your heart", "heart sounds", "cardiac exam", "cardiovascular exam", "examine your heart",
                     "auscultate your heart", "heart exam"],
    "exam:lungs": ["listen to your lungs", "listen to your chest", "listen to your breathing", "lung exam", "chest exam",
                   "respiratory exam", "examine your chest", "auscultate", "breath sounds", "lung sounds"],
    "exam:abdomen": ["examine your abdomen", "examine your belly", "examine your stomach", "abdominal exam", "press on your belly",
                     "press on your stomach", "feel your belly", "feel your abdomen", "feel your stomach", "palpate",
                     "abdomen exam", "belly exam", "look at your belly", "look at your stomach"],
    "exam:neuro": ["neuro exam", "neurological exam", "neurologic exam", "check your strength", "test your strength",
                   "check your reflexes", "squeeze my fingers", "follow my finger", "cranial nerves", "smile for me",
                   "raise both arms", "check your sensation", "nihss", "check your coordination", "check your pupils"],
    "exam:msk": ["examine your ankle", "examine your wrist", "examine your knee", "examine your back", "examine your shoulder",
                 "look at your ankle", "look at your wrist", "look at your back", "look at your leg", "look at your arm",
                 "musculoskeletal exam", "examine the joint", "examine your leg", "examine your arm", "straight leg raise",
                 "feel along the bone", "press on your ankle", "examine your foot", "look at your foot", "examine your hand",
                 "examine the injury", "msk exam", "back exam", "ankle exam", "wrist exam"],
    "exam:skin": ["look at your skin", "skin exam", "examine the rash", "look at the rash", "examine the wound", "look at the wound",
                  "examine your skin", "track marks"],
    "exam:heent": ["look in your throat", "look in your ears", "look in your mouth", "examine your throat", "heent",
                   "look at your eyes", "feel your neck", "check your glands", "lymph nodes"],
    "exam:extremities": ["look at your legs", "check your legs", "check your ankles", "examine your legs", "check for swelling",
                         "feel your calves", "check your pulses", "extremities"],
    "exam:mental_status": ["mental status", "orientation questions", "do you know where you are", "what year is it",
                           "do you know todays date", "mental state exam", "mini mental", "cognitive screen"],
    "exam:vitals": ["repeat vitals", "recheck vitals", "check your vitals", "take your blood pressure", "check your blood pressure",
                    "check your temperature", "take your temperature", "check your oxygen", "check your pulse",
                    "orthostatic", "vital signs"],
}

REQUEST_VERBS = [
    "order", "get", "send", "run", "check", "obtain", "request", "perform", "draw", "examine", "listen", "look at", "look in",
    "feel", "press", "palpate", "test", "pull up", "review", "do a", "do an", "take a look", "take your", "repeat", "show me",
    "like a", "like an", "want a", "want an", "need a", "need an", "like some", "like to see", "have a look"
]

# ---- conversation-level cues (used for rapport, structure and coaching heuristics)
OPEN_QUESTION = [
    "what brings you", "what brought you", "tell me more", "tell me about", "can you tell me", "could you tell me",
    "how can i help", "what can i do for you", "whats going on", "what is going on", "whats been going on",
    "describe", "walk me through", "in your own words", "how are you feeling", "how do you feel", "how has",
    "how have you been", "what happened", "what else", "anything else", "what do you think", "what are you worried",
    "what worries you", "what concerns", "help me understand", "what was that like", "how did that", "go on",
    "say more", "what matters",
]
INTRODUCTION = [
    "my name is", "i am dr", "im dr", "i am doctor", "im doctor", "i am a medical student", "im a medical student",
    "i am one of the", "im one of the", "i am the", "im the doctor", "im the resident", "i am a student", "im a student",
    "im a nurse", "i am a nurse", "i will be looking after", "ill be looking after", "ill be taking care",
    "i will be taking care", "i am a resident", "im a resident", "im your", "i am your", "this is dr", "i am dr.",
    "im a physician", "i am a physician", "nice to meet you", "im with the", "student doctor", "i am an", "im an",
]
AGENDA = [
    "i would like to ask", "id like to ask", "ask you some questions", "ask you a few questions", "is that okay",
    "is that ok", "is that alright", "if thats okay", "if thats ok", "going to ask",
    "talk about what", "find out what", "before we start", "first id like", "the plan is", "what id like to do",
    "then we will", "then well", "few minutes", "is now a good time",
]
EMPATHY = [
    "sorry to hear", "im sorry", "i am sorry", "that sounds", "that must be", "must be hard", "must be difficult",
    "must be scary", "must be frightening", "must be stressful", "must have been", "i understand", "i can understand",
    "i can see", "i can imagine", "i imagine", "i hear you", "that is understandable", "thats understandable",
    "understandable", "take your time", "thank you for telling", "thank you for sharing", "thanks for telling",
    "thanks for sharing", "thank you for being honest", "thanks for being honest", "i appreciate you", "appreciate you telling",
    "appreciate your honesty", "that is a lot", "thats a lot", "sounds difficult", "sounds hard", "sounds scary",
    "sounds stressful", "sounds frustrating", "sounds tough", "hard to talk about", "difficult to talk about",
    "not easy to talk", "isnt easy", "is not easy", "you are not alone", "youre not alone", "we are here to help",
    "were here to help", "im here to help", "i am here to help", "we will take good care", "well take good care",
    "glad you came", "you did the right thing", "that makes sense", "it makes sense", "i want to help",
    "going through a lot", "been through a lot", "no rush", "worried", "it is okay to", "its okay to", "its ok to",
]
NORMALISING = [
    "many people", "a lot of people", "lots of people", "many patients", "a lot of patients", "lots of patients",
    "it is common", "its common", "very common", "quite common", "is normal", "perfectly normal", "no judgment",
    "no judgement", "not here to judge", "wont judge", "will not judge", "without judgment", "without judgement",
    "confidential", "stays between us", "between us", "private", "i ask everyone", "i ask all my patients",
    "ask all of my patients", "ask everybody", "routine questions", "i ask these of everyone", "ask every patient",
    "nothing to be ashamed", "nothing to be embarrassed", "no shame", "not in trouble", "wont get you in trouble",
    "safe to tell", "safe space", "helps me take better care", "so i can take better care", "only to help you",
    "just so i can help", "sensitive questions", "personal questions",
    # confidentiality and reassurance (QA round 2, N10: these were being scored as judgmental through the word "whatever")
    "whatever you tell me", "anything you tell me", "what you tell me", "only used to look after you", "to look after you", "look after you",
    "im not here to judge", "not going to judge", "stays private", "stays confidential", "in confidence", "wont be shared", "will not be shared",
    "you can tell me anything", "nothing you say will", "between you and me",
]
JUDGMENTAL = [
    "you should have", "you shouldnt have", "you should not have", "why didnt you", "why did you not", "thats irresponsible",
    "that is irresponsible", "thats stupid", "that is stupid", "your own fault", "you people", "obviously you",
    "you need to stop lying", "stop lying", "youre lying", "you are lying", "dont lie", "thats ridiculous",
    "that is ridiculous", "how could you", "you must stop", "bad idea", "shame on", "disgusting", "thats crazy",
    "calm down", "just answer the question", "hurry up", "i dont have time", "whatever you say", "yeah whatever", "oh whatever",
]
SUMMARISING = [
    "let me summarize", "let me summarise", "to summarize", "to summarise", "so to recap", "let me recap", "just to recap",
    "let me make sure i", "make sure i have this right", "make sure ive got", "if i understand correctly",
    "if i have this right", "so what im hearing", "what im hearing is", "so far you have told me", "youve told me",
    "you have told me", "so in summary", "in summary", "have i got that right", "did i get that right", "is that right",
    "is that correct", "did i miss anything", "so you have had", "so youve had", "let me check i understood",
    "sounds like you", "it sounds like",
]
CLOSING = [
    "any questions", "do you have questions", "questions for me", "anything else you want to", "anything else youd like",
    "anything i missed", "anything we havent", "anything we have not", "thank you for your time", "thanks for your time",
    "thank you for talking", "thanks for talking", "next step", "next steps", "the plan", "what happens next",
    "going to happen next", "ill be back", "i will be back", "ill come back", "come back and", "talk to my attending",
    "discuss with my", "speak with my", "i will let you know", "ill let you know", "we will keep you", "take care",
    "press the call", "call button", "if anything changes", "if it gets worse", "if you feel worse", "let the nurse know",
    "let us know", "come back if", "return if", "follow up", "follow-up",
]
EXPLAINING = [
    "what this means", "this means", "the reason", "because", "im concerned", "i am concerned", "i think", "we think",
    "it could be", "it might be", "it may be", "it looks like", "the test", "the results", "we are going to",
    "were going to", "i would recommend", "id recommend", "i recommend", "we recommend", "the plan", "next step",
    "does that make sense", "does this make sense", "make sense", "how does that sound", "what do you think about",
    "would you be willing", "are you okay with", "is that okay with you", "your preference", "what would you prefer",
    "any questions", "in other words", "to explain",
]
CONFRONT_CUES = [
    "i noticed", "i notice", "i see that", "i can see that", "i saw", "your results", "your labs", "your lab", "your blood test",
    "your blood work", "your bloodwork", "blood tests show", "the results show", "the labs show", "labs show", "test shows",
    "tests show", "test showed", "results suggest", "your chart", "the chart", "your record", "your records", "the record",
    "it says here", "says here", "according to", "the note", "prior note", "the notes", "your ecg", "the ecg", "the scan",
    "the x-ray", "the xray", "the pharmacy", "your pharmacy", "medication list", "came back", "shows that", "showed that",
    "doesnt quite fit", "does not quite fit", "doesnt match", "does not match", "doesnt add up", "earlier you said",
    "you mentioned", "you told me", "on exam", "when i examined", "i found", "the nurse noted", "triage note",
    "the screen", "tox screen", "level was", "level is", "positive for", "elevated", "is high", "are high", "was high",
    "were high", "are raised", "is raised",
]
JARGON = [
    "dyspnea", "dyspnoea", "orthopnea", "syncope", "hematuria", "haematuria", "dysuria", "emesis", "hematemesis",
    "melena", "diaphoresis", "angina", "myocardial infarction", "ischemia", "ischaemia", "paresthesia", "paraesthesia",
    "edema", "oedema", "pruritus", "tachycardia", "bradycardia", "hypertension", "hyperlipidemia", "dyslipidemia",
    "etiology", "idiopathic", "prn", "bid", "tid", "npo", "pmh", "hpi", "sob", "nstemi", "stemi", "pe ", "dvt",
    "cva", "tia", "uti", "copd", "etoh", "febrile", "afebrile", "bilateral", "radiculopathy", "claudication",
    "hemoptysis", "haemoptysis", "polyuria", "polydipsia", "nocturia", "anorexia", "malaise", "erythema",
    "differential diagnosis", "prophylaxis", "contraindicated", "subcutaneous", "intravenous",
]

_PUNCT = re.compile(r"[^a-z0-9\s\-/.]")
_WS = re.compile(r"\s+")
_IRREGULAR = {
    "drank": "drink", "drunk": "drink", "took": "take", "taken": "take", "ate": "eat", "eaten": "eat",
    "felt": "feel", "fell": "fall", "fallen": "fall", "hurts": "hurt", "smoked": "smok", "meds": "med",
    "medication": "med", "medications": "med", "medicine": "med", "medicines": "med", "children": "child",
    "kids": "kid", "allergic": "allerg", "allergy": "allerg", "allergies": "allerg", "began": "begin",
    "begun": "begin", "threw": "throw", "thrown": "throw", "lost": "lose", "bled": "bleed", "woke": "wake",
    "slept": "sleep", "went": "go", "gone": "go", "got": "get", "gotten": "get", "hrs": "hour", "yrs": "year",
    "dad": "father", "mom": "mother", "mum": "mother", "doc": "doctor", "ok": "okay",
    # inflections of the short words whose final "e" is kept (see _KEEP_E)
    "wines": "wine", "bites": "bite", "bitten": "bite", "biting": "bite", "notes": "note", "noted": "note", "hopes": "hope", "hoped": "hope",
    "hoping": "hope", "hates": "hate", "hated": "hate", "sites": "site",
}
# Short words that become a DIFFERENT word when the stemmer drops their final "e" (wine -> win, note -> not, here -> her).
# QA round 2, N7: "Who will win the election?" matched the alcohol topic through "wine". These keep their "e".
_KEEP_E = {"wine", "bite", "site", "pine", "mate", "fate", "hate", "cute", "pale", "bare", "fare", "cane", "here", "fine", "hope", "made", "note"}


def normalize(text: str) -> str:
    t = (text or "").lower().replace("’", "'").replace("'", "")
    t = _PUNCT.sub(" ", t)
    t = t.replace(".", " ").replace("/", " ")
    return _WS.sub(" ", t).strip()


def stem(word: str) -> str:
    w = _IRREGULAR.get(word, word)
    if w != word:
        return w
    if len(w) <= 3 or w.isdigit():
        return w
    for suf in ("ings", "ing", "edly", "ies", "ed", "es", "ers", "er", "ly", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            if suf == "ies":
                w += "y"
            break
    if w.endswith("e") and len(w) > 3 and w not in _KEEP_E:
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiouls":
        w = w[:-1]
    return w


def tokens(text: str) -> list[str]:
    return [stem(w) for w in normalize(text).replace("-", " ").split()]


STOPWORDS = set(
    "a an the and or of to in on at for with is are was were be been being am do does did have has had you your yours "
    "i me my we our it its this that these those any some there here how what when where who why which can could would "
    "should will shall may might must if so as by from about into than then too very just also not no yes".split()
)


def phrase_in(norm_text: str, phrases: list[str]) -> list[str]:
    """Phrases (already lower case, apostrophe-free) present in a normalized text, by token containment."""
    toks = tokens(norm_text)
    hits = []
    for p in phrases:
        if contains_phrase(toks, tokens(p)):
            hits.append(p)
    return hits


def phrase_positions(text_toks: list[str], phrase_toks: list[str], slack: int = 2) -> tuple[int, ...] | None:
    """Token positions where the phrase occurs: all phrase tokens in order inside a window of len(phrase)+slack tokens."""
    n = len(phrase_toks)
    if n == 0 or n > len(text_toks):
        return None
    first = phrase_toks[0]
    for i, t in enumerate(text_toks):
        if t != first:
            continue
        if n == 1:
            return (i,)
        pos, j = [], 0
        for k in range(i, min(len(text_toks), i + n + slack)):
            if text_toks[k] == phrase_toks[j]:
                pos.append(k)
                j += 1
                if j == n:
                    return tuple(pos)
    return None


def contains_phrase(text_toks: list[str], phrase_toks: list[str], slack: int = 2) -> bool:
    return phrase_positions(text_toks, phrase_toks, slack) is not None
