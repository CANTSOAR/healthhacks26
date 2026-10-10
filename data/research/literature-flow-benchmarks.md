# Published ED flow benchmarks for external proxy candidates

These extracts are published-study comparators for a future simulation prior registry. They are not measurements of a target hospital and must not be presented as local facts. “Observed” refers to measurements collected at the study site; “modeled input” refers to parameters authors entered into a simulation. Every row remains an `external_proxy_candidate` pending a decision about scope and validation.

## U.S. primary studies

| Flow component | Extract | Evidence type | Source |
|---|---|---|---|
| Arrival volume | Mean 769 arrivals/week as a site-specific input; the paper describes a heterogeneous Poisson process with hourly rates estimated from average counts in each of the 168 hours of a week. The numerical hourly rate vector is not published in the extract. | Author-entered site-specific simulation input, not raw arrival records. | Jones & Evans, “An Agent Based Simulation Tool for Scheduling Emergency Department Physicians,” AMIA 2008, Table 1 and Methods. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2656074/) |
| Routing/admission | 21% admitted; same paper reports 18% ambulance arrivals, 2% transfers, 1% left without treatment, 4% left against medical advice, and 0.07% expired as site-specific simulation inputs. | Author-entered model parameters; not independently tabulated observations. | Jones & Evans, Table 1. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2656074/) |
| Initial physician evaluation | Observed door-to-doctor median 21.93 min (IQR 14.05–32.38); mean 25.83 min. These are reported separately from the simulation's output. | Observed site data, used for model validation. | Jones & Evans, Results. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC2656074/) |
| Arrival to treatment room | Median 38.4 min (SD 21) on days with discharged-patient ED LOS ≤154 min, versus 88.8 min (SD 31.5) on days >154 min. | Daily operational measurements summarized as group medians; not a patient-level distribution. | Krall et al., “Hospital Factors Impact Variation in Emergency Department Length of Stay More Than Physician Factors,” 2014, Table 2. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC3966443/) |
| Admission/boarding | Median admission-decision-to-ED-departure 199 min (SD 99.7) for days with discharged-patient LOS ≤154 min and 237 min (SD 141) for days >154 min. | Daily operational measurements; interval explicitly begins at admission decision and ends at physical ED departure. | Krall et al., Table 1 definition and Table 2. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC3966443/) |
| Arrival to triage | In a subgroup that did not proceed directly to a bed or triage (7,795/50,576 visits), median 11 min (IQR 5–19; range 1–105). | Directly observed arrival-to-triage interval. | Houston et al., “Waiting for Triage: Unmeasured Time in Patient Flow,” 2015, Methods/Results. [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC4307723/) |

## Interpretation and limits

- These are cross-hospital literature comparators only. They do not establish local arrivals, admissions, acuity mix, service times, bed-cleaning time, diagnostic turnaround, or staff capacity.
- Jones and Evans report modeling parameters for one Utah Level I trauma center. The arrival process is explicitly represented as a heterogeneous Poisson process by hour of week, but the paper does not provide the actual hourly rates as a reusable numeric distribution. Their 21% admission share and other disposition shares are model inputs.
- Jones and Evans separately report observed door-to-doctor data (mean/median/IQR); that endpoint is initial physician evaluation, not total ED length of stay. Its validation sample count is not stated.
- Krall et al. analyze daily average intervals at one Corpus Christi county hospital over one year. The paper does not state calendar dates in the opened methods text. Its 154-minute day-grouping threshold comes from the 2008 NHAMCS national median LOS; the reported door-to-room and boarding measurements remain single-site.
- Houston et al. observe a selected pre-triage subgroup. The 11-minute median is not a whole-ED arrival-to-provider estimate.
- No diagnostic turnaround distribution is included here: the opened candidates did not provide a clearly bounded, reusable observed time distribution for diagnostics. Avoid substituting overall LOS for diagnostic or active service duration.
- Qualitative confidence labels in the JSON describe the evidence's fit to the stated quantity and transferability, not statistical confidence intervals. The studies' reported SDs, IQRs, and intervals are preserved where available.
