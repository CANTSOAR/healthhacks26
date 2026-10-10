# Operations citation audit

Independent audit, 2026-10-10, of (a) every catalog attribute tagged `source: literature` in
`catalog/{patient,staff,space,equipment,event}.yaml` (23 found; the brief estimated about 25) and
(b) a seeded random sample of 15 of the 78 records in `research/operations-evidence.md`.
The audited files were not edited.

## Method

- For each item the cited source was fetched again in this run and the cited numbers were searched for in
  the fetched text. Nothing was accepted from memory or from the audited files themselves.
- How sources were fetched:
  - Journal articles: Europe PMC REST API by DOI or PMID (metadata + abstract), and Europe PMC open-access
    full-text XML where available (Wrede 2020, Guttmann 2011, Lake 2025, Joseph 2018, Ramsey 2018).
    Two DOIs not indexed in Europe PMC (Batt and Terwiesch; Whitt and Zhang) were checked against Crossref
    metadata, and their cited PDFs were downloaded and text-extracted.
  - PDFs downloaded and text-extracted with pypdf: NSI 2026 report (19 pp.), NJ bill A1974 (8 pp.),
    Batt and Terwiesch working paper (33 pp.), Whitt and Zhang author manuscript (38 pp.), arXiv 2410.13767 (58 pp.).
  - Web pages downloaded directly: Wiener Gesundheitsverbund CT downtime page, SHM abstract 692, Cornell LII
    (Cal. Code Regs. tit. 22 s. 70217), arXiv abstract pages.
  - cdc.gov and bls.gov returned HTTP 403 to a direct download; both were read through the WebFetch tool
    (which returns a model-extracted answer, not raw text). Those two items are therefore one step less
    direct than the rest.
- Derived values: arithmetic was recomputed from the source inputs.
- Classifications:
  - `verified`: the number, or every input to a value labelled DERIVED, was seen in the fetched source.
  - `plausible-unverified`: source exists, number not visible in what could be accessed.
  - `mismatch`: source exists but says something different from the citation.
  - `not-found`: source could not be located.
- `verified` certifies the cited figures and the arithmetic. It does not certify that a derivation is a sound
  modelling choice; where the step from source to value is a judgement, that is said in the reason.
- Sample selection: Python `random.seed(20261010); sorted(random.sample(range(1, 79), 15))` gave
  E-01, E-06, E-22, E-23, E-30, E-33, E-38, E-42, E-43, E-45, E-46, E-51, E-52, E-59, E-75.
- Not checked: the 63 evidence records outside the sample; catalog attributes with any other `source` tag;
  secondary citations that appear only in `note:` fields unless listed below.

## Totals

| Set | Items | verified | plausible-unverified | mismatch | not-found |
|---|---|---|---|---|---|
| Catalog `source: literature` attributes | 23 | 22 | 0 | 1 | 0 |
| Evidence-record sample | 15 | 15 | 0 | 0 | 0 |

No invented source, author list, DOI, sample size or headline number was found in either set. Every cited
source exists with the stated authors, year and title. One citation mis-pairs two figures from its source
(C-21), and several carry small unsupported details (listed under Corrections).

## Catalog attributes (23)

Attribute paths were resolved from YAML indentation; the line number is that of the `source: literature` line.

