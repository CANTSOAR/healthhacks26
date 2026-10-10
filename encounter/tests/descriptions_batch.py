"""Self-check batch for the description reader: 25 descriptions written to stress sentence shapes, not to pass.
Values embedded mid-clause, "and" lists, relative clauses, possessives, passive voice, "denies", "reports", "c/o",
a parent speaking for a toddler, first-person paragraphs. Used by test_round4.py. All invented."""

BATCH = {
    "embedded_fever": "Mrs. Elena Park is a 67-year-old retired teacher brought in by her daughter with two days of confusion and a fever of 38.9. She has type 2 diabetes and takes "
                      "metformin 500 mg twice daily and lisinopril 10 mg every morning. She is allergic to sulfa drugs, which give her a rash. She has not told anyone that she "
                      "has had burning when she urinates for a week because she is embarrassed. HR 108, BP 104/62. She lives alone and drinks a glass of wine with dinner.",
    "pain_score": "Marcus Bell is a 29-year-old bike courier who presents with right flank pain rated 8/10 that started three hours ago. He has vomited once. He has a BP of 150 "
                  "over 90 and a heart rate of 112. He has had a kidney stone before. He takes no regular medications and has no known drug allergies.",
    "bp_over": "A 61-year-old woman presents with a severe headache and blurred vision, with a BP of 210 over 120 and a pulse of 96. She has hypertension, for which she takes "
               "amlodipine 10 mg daily. She is hiding that she stopped taking her amlodipine two weeks ago because it made her ankles swell.",
    "relative_who": "Mr. Peter Novak, who is 72 and lives with his wife, comes in with chest tightness which gets worse when he climbs stairs. He has a history of high cholesterol "
                    "and angina. He takes atorvastatin 40 mg at night and uses a GTN spray. He smokes a pipe.",
    "which_clause": "Dana Whitfield is a 38-year-old chef with a cut on her left hand, which she got from a knife two hours ago and which is still bleeding. Her tetanus shot was "
                    "more than ten years ago. She is allergic to latex, which causes hives. She does not drink alcohol.",
    "possessive": "Oliver's mother brought him in. Oliver Grant is a 9-year-old boy with a swollen right ankle after falling off his scooter this afternoon. His pain is 6 out of 10. "
                  "He is allergic to penicillin. His father's asthma is well controlled. Oliver does not want to tell anyone that he was not wearing his helmet.",
    "passive": "A 55-year-old man was brought in by ambulance after he was found collapsed at home by his wife. He was given glucose by the paramedics. He has type 1 diabetes and "
               "takes insulin glargine 24 units at night. Blood sugar 42 on arrival, now 110. He drinks six beers a day but minimises it.",
    "denies": "Priya Nair, 44, accountant, presents with three weeks of fatigue and shortness of breath on exertion. She denies chest pain, fever or weight loss. She reports heavy "
              "periods for six months. Hemoglobin 7.9. She takes no medications. She is worried about her job.",
    "reports": "A 26-year-old male student reports a sore throat, a dry cough and muscle aches since Monday. He reports a temperature of 38.2 at home. He denies shortness of "
               "breath. He vapes daily. He lives with three housemates, one of whom has the flu.",
    "c_o": "58F c/o epigastric pain x 2 days, worse after meals, N/V x 1. PMH: HTN, GERD. Meds: omeprazole 20 mg daily, losartan 50 mg daily. NKDA. Social drinker, non-smoker. "
           "BP 132/84, HR 88, temp 37.0.",
    "toddler_parent": "My son Leo is 2 years old. He has had diarrhoea and vomiting since yesterday and has not had a wet nappy today. He had a fever of 39 last night. He is "
                      "drinking very little. His vaccinations are up to date. He goes to nursery, where several children have been sick.",
    "first_person": "I am a 41-year-old woman and I work as a bus driver. I have had lower back pain for five days after lifting a suitcase. The pain goes down my left leg. I take "
                    "ibuprofen 400 mg three times a day. I am allergic to codeine, which makes me vomit. I have not told anyone that I have had trouble passing urine since "
                    "yesterday. I smoke ten cigarettes a day.",
    "and_list": "Grace Okonkwo is a 70-year-old widow who presents with nausea, sweating and pain in her jaw and left arm for one hour. She has diabetes, high blood pressure and "
                "arthritis. She takes metformin 1000 mg twice daily, ramipril 5 mg daily and naproxen 500 mg twice daily. She is allergic to penicillin and shellfish.",
    "infant": "An 8-month-old girl brought in by her parents with a fever of 39.4 and poor feeding for one day. She has been irritable and has a rash on her chest. Her "
              "immunisations are up to date. Heart rate 168, respiratory rate 48, oxygen saturation 96%.",
    "teen": "Jordan is a 16-year-old girl brought in by her aunt with abdominal pain and vomiting since this morning. Her last period was six weeks ago. She does not want her "
            "aunt to know that she is sexually active. She takes no medications. Temp 37.4, HR 104, BP 108/70.",
    "elderly_fall": "Mr. Arthur Hale, an 84-year-old retired farmer, was brought in by his neighbour after a fall in the garden. He has pain in his right hip and cannot bear "
                    "weight. He has atrial fibrillation and takes apixaban 5 mg twice daily and bisoprolol 2.5 mg daily. He lives alone. He denies hitting his head. His wife "
                    "died last year.",
    "psych": "A 33-year-old woman presents with trouble sleeping and feeling low for two months. She has lost her appetite and has lost 5 kg. She takes sertraline 50 mg daily. She "
             "is reluctant to admit that she has had thoughts of harming herself. She lives with her partner, who is supportive.",
    "asthma": "Tariq Hussain is a 19-year-old student with wheezing and a tight chest since last night, which has not improved with his salbutamol inhaler. He has asthma and was "
              "admitted to intensive care two years ago. Sats 91% on room air, RR 30, HR 124. He secretly smokes cannabis every day.",
    "semicolon": "47-year-old male; sudden onset severe abdominal pain 4 hours; history of alcohol excess; drinks a bottle of vodka daily; lipase 1450; HR 118; BP 98/60; "
                 "allergic to morphine (itching).",
    "pregnancy": "Sofia Marin is a 31-year-old woman who is 34 weeks pregnant and presents with a headache, swollen feet and seeing flashing lights since yesterday. Blood pressure "
                 "164/108. This is her first pregnancy. She takes folic acid and iron tablets. She has no allergies.",
    "comma_heavy": "Ben Carter, 52, plumber, married, comes in with crushing chest pain, sweating, and nausea, which began 40 minutes ago, while he was carrying a boiler. His "
                   "father died of a heart attack at 54. He takes nothing regularly. He smokes 20 cigarettes a day, and drinks at weekends.",
    "stroke_time": "A 78-year-old woman was found by her son at 7 am with a drooping face on the right side, slurred speech and weakness of her right arm. She was last seen well at "
                   "10 pm. She takes warfarin 3 mg daily for atrial fibrillation. INR 1.4. Blood pressure 188/102, glucose 131.",
    "skin": "Hannah Lee is a 24-year-old nurse with a red, hot, swollen area on her right shin that has spread over three days, after an insect bite. She has a temperature of 38.1. "
            "She is allergic to flucloxacillin, which gave her a rash. She takes the contraceptive pill.",
    "short_note": "63M. Black stools 3 days. On aspirin 75 mg daily and ibuprofen 400 mg three times a day for knee pain. Hb 9.2. Ex-smoker. Denies alcohol.",
    "run_on": "Luis Ortega is a 36-year-old construction worker and he comes in with a painful swollen knee and he says it started after he twisted it at work yesterday and he "
              "cannot bend it and he has taken paracetamol 1 g four times a day with no relief.",
}
