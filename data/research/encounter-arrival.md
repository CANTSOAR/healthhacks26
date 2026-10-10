# Emergency encounter arrival and waiting-room evidence

This evidence set covers front-door branches and the state after initial contact: self-presenting versus ambulance arrivals, quick registration versus clinical assessment, EMS handover and placement, reassessment while waiting, and departure before physician assessment. These are external workflow references, not RWJ observations. It does not establish RWJ identity-match performance, registration duration, arrival-mode mix, triage timing, waiting-room monitoring policy, or LWBS rate.

## Evidence records

### encounter-arrival-route-mix-sweden

**Source:** [Pathways to the emergency department - a national, cross-sectional study in Sweden](https://bmcemergmed.biomedcentral.com/articles/10.1186/s12873-022-00619-3) (10.1186/s12873-022-00619-3), Abstract; Results, pathway to ED and admission by pathway.  
**Setting/period/N:** Adult arrivals at 43 of Sweden’s 72 emergency departments; all patients present over an observed 24-hour period. 2018-04-25 (single 24-hour observation). 3,875 adults overall; complete pathway data n=3,693; triage acuity recorded for n=3,365.  
**Measure:** Observed pathway composition and admission share by arrival pathway — {"walk_in_n": 1310, "walk_in_percent_of_pathway_complete": 34, "ambulance_n": 920, "ambulance_percent_of_pathway_complete": 24, "ambulance_admission_percent": 53, "overall_admission_percent": 27} patients; percent of pathway-complete sample or pathway subgroup.  
**Evidence:** National cross-sectional direct observation across 43 EDs: self-referred walk-in was the commonest pathway, followed by ambulance; ambulance arrivals had the highest admission rate.  
**Limitations:** One day, Sweden; nonrandom pathway groups differ in age and acuity. Does not specify registration or handoff durations, and admission proportions are not local arrival probabilities.  
**Scenario use:** Represent arrival mode as an explicit branch into front-door workflows, with ambulance arrivals carrying a different acuity/admission mix only as an external scenario reference; do not assign RWJ rates from this study.  
**Access:** primary_full_text_and_abstract_inspected_via_publisher_open_access; inspected: https://bmcemergmed.biomedcentral.com/articles/10.1186/s12873-022-00619-3

### encounter-arrival-registration-to-vitals

**Source:** [A Novel Approach to Addressing an Unintended Consequence of Direct to Room: The Delay of Initial Vital Signs](https://westjem.com/articles/a-novel-approach-to-addressing-an-unintended-consequence-of-direct-to-room-the-delay-of-initial-vital-signs.html) (10.5811/westjem.2017.12.35068), Abstract and Methods/Results; TTVS defined as quick registration to first documented vital sign.  
**Setting/period/N:** Single academic tertiary ED, Staten Island University Hospital, New York; ambulatory entry via quick registration and direct-to-room or formal triage pathways. Control 2014-11-01 to 2015-05-01; intervention 2015-11-01 to 2016-05-01; included 07:00-23:00 arrivals. Pre n=37,900; post n=39,392 encounters.  
**Measure:** Mean time from quick registration to first documented vital sign — {"pre_mean_minutes": 15.3, "post_mean_minutes": 9.8, "absolute_reduction_minutes": 5.5, "relative_reduction_percent": 35} minutes per encounter; percent reduction.  
**Evidence:** Retrospective before-after cohort reports means and Ns; intervention placed a patient-care assistant at a waiting-area vital-sign station coupled to quick registration.  
**Limitations:** Single-center nonrandomized before/after implementation and restricted hours; pre/post cohort dates are a year apart. Does not quantify identity verification failure, completion of full triage, or effects in EMS arrivals.  
**Scenario use:** Model quick demographic/chief-complaint registration, initial vital signs, and formal nurse triage as distinct events; use the pre/post timing only as an external workflow scenario, never as RWJ timing.  
**Access:** primary_full_text_and_abstract_inspected; inspected: https://westjem.com/articles/a-novel-approach-to-addressing-an-unintended-consequence-of-direct-to-room-the-delay-of-initial-vital-signs.html

### encounter-arrival-waiting-reassessment

**Source:** [The effect of emergency department crowding on reassessment of children with critically abnormal vital signs](https://pubmed.ncbi.nlm.nih.gov/25308134/) (10.1111/acem.12478), Abstract, Methods and Results; triage vital-sign reassessment, electronic alert after 1 hour.  
**Setting/period/N:** Pediatric ED at Cincinnati Children’s Hospital Medical Center; patients placed in regular ED rooms after critically abnormal triage vital signs. 2006-09-01 to 2009-05-01 (2.5 years). 9,976 patients with critically abnormal triage vital signs among 253,408 visits (3.9%).  
**Measure:** Mean time to repeat vital signs and association between crowding and reassessment rate — {"mean_reassessment_minutes": 84, "adjusted_rate_ratio_per_10_additional_lobby_patients": 0.94, "95_percent_CI_lobby": [0.93, 0.96], "adjusted_rate_ratio_per_10_additional_overall_census": 0.97, "95_percent_CI_census": [0.97, 0.98]} minutes; relative reassessment rate per 10 patients.  
**Evidence:** Retrospective cross-sectional cohort, Cox time-to-event analysis; electronic alerts prompted reassessment after one hour. Crowding correlated with slower reassessment.  
**Limitations:** Pediatric single-center retrospective study; sample restricted to patients with critically abnormal triage vitals placed in regular rooms, not all waiting-room arrivals. Association does not establish causation or a staffing standard.  
**Scenario use:** Represent waiting after triage as an active monitored state with a reassessment due event and escalation pathway; test missed/delayed reassessment under congestion without borrowing a RWJ interval or probability.  
**Access:** primary_abstract_and_bibliographic_record_inspected; inspected: https://pubmed.ncbi.nlm.nih.gov/25308134/

### encounter-arrival-lwbs-pretriage-and-crowding

**Source:** [Factors Associated with Patients Leaving Without Being Seen in a Canadian Emergency Department](https://pmc.ncbi.nlm.nih.gov/articles/PMC12815564/) (10.5811/westjem.47302), Abstract; Results; Table, LWBS denominator and adjusted operational factors.  
**Setting/period/N:** The Ottawa Hospital General Campus, tertiary-care/cancer-center ED, Canada. 2022-05-01 to 2024-04-30. 170,536 ED encounters; 15,473 LWBS; 2,716 left before triage.  
**Measure:** LWBS and pre-triage departure shares; adjusted odds change with queue counts — {"lwbs_n": 15473, "lwbs_percent_reported_abstract": 9.1, "pretriage_departure_n": 2716, "pretriage_percent_of_all_encounters": 1.6, "adjusted_OR_per_5_waiting_to_be_seen": 1.169, "95_percent_CI_waiting_OR": [1.161, 1.177], "adjusted_OR_per_5_seen_awaiting_disposition": 1.096, "95_percent_CI_disposition_OR": [1.087, 1.104]} encounters; percent; adjusted odds ratio per five people.  
**Evidence:** All-encounter retrospective cohort; the paper reports 9.1% in abstract and 9.2% in detailed results (15,473/170,536 is about 9.1%). Pre-triage departures were separately counted. Adjusted odds rose with both waiting-patient and awaiting-disposition counts.  
**Limitations:** Single Canadian center, observational design; records did not include arrival method and authors did not report downstream outcomes for departures. Percent rounding differs between abstract and detailed text.  
**Scenario use:** Keep registered-but-not-triaged departure and post-triage/pre-physician LWBS as separate absorbing outcomes, linked to queue state. Treat reported associations as external evidence, not transferable departure probabilities.  
**Access:** primary_full_text_inspected; inspected: https://pmc.ncbi.nlm.nih.gov/articles/PMC12815564/

### encounter-arrival-official-ems-handover-15min

**Source:** [Guidance for emergency departments: initial assessment](https://www.england.nhs.uk/guidance-for-emergency-departments-initial-assessment/) (official guidance), Patient arrival / Ambulance handover section.  
**Setting/period/N:** NHS England emergency department guidance, England. Guidance first published 2022-08-12; page updated 2022-11-09. Not applicable; operational guidance, not a cohort.  
**Measure:** Target process for non-pre-alerted ambulance handover — "Complete handover following locally agreed processes within 15 minutes of arrival; pre-alerted patients needing a clinical team should be received immediately; hospital responsibility for clinical assessment/treatment begins when ambulance arrives at department." minutes from ED arrival; workflow requirement.  
**Evidence:** Official NHS England guidance distinguishes heralded ambulance patients from unheralded self-presenters, sets separate handover process expectations, and states responsibility transfer at arrival.  
**Limitations:** England operational guidance, not an observed compliance estimate; local pathways and regulatory context may differ. Does not define a US hospital’s identity/registration steps.  
**Scenario use:** Model ambulance arrival, pre-alert, immediate clinical receipt versus standard handover, then destination; keep administrative registration from delaying clinical ownership. Use 15 minutes as policy reference only, not actual RWJ handover time.  
**Access:** official_guidance_page_inspected; inspected: https://www.england.nhs.uk/guidance-for-emergency-departments-initial-assessment/

### encounter-arrival-official-ems-handoff-branching

**Source:** [Protocol for the handover of ambulance patients in the Emergency Department process map](https://www.health.vic.gov.au/sites/default/files/2025-09/protocol-handover-ambulance-patients-ed-process-map_0.pdf) (official guidance), Original one-page PDF inspected: pre-arrival review; IMIST-AMBO handover; triage/registration; transfer to available space or stretcher hold with regular triage-nurse review and escalation if no space within local thresholds.  
**Setting/period/N:** Victorian Department of Health ambulance-to-ED handover process guidance. Published/updated 2025 (PDF path indicates September 2025). Not applicable; official process map, not a cohort.  
**Measure:** Conditional destination after ambulance triage/handover — "After arrival and clinical handover, ED location is immediately available as treatment space or waiting room depending on patient condition and acuity; if no ED location is available, patient remains on ambulance stretcher with regular triage-nurse review. Process map separately records triage and registration." workflow states and branches.  
**Evidence:** Official Victorian government process map explicitly shows arrival, handover, triage, registration, location assignment and the no-location branch with repeat triage-nurse review.  
**Limitations:** A stated process design, not measured compliance, frequency, or elapsed-time distribution; Australian workflow may not match RWJ.  
**Scenario use:** Add distinct EMS stretcher-hold, repeat nurse review, registration, and placement transitions. Do not infer how often the hold occurs or its duration.  
**Access:** official_process_map_PDF_downloaded_and_text_extracted; inspected: https://www.health.vic.gov.au/sites/default/files/2025-09/protocol-handover-ambulance-patients-ed-process-map_0.pdf

### encounter-arrival-waiting-area-monitoring-feasibility

**Source:** [Surveillance of Patients in the Waiting Area of the Department of Emergency Medicine](https://pmc.ncbi.nlm.nih.gov/articles/PMC4697987/) (10.1097/MD.0000000000002211), Abstract; Methods and Results, waiting-area wireless vital sign monitoring.  
**Setting/period/N:** Single high-volume German emergency department; selected patients with acute cardiac/pulmonary symptoms or potentially life-threatening conditions. Study period not specified in the inspected abstract/text excerpt. 230 enrolled patients; 4 terminated participation early; 684 monitoring hours.  
**Measure:** Duration of waiting-area vital-sign observation in feasibility cohort — {"median_monitoring_minutes_per_patient": 178, "iqr_minutes": [118, 258], "total_monitoring_hours": 684, "early_termination_n": 4} minutes per patient (median, IQR); total hours.  
**Evidence:** Single-center observational cross-sectional feasibility study reports enrollment, monitoring time, aggregate monitored hours, and use of continuous wireless vital-sign data to assist care.  
**Limitations:** Selected higher-risk consenting patients, small feasibility cohort, no control group and no estimate of deterioration incidence or outcome benefit; source period unavailable from excerpt.  
**Scenario use:** Treat waiting-room monitoring and detection/escalation as a possible staffed capability for a high-risk subgroup, not a default universal workflow or a probability model.  
**Access:** primary_full_text_inspected_via_NCBI_PMC_BioC_JSON; inspected: https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/PMC4697987/unicode

## Synthesis and gaps

The supported process graph is arrival-mode-specific. Ambulance arrivals can be pre-alerted, handed over directly to clinical staff, held on the stretcher pending space with repeat nursing review, or placed in a treatment space/waiting area according to acuity. Ambulatory arrivals may receive brief demographic/chief-complaint registration and vital signs before formal triage; direct-to-room pathways can create a measurable delay in first documented vital signs unless a specific station is staffed. Following triage, waiting remains an active state: deterioration surveillance/reassessment can be delayed under crowding, and departure can occur before triage or after triage but before physician assessment.

The source studies do not support a single generic “arrival-to-care” duration or common departure probability. Identity/registration accuracy, ID-band process, registration completion by arrival mode, triage-to-reassessment interval distribution, clinical deterioration incidence, escalation response times, and RWJ-specific LWBS are unresolved and require local workflow evidence. No values here should be populated as RWJ observations or used as unqualified probabilities.