| # | File:line | Attribute | Class | Reason |
|---|---|---|---|---|
| C-01 | equipment.yaml:44 | ct.failure_prob_per_hour = 0.001 | verified | Page lists yearly downtime 22.5, 11.5, 38.5, 0, 14, 0, 0, 0, 4, 3.2, 22.33, 0.33 h (2011-2022), 2,500 operating h/yr, 2% vendor guarantee. Recomputed mean 9.7 h/yr = 0.39%; 0.4% / 4 h = 0.001. Single scanner, as the note says. |
| C-02 | equipment.yaml:90 | ct.result_delay_min = 74 | verified | Brunner 2014 abstract: annual median completion-to-report 74 min (IQR 35-127); CT order-to-completion 72 (40-129); radiography 31 (19-48). Dhanik 2024: 5,685 CTs, median 108 (Q1 57, Q3 182). |
| C-03 | equipment.yaml:360 | lab_analyzer.procedure_min = 54, cv 0.35 | verified | Vrijsen 2022 abstract: 23,718 visits, TAT 51.1 (41.1-65.0), TTT 7.0, lab stage 69%. Recomputed sigma = ln(65.0/41.1)/1.349 = 0.34, mean = 54.1. Hausfater 2020: 20,923 analysed, 79 (34) vs 28 (31), LOS 210 vs 203, -9 (-22 to 5). |
| C-04 | event.yaml:14 | flu_wave.arrival_multiplier = 1.1 | verified | CDC week 5 page (via WebFetch): 8.0% of ED visits influenza (NSSP); 7.8% ILI vs 3.0% baseline, tenth consecutive week. 1/(1-0.08) = 1.087. Schanzer 2013: 500 per 100,000, 7% coded. "High-severity season" is not on the cited page (see corrections). |
| C-05 | event.yaml:75 | mass_casualty.extra_patients = 40 | verified | Brunner 2014: 40 patients, 16 admitted, 24 discharged, 10 emergent surgery, no deaths. Lake 2025 full text: over 800 injured, 413 gunshot wounds needing immediate treatment, self-transport. |
| C-06 | event.yaml:87 | mass_casualty.window_min = 180 | verified | Input verified: blast-to-arrival median 97 min (IQR 43-139). The step from an IQR of 96 min to a 180-min window is a judgement, not a calculation; it is labelled DERIVED. |
| C-07 | space.yaml:22 | walk_speed_m_per_min = 80 | verified | Bohannon 1997 abstract: 127.2 to 146.2 cm/s comfortable (76.3 to 87.7 m/min), 174.9 to 253.3 maximum, n = 230, 7.62 m. |
| C-08 | space.yaml:445 | icu_bed.turnaround_min = 68 | verified | SHM Converge 2026 abstract 692 (MD Anderson): 115 min (Feb 2023-Feb 2024) to 68 min (Jan-Jun 2025), 41% decrease. Ankrum 2019: 130 (93-294) to 65 (48-95); cleaning and curtains 57 to 37. Neither source is an ICU; the note says so. |
| C-09 | space.yaml:480 | stepdown_bed.turnaround_min = 68 | verified | Same citation as C-08. |
| C-10 | space.yaml:519 | ward_unit.turnaround_min = 68 | verified | Same citation as C-08. |
| C-11 | staff.yaml:75 | agency_premium_multiplier = 1.93 | verified | NSI 2026 PDF: travel nurse fee $91.23/h; RN pay "(includes 25.8% for benefits) $59.46"; "average $91/hour and range to $160/hour". 59.46/1.258 = 47.27; 91.23/47.27 = 1.93; 160/47.27 = 3.38. |
| C-12 | staff.yaml:88 | benefits_load = 1.258 | verified | Same NSI line. Upper range 1.35 is stated to be a judgement. |
| C-13 | staff.yaml:105 | absence_rate = 0.021 | verified | BLS CPS Table 47, 2025 (via WebFetch): healthcare practitioners and technical, absence rate 3.7, lost worktime 2.1; healthcare support 4.1 / 2.2; 2025 averages exclude October. |
| C-14 | staff.yaml:135 | fatigue_error_multiplier = 2.0 | verified | Landrigan 2004: 2,203 patient-days, 35.9% more (136.0 vs 100.1), 5.6 times diagnostic errors. Barger 2006: 2,737 interns, 17,003 reports, OR 3.5 (3.3-3.7) and 7.5. Rogers 2004: 393 nurses, 5,317 shifts. The value 2.0 itself is a pick inside 1.36-3.5, not a source figure; the note says so. |
| C-15 | staff.yaml:150 | annual_turnover = 0.185 | verified | NSI: 527 hospitals, forty states; hospital turnover 18.5% (7.6% to 33.1%); RN 17.6%; $60,090; $295,000. Emergency 20.7% / 19.1%: both values are on the chart; the legend-to-year mapping was checked against the report text ("behavior health, emergency services, telemetry, step down, and medical/surgical all exceeded the national average" of 17.6%), which fits only if 20.7% is 2025. |
| C-16 | staff.yaml:168 | rn_patients_per_nurse_max = 4 | verified | Cornell LII text: ED 1:4, ED critical care 1:2, critical trauma 1:1 RN, two licensed nurses present, RN for triage; critical care 1:2, step-down 1:3 (2008), telemetry 1:4 (2008), medical/surgical 1:5 (2005). NJ A1974 PDF: 1:4 ED, 1:2 ED critical care, 1:1 ED trauma. Two small wording issues (see corrections). |
| C-17 | staff.yaml:229 | attending.patients_per_hour_by_acuity = 0.8, 1.2, 1.9, 3.3, 5.0 | verified | Wrede 2020 Table 1 (full text): ESI 1+2 n=45, 76 (42); ESI 3 n=93, 48 (27); ESI 4 n=43, 27 (15); ESI 5 n=21, 18 (11); specialists 31 (16); overall 47 (34); only two ESI 1 patients. Recomputed 60/(min x 31/47) = 1.20, 1.90, 3.37, 5.05; 60/76 = 0.79. Joseph 2018: 15.0, 20.9, 13.2 per shift; 2.97, 2.95, 2.17 first hour. ESI 1 is unscaled and ESI 2 scaled from the same pooled 76-min figure (stated in the citation). |
| C-18 | staff.yaml:263 | resident.productivity = 0.6 | verified | Joseph 2017: 75 residents, 14,364 shifts, 10.1 (3.2) per shift, 2.14 first hour. Shaw 2024: 2,950 shifts, 0.88-0.96 and 1.61-1.75. Hamden 2014: 1.23. 10.1/8.5 h = 1.19; /2.0 = 0.59. |
| C-19 | staff.yaml:289 | app.productivity = 0.78 | verified | Hamden 2014: 55 and 98 shifts, 1.56 (CI +/-0.14) vs 1.23 pt/h, 2.05 vs 2.73 RVU/pt. 1.56/2.0 = 0.78. McDonnell 2015: 2.18 vs 1.90, not significant. |
| C-20 | patient.yaml:299 | deterioration_hazard_per_hour_waiting = 0.02, 0.003, 0.001, 0.0004, 0.0001 | verified | Rizer 2026 abstract: 173,168; 6,299 (3.6%); 2,823 (45%); 12.5 h (8.2-20.7) vs 10.2; +0.8% and +2.4% per hour; 13.0% vs 3.9%. 3.6%/12.5 = 0.0029; 2,823/173,168 = 1.63%, /12.5 = 0.0013. Only the ESI 2 element comes from the source; ESI 3 is "a third of ESI 2" by assumption and ESI 1, 4, 5 are Wave 0 placeholders, so 4 of 5 elements under this `literature` tag are not literature values (disclosed in the note; see corrections). |
| C-21 | patient.yaml:330 | death_hazard_per_hour_untreated = 0.01, 0.0015, 0.0005, 4e-5, 4e-5 | mismatch | Singer and Jones figures verified. Guttmann figure is mis-paired: the citation says "8,625 deaths among 6.64 million high-acuity and 2,054 among 7.29 million low-acuity discharged patients". Guttmann Table 2 gives 8,502 deaths among 6,643,694 high-acuity and 1,998 among 7,290,848 low-acuity seen-and-discharged patients; 8,625 and 2,054 are the totals including patients who left without being seen (123 and 56 more deaths; denominators 6,905,618 and 7,640,905). The avoidable-death figures 558 (6.5%) and 261 (12.7%) are verified. Effect on the value is small: 558/6.91 M = 8.1e-5, 261/7.64 M = 3.4e-5 (the catalog uses 4e-5). ESI 1 is assumed (disclosed). |
| C-22 | patient.yaml:362 | lwbs_patience_min = 100000, 3500, 1150, 1600, 1000 | verified | Batt and Terwiesch working paper Table 1: wait 1.0/1.9/1.3/1.3 h, LWBS 1.7/9.5/4.7/7.4%, N 27,538/65,773/39,878/10,509; "these patients do not abandon" (ESI 1). Recomputed theta = 3,499 / 1,142 / 1,620 / 1,014 min. Note figures verified: +2.0 points per hour of wait, +0.5 points per person. Crossref confirms Management Science 61(1):39-59, 2015. |
| C-23 | patient.yaml:389 | boarding_los_penalty = 0.01 | verified | Singer 2011: 41,256 admissions, 5.6 (SD 11.4) vs 8.7 (SD 16.3) days for under 2 h vs over 24 h; 55%/24 h = 2.3% per hour. Roussel 2023: rate ratio 1.20 (1.11-1.31). Sun 2013: 995,379 admissions, 0.8% longer stay. The value 0.01 is a pick inside the range (stated). |

