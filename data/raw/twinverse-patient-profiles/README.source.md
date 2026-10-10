---
license: cc-by-4.0
language:
- en
task_categories:
- text-generation
- question-answering
tags:
- healthcare
- medical-education
- dietetics
- nutrition
- patient-simulation
- motivational-interviewing
- synthetic
pretty_name: VHS Patient Profiles — Nutrition Education Simulation
size_categories:
- n<1K
---

# VHS Patient Profiles — Nutrition Education Simulation

## Dataset Summary

A curated collection of 8 richly structured synthetic patient personas designed for healthcare education simulations, with a primary focus on dietetics and nutrition counseling training. Each record represents a complete clinical case with demographic, clinical, psychosocial, and behavioral dimensions, along with structured guidance for educators and AI simulators.

Profiles are intended for use in virtual patient simulation platforms where students practice clinical nutrition competencies: applying the Nutrition Care Process (NCP), formulating PES statements, conducting motivational interviewing (MI), integrating medication management with nutrition care, and identifying interprofessional and community resources.

## Supported Tasks

- **Virtual patient simulation**: Each profile supports a full simulated clinical encounter. The `information_disclosure` section defines what the patient volunteers, what must be elicited, what is reluctant, and what is hidden in the chart.
- **LLM fine-tuning / prompting**: Profiles can serve as grounding documents for AI patient roleplay models.
- **Curriculum design**: The `learning_opportunities` section maps each patient to specific pedagogical objectives.

## Languages

English (all profiles). Two patients have noted bilingual backgrounds (Spanish/English, Hindi/English), which is reflected in the `demographics.language` field.

---

## Dataset Structure

### Data Instances

Each line of `patients.jsonl` is one self-contained JSON object representing a single patient. Example top-level keys:

```json
{
  "patient_overview": {...},
  "demographics": {...},
  "clinical_profile": {...},
  "medication_profile": {...},
  "nutrition_profile": {...},
  "psychosocial_profile": {...},
  "information_disclosure": {...},
  "learning_opportunities": {...},
  "metadata": {...}
}
```

### Data Fields

| Section | Key Fields | Description |
|---|---|---|
| `patient_overview` | `name`, `age`, `sex`, `description`, `keywords` | High-level identity and searchable tags |
| `demographics` | `occupation`, `ethnicity`, `language`, `insurance`, `cultural_context` | Socioeconomic and cultural background |
| `clinical_profile` | `primary_diagnosis`, `secondary_diagnoses`, `laboratory_data`, `vital_signs`, `anthropometrics` | Full clinical picture including labs and vitals |
| `medication_profile` | `medications[]` (name, dose, frequency, purpose, adherence, patient_concerns), `supplements_and_otc` | Current regimen with adherence patterns and patient-stated concerns |
| `nutrition_profile` | `dietary_pattern`, `food_preferences`, `meal_pattern`, `hydration`, `physical_activity`, `substance_use`, `sleep` | Behavioral and dietary habits |
| `psychosocial_profile` | `goals`, `concerns`, `beliefs`, `motivations`, `fears`, `barriers`, `strengths`, `readiness_to_change` | Full psychosocial model for motivational interviewing |
| `information_disclosure` | `initial_information`, `discoverable_information`, `reluctant_information`, `hidden_information` | Layered disclosure structure for simulation realism |
| `learning_opportunities` | `opportunities[]` (learning_objective, expected_discoveries, possible_patient_reactions) | Structured pedagogical guidance per patient |
| `metadata` | `assumptions`, `optional_details` | Generation assumptions and optional character details |

### Data Splits

The dataset ships as a single split (`train`). All 8 records are in `patients.jsonl`.

---

## Patient Roster

| Name | Age | Sex | Ethnicity | Primary Diagnosis | Key Learning Focus |
|---|---|---|---|---|---|
| Dominic Rivera | 22 | M | Puerto Rican | Poorly controlled T2DM | Cultural humility, healthcare mistrust, MI |
| Yvette Armstrong | 64 | F | Eastern European American | Stage II Hypertension + T2DM | Health literacy, sodium education |
| Nisha Patel | 29 | F | Indian-American | T2DM (first hospitalization) | Anxiety, detailed questioning, MI |
| Omar Sinclair | 45 | M | African-American | Dyslipidemia | Medication skepticism, cardiovascular risk |
| Marcus Ramirez | 59 | M | Hispanic/Latino | Heart Failure + T2DM | Early satiety, comorbidity integration |
| Walter Greene | 72 | M | African-American | Uncontrolled T2DM + CHF + CKD | Dietary non-adherence, aging, social isolation |
| Wyatt Nelson | 18 | M | White American | T2DM + Obesity + Dyslipidemia | Adolescent counseling, constipation |
| Vladko Bareche | 31 | M | Asian Indian | T2DM + Substance Use Disorder | Immigration barriers, substance use, vegetarian diet |

---

## Dataset Creation

### Curation Rationale

The profiles were generated to support a virtual human simulation platform for dietetics and health professions education. Real patient data was not used. Each persona was designed to represent a distinct cluster of clinical and psychosocial challenges that nutrition students commonly encounter, spanning age, ethnicity, health literacy, cultural context, and disease complexity.

### Source Data

All profiles are synthetically generated. Clinical values (labs, vitals, medications) are constructed to be internally consistent and clinically plausible but do not represent real individuals.

### Annotations

The `learning_opportunities` section serves as structured annotation for each case, mapping patient behaviors to educational objectives aligned with the Nutrition Care Process and ACEND competencies.

### Personal and Sensitive Information

No real individuals are represented. Names, demographics, and clinical details are entirely fictional. The dataset does include synthetic sensitive health information (substance use, mental health, STI risk) within specific profiles, which is intentional for educational fidelity.

---

## Considerations for Using the Data

### Social Impact

These profiles are designed to foster cultural humility, empathy, and evidence-based practice in nutrition education. The diversity of patient backgrounds is intentional and meant to prepare students for real-world clinical populations.

### Discussion of Biases

- Profiles reflect common clinical presentations and cultural contexts as understood at the time of creation. They may not cover the full range of lived experiences.
- AI models trained or prompted with these profiles should be evaluated for whether they reproduce or amplify stereotypes present in the synthetic personas.

### Other Known Limitations

- 8 profiles is a small dataset. It is intended as a seed corpus for a simulation platform, not for large-scale statistical training.
- Some profiles contain minor inconsistencies introduced during generation (e.g., duplicate list entries, abbreviated field values in some records). These are noted in `metadata.assumptions`.

---

## Additional Information

### Citation

If you use this dataset, please cite the VHS (Virtual Human Simulation) project at Rutgers University.

### License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)