## Evidence-record sample (15 of 78)

| Record | Source | Class | Reason |
|---|---|---|---|
| E-01 | Batt, Terwiesch 2015 (working-paper PDF) | verified | "over 180,000 patient visits"; Table 1 N, wait, service time, LWBS and fast-track shares all match; 0.5 points per extra person = 15 min (working paper), 0.6 points per first-come departure, 1 point per sicker arrival, 1.8 points for a triage test; patients "generally not informed" of triage level. Crossref abstract of the published version gives 25 minutes, as the record says. |
| E-06 | Whitt, Zhang 2017 (author manuscript PDF) | verified | Rambam, "1000-bed", emergency internal medicine unit; 25 weeks Dec 5 2004-May 28 2005; 23,409 arrivals; weekday means 162.00 to 105.40; dispersion 1.51 (single-factor model) and "average IDC is about 1.5"; arrival rate lowest "about 6am", peak "just before noon", steep decline around midnight; admitted mean LoS 4.30 h after omitting stays under 2 minutes; occupancy lag. Crossref: Oper Res Health Care 12:1-15, 2017. |
| E-22 | Epstein et al. 2012 | verified | 533 patients, four Massachusetts EDs, 46 (8.6%) preventable errors, more than twofold in quartile 4 vs 1, non-linear. |
| E-23 | Powell et al. 2012 | verified | 38.8 / 22.7 / 19.5 / 81.1 daily; 70.5% to 88.0% between noon and midnight; 77.0 boarding hours; 4 h shift eliminates boarding; 3.0 under both policies. |
| E-30 | Schull, Kiss, Szalai 2007 | verified | 4.1 million visits, 110 EDs, 1,095 intervals; 6.3 (4.7), 3.9 (2.8), 2.2 (1.6) h; 1.1, 1.3, 1.1 h; 5.4 and 2.1 min per 10 arrivals. |
| E-33 | Green et al. 2006 | verified | Lag SIPP; arrivals +6.3%, provider hours +3.1%, 258 fewer LWBS (22.9%); four-day subset 21.7% with +5.5% arrivals. |
| E-38 | Sun, Dai, Shi, arXiv 2410.13767 v6 | verified | Abstract and PDF: up to twenty classes and twenty wards; ADP "infeasible beyond five wards"; atomic actions; (2J+1)-dimensional state (counts, to-depart counts, time of day); holding cost plus one-time overflow cost; LSTD with queueing-informed basis; "only a few thousand simulation data samples" in a ten-pool system vs "100 times more"; domain-aware adaptation quote. |
| E-42 | Hoot et al. 2008 | verified | n = 52,560; lowest r 0.56 / 0.49 / 0.78 / 0.86 / 0.79 / 0.80; AUC 0.86; residuals unbiased except boarding time. |
| E-43 | Connelly, Bair 2004 | verified | EDSIM, Level 1 trauma centre, five days July 2003, 674 charts; within 10%; 28% within one hour, 59% within three. |
| E-45 | Shakur et al., arXiv 2410.12858 | verified | All eight authors match; 2,027 OSCE videos, UTSW, 2019-2022; Whisper-v3; GPT-4 kappa 0.88. |
| E-46 | Wang et al. 2025, JMIR 27:e59435 | verified | 74.7 (5.44), 82.67 (5.30), 85 (3.27); P = .16; 29.83% to 6.06%; SD 0.55 to 0.068; 3.21%. |
| E-51 | Ramsey et al. 2018 | verified | 105,887 patients, 336 to 580 nursing hours, median 464.7; +28.2 min; nine more LWBS per day. Chicago (Cook County) is from the author affiliations, not the abstract. 105,887/365 = 290 per day. |
| E-52 | Landrigan et al. 2004 | verified | 2,203 patient-days, 634 admissions; 35.9% (136.0 vs 100.1); 56.6%; 20.8%; 5.6 times. |
| E-59 | Jalal et al. 2021, Can Assoc Radiol J 72(3):548-556 | verified | 7.83 h trauma, 6.07 h non-trauma; completion-to-transcription 2.73 and 2.91 h. |
| E-75 | Vrijsen 2022; Hausfater 2020 | verified | Vrijsen: 23,718; 199.0 (146.0-268.0); 7.0 (2.0-12.0); 51.1 (41.1-65.0); 69%. Hausfater: 23,231 included, 36% sampled; 28 (31) vs 79 (34), -51; 203 (161) vs 210 (168); -9 (-22 to 5); -17 (-34.0 to 0.6). |

## Corrections needed

1. **`catalog/patient.yaml`, `shared.death_hazard_per_hour_untreated`, citation part (c)** (C-21). Wrong:
   "8,625 deaths among 6.64 million high-acuity and 2,054 among 7.29 million low-acuity discharged patients".
   Guttmann et al. 2011, Table 2: seen-and-discharged patients had 8,502 deaths of 6,643,694 (high acuity)
   and 1,998 of 7,290,848 (low acuity). 8,625 and 2,054 are the death totals including patients who left
   without being seen (denominators 6,905,618 and 7,640,905). Either use 8,502 / 1,998 with the discharged
   denominators or keep 8,625 / 2,054 and say "non-admitted patients (discharged or left without being seen)".
   With consistent denominators the per-patient-hour figures are 8.1e-5 and 3.4e-5.
2. **`research/operations-evidence.md`, E-09** (not in the random sample; found while checking C-21).
   Same error: "558 of 8,625 (6.5%) among high-acuity and 261 of 2,054 (12.7%) among low-acuity discharged
   patients". The source says "higher acuity patients (8625)" and "lower acuity patients (2054)" for the
   whole non-admitted cohort, not the discharged subgroup.
3. **`catalog/patient.yaml`, `shared.deterioration_hazard_per_hour_waiting`** (C-20). Not a citation error,
   a tagging one: the single `source: literature` tag covers five values of which only ESI 2 (0.003) is
   computed from Rizer et al. 2026. ESI 3 (0.001) is an assumed third of ESI 2; ESI 1, 4, 5 are unchanged
   placeholders. The note discloses this, but anything that reads only the `source` field will treat all
   five as literature-backed. The same applies to the ESI 1 element (0.01) of
   `death_hazard_per_hour_untreated`.
4. **`catalog/event.yaml`, `flu_wave.arrival_multiplier`** (C-04). The citation calls 2024-25 "a
   high-severity season" as if from the cited page. The week 5 FluView page says only that activity
   "remains elevated and continues to increase"; the severity classification is not on it. Drop the phrase
   or cite where CDC classifies the season.
5. **`catalog/staff.yaml`, `shared.rn_patients_per_nurse_max`** (C-16), two wording points.
   (a) The quotation is truncated: the regulation reads "...shall be 1:4 or fewer at all times that patients
   are receiving treatment". (b) "introduced 13 Jan 2026": the fetched bill PDF says "PRE-FILED FOR
   INTRODUCTION IN THE 2026 SESSION" and "Sponsorship Updated As Of: 6/30/2026"; no 13 January date
   appears in it. The same date is in evidence record E-49 (not in the sample).
6. **`catalog/event.yaml`, `mass_casualty.window_min`** (C-06). No factual error. The note says the IQR
   "implies" about three hours; that is a judgement, since the source gives only a median and IQR of
   blast-to-arrival time (97, 43-139 min) and no arrival span. Wording it as an assumption informed by the
   IQR would be accurate.

## Limits of this audit

- CDC and BLS pages were read through a summarising fetch tool, not as raw HTML.
- Sources that are not open access (for example Brunner, Bohannon, Ankrum, Rizer, Singer, Landrigan,
  Hamden) were seen here only as abstracts, as they were by the original agent; the cited numbers are all
  in those abstracts.
- 63 of 78 evidence records were not examined. The one error found outside the sample (E-09) surfaced
  only because it shares a source with a catalog attribute.
