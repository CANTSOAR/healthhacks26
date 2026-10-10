# Operations evidence records

Prepared 2026-10-10 by the overnight operations-research agent for HospitalGym. This file covers the operations
side that the existing research leaves open: emergency department (ED) flow, boarding, staffing, and simulation
and reinforcement learning (RL) for hospital operations. Challenge requirements, sponsor resources, competing
products and clinical-education evidence are in the teammate's files ([README](README.md)) and are not repeated.

**How to read a record.** Every source was fetched and read during this run. `Read:` says how much: *abstract*
(Europe PMC or arXiv record), *full text* (open-access text or PDF), or *page* (web page or regulation text).
Fields a source does not report are written "not reported". Records E-68 to E-78 were added in a second pass and sit at the end regardless of topic; each says which section it belongs to. Numbers are quoted from the source; anything
computed by this agent is labelled *derived* and appears only under "Implication". Bibliographic details
(volume, pages, DOI) come from the Europe PMC or arXiv metadata record for the item. The short notes for the
simulator and RL workstreams are in [operations-design-implications.md](operations-design-implications.md);
parameter ranges are in [operations-parameter-ranges.yaml](operations-parameter-ranges.yaml).

Sections: A arrivals, service and leaving without being seen · B flow, boarding and the manager's levers ·
C simulation and RL · D AI patients and automated scoring · E staffing · F equipment, spaces and events.

---

## A. Arrivals, service times, productivity, leaving without being seen (LWBS)

### E-01 Waiting Patiently: An Empirical Study of Queue Abandonment in an Emergency Department
- **Authors, year:** Batt RJ, Terwiesch C. Management Science 61(1):39-59, 2015. Read: full text of the authors' working-paper PDF.
- **Link:** https://faculty.wharton.upenn.edu/wp-content/uploads/2013/04/Waiting_Patiently-MS.pdf (published DOI 10.1287/mnsc.2014.2058)
- **Design:** Retrospective econometric study of abandonment (probit models per triage level, offered wait estimated from neighbouring patients).
- **Setting:** One large US urban academic ED with a fast track; patients are not told their triage level or queue position.
- **Sample:** "over 180,000 patient visits"; analysed ESI 2 n=27,538, ESI 3 n=65,773, ESI 4 n=39,878, ESI 5 n=10,509.
- **Comparator:** Within-sample variation in wait, queue length and observed flows.
- **Outcomes:** Table 1: mean wait 1.0 / 1.9 / 1.3 / 1.3 hours and LWBS 1.7% / 9.5% / 4.7% / 7.4% for ESI 2 / 3 / 4 / 5; mean service time 3.7 / 4.0 / 1.8 / 1.2 hours; 68% and 67% of ESI 4 and 5 go to fast track. ESI 1 patients "do not abandon". For moderate-severity patients one more person in the queue raises abandonment by 0.5 percentage points, "equivalent to a 15 minute increase in wait time" (the published abstract gives 25 minutes); one more departure that keeps first-come order lowers it by 0.6 points; an arrival of a sicker patient raises it by 1 point; a test ordered at triage lowers it by 1.8 points.
- **Limitations:** Single hospital; abandonment times are not observed, so the offered wait of leavers is estimated; working-paper and published effect sizes differ.
- **Implication:** The only per-acuity wait-and-LWBS table found. *Derived* exponential patience means (theta = -wait / ln(1 - LWBS)): about 3,500 / 1,150 / 1,600 / 1,000 minutes for ESI 2-5. Patience should also fall with visible queue length, and early test ordering is a direct LWBS lever.

### E-02 Patient Characteristics and Clinical Process Predictors of Patients Leaving Without Being Seen from the Emergency Department
- **Authors, year:** Rathlev NK, Visintainer P, Schmidt J, Hettler J, Albert V, Li H. West J Emerg Med 21(5), 2020. Read: full text.
- **Link:** https://westjem.com/articles/patient-characteristics-and-clinical-process-predictors-of-patients-leaving-without-being-seen-from-the-emergency-department.html
- **Design:** Cross-sectional predictive model with derivation and validation cohorts.
- **Setting:** Adult ED, 66 licensed bays, about 95,000 annual visits (Baystate, Massachusetts), four seasonally spread months.
- **Sample:** 30,679 visits, 29,382 analysed (derivation 14,937, validation 14,445).
- **Comparator:** Patients seen versus LWBS.
- **Outcomes:** LWBS 7.5% of analysed visits (7.2% of all). Adjusted odds ratios (Table 3): door-to-provider 30-59 min 1.34 (0.95-1.89), 60-89 min 1.69 (1.20-2.39), 90-119 min 1.87 (1.28-2.73), 120+ min 1.99 (1.34-2.96) versus under 30; per one-step-lower acuity (ESI) 2.02 (1.85-2.21); per person in the waiting room 1.05 (1.03-1.06); per boarder 1.02 (1.01-1.03); ambulance arrival 0.29 (0.23-0.36). Validation AUC 0.85.
- **Limitations:** Single centre; process measures hourly; median wait of leavers not reported.
- **Implication:** A hospital of RWJUH's volume; gives the shape of LWBS against wait (steep to 90 minutes, then flat), and the size of the queue-length and boarding effects. Ambulance arrivals should have about a third of the walk-in abandonment hazard.

### E-03 Hospital determinants of emergency department left without being seen rates
- **Authors, year:** Hsia RY, Asch SM, Weiss RE, Zingmond D, Liang LJ, Han W, McCreath H, Sun BC. Ann Emerg Med 58(1):24-32, 2011. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2011.01.009
- **Design:** Cross-sectional, all California acute-care hospitals with an ED, 2007.
- **Sample:** 9.2 million visits, 262 hospitals.
- **Comparator:** Between-hospital variation.
- **Outcomes:** LWBS median 2.6%, range 0% to 20.3%. Odds x1.15 per 10-point rise in poorly insured share, x0.86 per $10,000 household income; county ownership OR 2.09, trauma centre 1.62, teaching 2.14.
- **Limitations:** Administrative data; hospital-level; 2007.
- **Implication:** Validation target: baseline LWBS near 2-3% for a typical ED, with teaching trauma centres roughly doubling the odds. Payer mix belongs in the patience model if it is ever refined.

### E-04 Identifying Patient Door-to-Room Goals to Minimize Left-Without-Being-Seen Rates
- **Authors, year:** Pielsticker S, Whelan L, Arthur AO, Thomas S. West J Emerg Med 16(5):611-618, 2015. Read: full text.
- **Link:** https://pmc.ncbi.nlm.nih.gov/articles/PMC4644024
- **Design:** Retrospective analysis with the day as the unit.
- **Setting:** ED of a 700-bed US hospital, about 50,000 visits a year, 30 beds plus 8 fast-track.
- **Sample:** 365 days (Aug 2013-Aug 2014).
- **Outcomes:** Median daily LWBS 0.8% (IQR 0-1.7). Days meeting LWBS under 1%: 87.5% when mean door-to-room was 20 minutes or less, 61.1% at 31-35 minutes, 34.4% at 36-40 minutes, 25.8% above 60. Odds of meeting the goal 0.26 (0.13-0.53) for 21-35 versus 20 or less.
- **Limitations:** Single centre, daily averages, arbitrary 1% target.
- **Implication:** A simple calibration check: simulated days with mean door-to-room under 20 minutes should almost always have LWBS under 1%.

### E-05 Mortality and Return Visit Frequency Among Emergency Department Patients Who Leave Without Being Seen at a Regional Health Care System
- **Authors, year:** Joseph JW, Bukhman AK, Baymon DE, Lai-Becker MW, Im DD, Nentwich LM, Chen PC, Sánchez LD. Jt Comm J Qual Patient Saf 51(7-8):466-473, 2025. Read: abstract.
- **Link:** https://doi.org/10.1016/j.jcjq.2025.02.008
- **Design:** Retrospective cohort, 10 EDs in one US system, 2019-2023.
- **Sample:** 1,474,395 visits; 17,523 (1.2%) LWBS.
- **Comparator:** Patients evaluated and discharged.
- **Outcomes:** LWBS associated with return within 72 hours (adjusted OR 2.56, 2.50-2.62), 30-day ICU admission (1.35) and 30-day mortality (2.59, 1.90-3.53).
- **Limitations:** Observational; baseline rates not in the abstract.
- **Implication:** Conflicts with E-09 (Ontario found no excess harm). In the US setting LWBS should carry a safety penalty, not only lost revenue; and a share of LWBS patients return within 72 hours as new arrivals.

### E-06 A data-driven model of an emergency department
- **Authors, year:** Whitt W, Zhang X. Operations Research for Health Care 12:1-15, 2017. Read: full text (author manuscript, NSF public access).
- **Link:** https://par.nsf.gov/servlets/purl/10023792 (published DOI 10.1016/j.orhc.2016.11.001)
- **Design:** Statistical modelling of public arrival and length-of-stay data; a time-varying infinite-server model.
- **Setting:** Internal-medicine ED of Rambam Hospital, Haifa, Israel (about 1,000 beds), 25 weeks, Dec 2004-May 2005.
- **Sample:** 23,409 arrivals in the 25-week table (mean 105 to 162 a day by weekday).
- **Outcomes:** Arrival rate lowest about 06:00, rising rapidly to a peak just before noon, declining irregularly with a steep drop around midnight. Daily totals are overdispersed against a Poisson process: variance-to-mean about 1.5. Busiest weekday has 54% more arrivals than the quietest (162.0 vs 105.4). Length-of-stay distribution and admission probability also vary by time of day; mean stay of admitted patients 4.30 hours after removing immediate transfers. Occupancy peaks lag arrival peaks.
- **Limitations:** Israel (Sunday is the first working day), one unit, 2004-05.
- **Implication:** Use a non-homogeneous Poisson process with a day-level random multiplier (dispersion about 1.5), not a plain Poisson; validate occupancy lag.

### E-07 The challenge of predicting demand for emergency department services
- **Authors, year:** McCarthy ML, Zeger SL, Ding R, Aronsky D, Hoot NR, Kelen GD. Acad Emerg Med 15(4):337-346, 2008. Read: abstract.
- **Link:** https://doi.org/10.1111/j.1553-2712.2008.00083.x
- **Design:** Poisson regression of hourly arrivals on temporal, climate and patient factors.
- **Setting:** One US academic ED, one year (8,760 hours).
- **Outcomes:** High- and low-acuity arrivals have significantly different hourly patterns and need separate models; variance about equal to the mean within an hour; no residual autocorrelation; observed counts fell inside 50% and 90% prediction intervals 50% and 90% of the time.
- **Limitations:** Single site; sample size of visits not in the abstract.
- **Implication:** Within an hour, Poisson is adequate once the rate is right; acuity-specific hourly profiles are worth having (sicker patients arrive more evenly through the night).

### E-08 Modelling attending physician productivity in the emergency department: a multicentre study
- **Authors, year:** Joseph JW, Davis S, Wilker EH, Wong ML, Litvak O, Traub SJ, Nathanson LA, Sanchez LD. Emerg Med J 35(5):317-322, 2018. Read: full text.
- **Link:** https://doi.org/10.1136/emermed-2017-207194 (PMC5916102)
- **Design:** Retrospective cohort; generalised estimating equations for new patients per shift hour.
- **Setting:** Three community hospitals, north-eastern USA, 2014-2016; 8- and 9-hour shifts, last hour for wrap-up.
- **Sample:** 207,169 patients (200,772 analysed), 64 physicians, 9,822 shifts.
- **Outcomes:** 15.0 (SD 4.7), 20.9 (6.4) and 13.2 (3.8) patients per shift. First-hour rate 2.97, 2.95, 2.17 new patients; change from hour 1 at site 1: hour 2 -1.00, hour 3 -1.40, hour 4 -1.61, hour 5 -1.67, hour 6 -1.69, hour 7 -2.00, hour 8 -2.56 (site 2 -1.35 to -2.69; site 3 -0.79 to -1.43). Each extra arrival raises pickup by 0.12 to 0.42. Other physicians present slightly lower it.
- **Limitations:** Community sites; new-patient pickup, not total work; no acuity split.
- **Implication:** A physician front-loads new patients and then works them up. Model pickup rate by hour-in-shift (about 3, 2, 1.6, 1.4, 1.3, 1.3, 1.0, 0.4 at site 1), which makes shift start times a lever.

### E-09 Association between waiting times and short term mortality and hospital admission after departure from emergency department
- **Authors, year:** Guttmann A, Schull MJ, Vermeulen MJ, Stukel TA. BMJ 342:d2983, 2011. Read: full text.
- **Link:** https://doi.org/10.1136/bmj.d2983
- **Design:** Population-based retrospective cohort.
- **Setting:** High-volume EDs in Ontario, Canada, 2003-2007.
- **Sample:** 13,934,542 seen and discharged; 617,011 LWBS.
- **Comparator:** Shifts with mean length of stay under 1 hour.
- **Outcomes:** Shift mean stay 6 hours or more: 7-day death adjusted OR 1.79 (1.24-2.59) and admission 1.95 for high-acuity patients; 1.71 (1.25-2.35) and 1.66 for low-acuity. LWBS itself not associated with adverse events. Authors' estimate: one hour less mean stay could have cut deaths by 558 of 8,625 (6.5%) among high-acuity and 261 of 2,054 (12.7%) [totals for the whole non-admitted cohort including LWBS; seen-and-discharged only: 8,502 and 1,998] among low-acuity discharged patients.
- **Limitations:** Observational; Canadian universal coverage; exposure is the shift average.
- **Implication:** The only source that prices waiting for patients who go home. *Derived*: about 8e-5 (high acuity) and 4e-5 (low acuity) attributable deaths per patient-hour.

### E-10 Emergency Department Mean Physician Time per Patient and Workload Predictors ED-MPTPP
- **Authors, year:** Wrede J, Wrede H, Behringer W. J Clin Med 9(11):3725, 2020. Read: full text.
- **Link:** https://doi.org/10.3390/jcm9113725
- **Design:** Prospective time measurement with a purpose-built app; regression model.
- **Setting:** One German university hospital ED, one year.
- **Sample:** 202 patients, 32 physicians.
- **Outcomes:** Mean physician time per patient 47 minutes (SD 34). By ESI: levels 1+2 76 (42), level 3 48 (27), level 4 27 (15), level 5 18 (11). Fully trained specialists 31 (16). Model R2 0.45.
- **Limitations:** Small, one site, Germany; ESI 1 and 2 pooled (two ESI 1 patients).
- **Implication:** Per-acuity provider time with spread: CV 0.55 to 0.61 at every level, supporting a lognormal with CV about 0.6. Specialist-scaled times (x 31/47) are about 50 / 32 / 18 / 12 minutes, matching the Wave 0 placeholders and the US shift averages in E-08.

### E-11 Evaluation of the Emergency Severity Index in US Emergency Departments for the Rate of Mistriage
- **Authors, year:** Sax DR, Warton EM, Mark DG, et al. JAMA Netw Open 6(3):e233404, 2023. Read: abstract.
- **Link:** https://doi.org/10.1001/jamanetworkopen.2023.3404
- **Design:** Retrospective cohort with an algorithmic definition of mis-triage.
- **Setting:** 21 EDs, Kaiser Permanente Northern California, 2016-2020.
- **Sample:** 5,315,176 encounters.
- **Outcomes:** Mis-triage 32.2% (overtriage 28.9%, undertriage 3.3%). Sensitivity of ESI 1-2 for patients receiving a life-stabilising intervention 65.9%. Undertriage relative risk +18.5% for Black versus White patients.
- **Limitations:** One integrated system; reference standard is resource use in hindsight.
- **Implication:** Default mis-triage probability about 0.32 with a 9:1 over-to-under split; a third of truly critical patients are not flagged ESI 1-2.

### E-12 Emergency Department Triage Accuracy and Delays in Care for High-Risk Conditions
- **Authors, year:** Sax DR, Warton EM, Mark DG, Reed ME. JAMA Netw Open, 2025. Read: abstract.
- **Link:** https://doi.org/10.1001/jamanetworkopen.2025.8498
- **Design:** Retrospective cohort; lognormal time-to-event models.
- **Sample:** 5,929 patients with subarachnoid haemorrhage, aortic dissection or STEMI; 36.7% undertriaged.
- **Outcomes:** Undertriage delayed antihypertensive orders by 33.3 minutes and beta-blocker orders by 17.6 minutes, lengthened ED stay by 64 minutes for aortic dissection; no meaningful delay for STEMI.
- **Limitations:** One system; selected diagnoses.
- **Implication:** The cost of undertriage is tens of minutes of treatment delay, not hours; models time-to-event as lognormal, as the simulator does.

### E-13 Triage Performance in Emergency Medicine: A Systematic Review
- **Authors, year:** Hinson JS, Martinez DA, Cabral S, George K, Whalen M, Hansoti B, Levin S. Ann Emerg Med 74(1):140-152, 2019. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2018.09.022
- **Design:** Systematic review; 182 studies eligible, 50 compared.
- **Outcomes:** 3% to 45% of hospitalised patients had been triaged to levels 4-5; sensitivity under 80% for critical-illness outcomes; kappa above 0.8 in only 11 of 42 evaluations.
- **Implication:** Triage error is structural; admission probability for ESI 4-5 should not be zero.

### E-14 The emergency severity index triage algorithm version 2 is reliable and valid
- **Authors, year:** Eitel DR, Travers DA, Rosenau AM, Gilboy N, Wuerz RC. Acad Emerg Med 10(10):1070-1080, 2003. Read: abstract. (Earlier single-study version: Wuerz RC et al., Acad Emerg Med 7(3):236-242, 2000, weighted kappa 0.80, 493 patients.)
- **Link:** https://doi.org/10.1111/j.1553-2712.2003.tb00577.x
- **Design:** Prospective cohort with stratified sampling, seven US EDs.
- **Sample:** Validity cohort n=1,042.
- **Outcomes:** Hospitalisation by ESI level 83% / 67% / 42% / 8% / 4%; 60-day all-cause mortality 25% / 4% / 2% / 1% / 0%. Weighted kappa 0.69 to 0.87.
- **Limitations:** 2003, ESI version 2, academic sites.
- **Implication:** Literature cross-check for the data agent's measured admission probabilities, and the ceiling for any mortality the simulator attributes by acuity.

---

## B. Patient flow, boarding, diversion, and the manager's levers

### E-15 Association between delays to patient admission from the emergency department and all-cause 30-day mortality
- **Authors, year:** Jones S, Moulton C, Swift S, Molyneux P, Black S, Mason N, Oakley R, Mann C. Emerg Med J 39(3):168-173, 2022. Read: abstract.
- **Link:** https://doi.org/10.1136/emermed-2021-211572
- **Design:** Cross-sectional retrospective observational, every major ED in England, Apr 2016-Mar 2018.
- **Sample:** 7,472,480 admissions (5,249,891 patients); 433,962 deaths in 30 days (8.71%).
- **Outcomes:** Linear rise in standardised mortality from 5 hours after arrival to 12 hours; +8% at 6-8 hours; "For every 82 admitted patients whose time to inpatient bed transfer is delayed beyond 6 to 8 hours ... there is one extra death."
- **Limitations:** Observational; time measured from arrival, not from the decision to admit.
- **Implication:** The strongest dose-response for boarding harm. Start the penalty about 5 hours after arrival; about 1.2 percentage points of 30-day mortality at 6-8 hours.

### E-16 The association between length of emergency department boarding and mortality
- **Authors, year:** Singer AJ, Thode HC, Viccellio P, Pines JM. Acad Emerg Med 18(12):1324-1329, 2011. Read: abstract.
- **Link:** https://doi.org/10.1111/j.1553-2712.2011.01236.x
- **Design:** Retrospective cohort, suburban US academic ED (90,000 visits a year), 2005-2008.
- **Sample:** 41,256 admissions.
- **Outcomes:** In-hospital mortality 2.5% when boarded under 2 hours, 4.5% at 12 hours or more; mean hospital stay 5.6 days (SD 11.4) under 2 hours versus 8.7 days (SD 16.3) over 24 hours; persisted after adjustment.
- **Limitations:** Single site; residual confounding (sicker and harder-to-place patients board longer).
- **Implication:** *Derived* ceilings: about 0.0017 deaths and 2.3% of inpatient stay per boarding hour.

### E-17 The association between hospital overcrowding and mortality among patients admitted via Western Australian emergency departments
- **Authors, year:** Sprivulis PC, Da Silva JA, Jacobs IG, Frazer AR, Jelinek GA. Med J Aust 184(5):208-212, 2006. Read: abstract.
- **Link:** https://doi.org/10.5694/j.1326-5377.2006.tb00416.x
- **Sample:** 62,495 emergency admissions, three tertiary hospitals, 2000-2003.
- **Outcomes:** Overcrowding Hazard Scale above 2: hazard ratio for death 1.3 at day 2 and day 7, 1.2 at day 30. Among deaths, risk ratio 1.1 per hour of ED stay and 1.2 (1.1-1.3) per hour of wait for a physician.
- **Implication:** Hospital occupancy and ED occupancy jointly drive the hazard; a combined occupancy index is a reasonable observation feature and safety term.

### E-18 Overnight Stay in the Emergency Department and Mortality in Older Patients
- **Authors, year:** Roussel M, Teissandier D, Yordanov Y, et al. JAMA Intern Med 183(12):1378-1385, 2023. Read: abstract.
- **Link:** https://doi.org/10.1001/jamainternmed.2023.5961
- **Design:** Prospective cohort, 97 French EDs, 12-14 Dec 2022, patients 75 and older admitted.
- **Sample:** 1,598 (707 spent midnight-08:00 in the ED; 891 reached a ward before midnight).
- **Outcomes:** In-hospital mortality 15.7% vs 11.1% (adjusted risk ratio 1.39, 1.07-1.81); adverse events aRR 1.24; length of stay 9 vs 8 days (rate ratio 1.20, 1.11-1.31); aRR 1.81 for patients needing help with daily living.
- **Implication:** Age band 65+ should carry a larger boarding penalty; overnight boarding is the worst case.

### E-19 Effect of emergency department crowding on outcomes of admitted patients
- **Authors, year:** Sun BC, Hsia RY, Weiss RE, et al. Ann Emerg Med 61(6):605-611, 2013. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2012.10.026
- **Sample:** 995,379 admissions, 187 California hospitals, 2007; crowding proxy = top quartile of ambulance diversion hours for that hospital.
- **Outcomes:** High-crowding days: 5% greater odds of inpatient death (2-8%), 0.8% longer stay, 1% higher cost; 300 excess deaths, 6,200 hospital days, $17 million.
- **Implication:** The adjusted, multi-hospital effect is small per patient: use it as the low end of the boarding penalty range.

### E-20 The access-block effect: relationship between delay to reaching an inpatient bed and inpatient length of stay
- **Authors, year:** Richardson DB. Med J Aust 177(9):492-495, 2002. Read: abstract.
- **Link:** https://doi.org/10.5694/j.1326-5377.2002.tb04917.x
- **Sample:** 11,906 admissions, one Canberra tertiary hospital, 1999; 7.7% had access block (over 8 hours in the ED).
- **Outcomes:** Mean inpatient stay 4.9 days with access block versus 4.1 without (stays truncated at 10 days); effect across severities and diagnoses.
- **Implication:** +20% inpatient stay for an 8-hour-plus ED stay; consistent with about 1 to 2% per boarding hour.

### E-21 Crowding delays treatment and lengthens emergency department length of stay, even among high-acuity patients
- **Authors, year:** McCarthy ML, Zeger SL, Ding R, Levin SR, Desmond JS, Lee J, Aronsky D. Ann Emerg Med 54(4):492-503, 2009. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2009.03.006
- **Design:** Discrete-time survival analysis with crowding measured every 30 minutes, four EDs, one year.
- **Outcomes:** Crowding "substantially delayed patients' waiting room and boarding times but not treatment time". Boarders rising from the 50th to 90th percentile raised median waiting-room time (26 to 70 min across sites) by 6% to 78% and median boarding time (250 to 626 min) by 15% to 47%. Level 2 patients waited 3% to 35% longer when crowded.
- **Implication:** Congestion should act through queues and bed blocking, not by stretching in-bay service times. Baseline boarding medians of 4 to 10 hours are the validation range.

### E-22 Emergency department crowding and risk of preventable medical errors
- **Authors, year:** Epstein SK, Huckins DS, Liu SW, et al. Intern Emerg Med 7(2):173-180, 2012. Read: abstract.
- **Sample:** 533 patients (myocardial infarction, asthma, dislocation), four Massachusetts EDs. **Link:** https://doi.org/10.1007/s11739-011-0702-8
- **Outcomes:** 8.6% had a preventable medical error; more than twofold higher in the top crowding quartile than the bottom; non-linear, concentrated at the highest crowding.
- **Implication:** A quality-of-outcome multiplier of about 2 at the top occupancy quartile, flat below it, is the supported shape for the interaction "quality" field.

### E-23 The relationship between inpatient discharge timing and emergency department boarding
- **Authors, year:** Powell ES, Khare RK, Venkatesh AK, Van Roo BD, Adams JG, Reinhardt G. J Emerg Med 42(2):186-196, 2012. Read: abstract.
- **Link:** https://doi.org/10.1016/j.jemermed.2010.06.028
- **Design:** Computer model of inflow and outflow of inpatient beds, weekdays in September 2007, one US academic hospital.
- **Outcomes:** Daily means: 38.8 ED admissions, 22.7 surgical, 19.5 ICU transfers, 81.1 discharges; 70.5% to 88.0% of these happened between noon and midnight. Base case 77.0 boarding hours a day; shifting the discharge peak 4 hours earlier eliminated boarding; 75% of discharges by noon, or all between 08:00 and 16:00, cut it to 3.0.
- **Limitations:** Deterministic flow model, one month, one hospital.
- **Implication:** Ward discharge timing is the strongest boarding lever and needs a time-of-day discharge profile in the ward model (most discharges after noon by default).

### E-24 Effects of a fast-track area on emergency department performance
- **Authors, year:** Sanchez M, Smally AJ, Grant RJ, Jacobs LM. J Emerg Med 31(1):117-120, 2006. Read: abstract.
- **Link:** https://doi.org/10.1016/j.jemermed.2005.08.019
- **Design:** Historical cohort, one year before and after opening a fast track, US tertiary adult ED.
- **Outcomes:** Despite daily census rising by 8.71, waiting time fell 51 minutes (95% CI -56 to -46), length of stay 28 minutes (-31 to -23), LWBS 4.06 points (-4.48 to -3.46); no change in mortality or revisits.
- **Limitations:** Before-after, single site; sample size not in the abstract.
- **Implication:** Target effect size for the fast-track lever.

### E-25 A systematic review of triage-related interventions to improve patient flow in emergency departments
- **Authors, year:** Oredsson S, Jonsson H, Rognes J, et al. Scand J Trauma Resusc Emerg Med 19:43, 2011. Read: abstract.
- **Link:** https://doi.org/10.1186/1757-7241-19-43
- **Sample:** 33 controlled studies, over 800,000 patients.
- **Outcomes (GRADE):** Fast track: moderately strong evidence for shorter wait, shorter stay, fewer LWBS. Team triage with a physician: relatively strong for LWBS. Streaming, point-of-care testing, nurse-requested X-ray: limited or insufficient.
- **Implication:** Fast track and physician-in-triage are the two front-end levers worth modelling with confidence.

### E-26 The role of triage liaison physicians on mitigating overcrowding in emergency departments: a systematic review
- **Authors, year:** Rowe BH, Guo X, Villa-Roel C, et al. Acad Emerg Med 18(2):111-120, 2011. Read: abstract.
- **Link:** https://doi.org/10.1111/j.1553-2712.2010.00984.x
- **Sample:** 28 studies; 23 rated weak.
- **Outcomes:** Two RCTs pooled: ED stay -36.85 minutes (-51.11 to -22.58) versus nurse triage; one RCT: time to physician -30.00 minutes; LWBS RR 0.82 (0.67-1.00).

### E-27 Impact of triage liaison provider on emergency department throughput: A systematic review and meta-analysis
- **Authors, year:** Benabbas R, Shah R, Zonnoor B, Mehta N, Sinert R. Am J Emerg Med 38(8):1662-1670, 2020. Read: abstract.
- **Link:** https://doi.org/10.1016/j.ajem.2020.04.068
- **Sample:** 12 US studies, 329,340 patients.
- **Outcomes:** Attending physician at triage: LWBS risk ratio 0.62 (0.54-0.71). Change in ED stay ranged from -82 to +20 minutes, too heterogeneous to pool.
- **Implication (E-26, E-27):** Provider-in-triage reduces LWBS by about 20 to 40% and may or may not shorten stay; it costs a provider who is no longer in the main department. See also E-28.

### E-28 Impact of employing primary healthcare professionals in emergency department triage on patient flow outcomes
- **Authors, year:** Jeyaraman MM, Alder RN, Copstein L, et al. BMJ Open 12(4):e052850, 2022. Read: abstract.
- **Link:** https://doi.org/10.1136/bmjopen-2021-052850
- **Sample:** 40 comparative studies (10 RCTs).
- **Outcomes:** Nurse-practitioner, GP or extended-authority nurse triage reduced time to initial assessment in 13 of 14 studies, ED stay in 29 of 30, LWBS in 8 of 10; quality generally low.

### E-29 Implementation of Vertical Split Flow Model for Patient Throughput at a Community Hospital Emergency Department
- **Authors, year:** Hsieh A, Arena A, Oraha A, et al. J Emerg Med 64(1):77-82, 2023. Read: abstract.
- **Link:** https://doi.org/10.1016/j.jemermed.2022.10.007
- **Sample:** 10,638 ESI 3 visits (5,262 before, 5,376 after), three months each, 2018-2019.
- **Outcomes:** Mean length of stay 283 to 251 minutes with ESI 3 patients kept in chairs instead of beds.
- **Implication:** A results-waiting area (which RWJUH's expansion has) frees bays: about 11% shorter stay for ESI 3 with no added staff.

### E-30 The effect of low-complexity patients on emergency department waiting times
- **Authors, year:** Schull MJ, Kiss A, Szalai JP. Ann Emerg Med 49(3):257-264, 2007. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2006.06.027
- **Sample:** 4.1 million visits, 110 Ontario EDs, 1,095 eight-hour intervals.
- **Outcomes:** Mean (median) stay 6.3 (4.7), 3.9 (2.8) and 2.2 (1.6) hours for high-, medium- and low-complexity patients; time to physician 1.1, 1.3, 1.1 hours. Every 10 extra low-complexity arrivals per 8 hours add 5.4 minutes to others' stay and 2.1 minutes to time to physician.
- **Implication:** Low-acuity volume is not what crowds the department; a policy that only turns away ESI 5 should gain almost nothing. *Derived*: mean-to-median ratios of 1.34 to 1.39 imply a lognormal CV of about 0.9 to 1.0 for total stay.

### E-31 Reducing ambulance diversion at hospital and regional levels: systemic review of insights from simulation models
- **Authors, year:** Delgado MK, Meng LJ, Mercer MP, Pines JM, Owens DK, Zaric GS. West J Emerg Med 14(5):489-498, 2013. Read: abstract.
- **Link:** https://doi.org/10.5811/westjem.2013.3.12788
- **Sample:** 10 simulation studies from 5,116 records.
- **Outcomes:** "diversion was found to only minimally improve ED waiting room times"; holding units for boarders, fast tracks, faster lab turnaround and smoothing elective surgery reduced diversion considerably; hospitals divert defensively when a neighbour diverts.
- **Implication:** Diversion is a weak lever for waits and should carry a cost; smoothing the elective schedule is a real lever and is already in the daily action set.

### E-32 Association between ambulance diversion and survival among patients with acute myocardial infarction
- **Authors, year:** Shen YC, Hsia RY. JAMA 305(23):2440-2447, 2011. Read: abstract.
- **Link:** https://doi.org/10.1001/jama.2011.811
- **Sample:** 13,860 Medicare patients (11,625 analysed), four California counties, 149 EDs, 2000-2005; mean daily diversion 7.9 hours (SD 6.1).
- **Outcomes:** Nearest ED on diversion 12 or more hours that day: 30-day mortality 19% vs 15% (adjusted difference 3.24 points, 0.60-5.88); no difference below 12 hours.
- **Implication:** Diversion harm is a threshold effect: penalise hours on diversion beyond about 12 a day heavily, short diversions lightly. *Derived* default: +3 percentage points 30-day mortality for diverted ESI 1-2 cardiac patients on such days.

### E-33 Using queueing theory to increase the effectiveness of emergency department provider staffing
- **Authors, year:** Green LV, Soares J, Giglio JF, Green RA. Acad Emerg Med 13(1):61-68, 2006. Read: abstract.
- **Link:** https://doi.org/10.1197/j.aem.2005.07.034
- **Design:** Before-after field implementation of a time-varying queueing (lag stationary independent period-by-period) staffing model, one urban US ED.
- **Outcomes:** With arrivals up 6.3% and provider hours up 3.1%, LWBS fell 22.9% (258 fewer patients). On four weekdays with no extra provider hours, reallocating the same hours by the queueing model cut LWBS 21.7% while arrivals rose 5.5%.
- **Implication:** The benchmark any learned staffing policy has to beat: matching staff to the lagged arrival curve at constant hours is worth about a fifth of LWBS. A queueing-formula staffing rule belongs among the baselines.

### E-34 Systematic reviews of ED crowding (three records, used for scope only)
- Hoot NR, Aronsky D. Systematic review of emergency department crowding: causes, effects, and solutions. Ann Emerg Med 52(2):126-136, 2008. https://doi.org/10.1016/j.annemergmed.2008.03.014 . Abstract: 93 articles; causes include boarding, bed shortage, staffing, influenza season; solutions studied include extra personnel, observation units, bed access, diversion, queueing theory.
- Morley C, Unwin M, Peterson GM, Stankovich J, Kinsman L. Emergency department crowding: A systematic review of causes, consequences and solutions. PLoS One 13(8):e0203316, 2018. https://doi.org/10.1371/journal.pone.0203316 . Abstract: 102 studies; mismatch between causes (who attends, timely discharge from the ED) and tested solutions (flow inside the ED); whole-system disposition targets were promising.
- Bernstein SL, Aronsky D, Duseja R, et al. The effect of emergency department crowding on clinically oriented outcomes. Acad Emerg Med 16(1):1-10, 2009. https://doi.org/10.1111/j.1553-2712.2008.00295.x . Abstract: 41 studies; crowding associated with in-hospital mortality, delayed treatment for pneumonia and pain, more leaving; not with delayed reperfusion for STEMI.
- **Implication:** Output blocking (boarding) is the root cause across reviews; a simulator without inpatient beds cannot reproduce crowding.

---

## C. Simulation and reinforcement learning for hospital and queueing operations

The teammate's file cites Agent Hospital (arXiv 2405.02957) and AgentClinic (arXiv 2405.07960) as LLM-agent
precedents; they are language-agent simulations, not queueing or RL-for-operations work, and are not re-reviewed.

### E-35 QGym: Scalable Simulation and Benchmarking of Queuing Network Controllers
- **Authors, year:** Chen H, Li A, Che E, Peng T, Dong J, Namkoong H. arXiv 2410.06170, 2024. Read: full text.
- **Link:** https://arxiv.org/abs/2410.06170 ; code https://github.com/namkoong-lab/QGym
- **Design:** Open-source benchmark: event-driven queueing simulator with a Gym step interface and batched GPU execution; classical policies against PPO variants.
- **Setting:** Parallel-server, criss-cross, tandem, re-entrant networks, an input switch, and a "hospital" instance: 8 specialties routed to 497 servers in 11 wards, calibrated to a real hospital's inpatient network.
- **Comparator:** c-mu rule, MaxWeight, MaxPressure, fluid policy versus PPO, PPO with behaviour cloning (PPO-BC), work-conserving PPO (PPO-WC), A2C-WC.
- **Outcomes:** Reward: negative holding cost (queue lengths). Vanilla PPO "fail[s] to achieve stability" in every setting. PPO-WC beats the classical baselines in 77% of pairwise comparisons, by about 10% with exponential service times and about 21% with hyper-exponential. On the hospital instance average total queue length was 4.4e2 for c-mu, MaxWeight and MaxPressure, 1.5e3 for the fluid policy, and 2.3e4 to 2.5e4 for all PPO variants after 5 million steps. Training recipe: 100 iterations x 50,000 steps over 50 actors, discount 0.998, GAE lambda 0.99, KL penalty 0.03, value batch 2,500, policy batch = whole rollout, 3 epochs, Adam with warm-up and cosine decay, learning rate 3e-4 (value) and 9e-4 (policy), 100 evaluation trajectories.
- **Limitations:** Scheduling only (which queue a server takes); no staffing, abandonment-by-acuity or money; arXiv preprint.
- **Implication:** The closest published precedent for HospitalGym's simulator design, and a warning: on the one realistic hospital network RL lost to simple index rules by about 50x. Mask non-work-conserving actions, warm-start from a heuristic, and expect the tuned rule-based manager to be a strong baseline.

### E-36 Differentiable Discrete Event Simulation for Queuing Network Control
- **Authors, year:** Che E, Dong J, Namkoong H. arXiv 2409.03740, 2024. Read: full text (introduction and results summary).
- **Link:** https://arxiv.org/abs/2409.03740
- **Design:** Smoothed discrete-event dynamics so that policy gradients can be computed pathwise with auto-differentiation on GPU.
- **Comparator:** REINFORCE-style estimators and the PPO of E-37.
- **Outcomes:** Pathwise gradients "50-1000x" more sample-efficient; in 94.5% of 10,800 parameter settings a single-trajectory pathwise estimate was closer to the true gradient (cosine similarity) than REINFORCE with 1,000 trajectories; a "work-conserving softmax" policy head keeps even randomly initialised networks stable where plain PPO "fails to stabilize large queuing networks and leads to runaway queue lengths"; handles non-stationary arrivals and non-exponential service.
- **Limitations:** Requires a differentiable simulator; preprint.
- **Implication:** Second independent source for the work-conserving action head. If the simulator is ever ported to PyTorch tensors end to end, pathwise gradients are the upgrade path; not needed tonight.

### E-37 Queueing Network Controls via Deep Reinforcement Learning
- **Authors, year:** Dai JG, Gluzman M. arXiv 2008.01644, 2020 (v7). Read: abstract and parts of full text.
- **Link:** https://arxiv.org/abs/2008.01644
- **Design:** PPO extended to long-run average cost with unbounded costs and countable state.
- **Setting:** Criss-cross network, N-model parallel-server system, multiclass re-entrant networks of 6 to 21 classes, light to heavy traffic.
- **Comparator:** State-of-the-art heuristics from the queueing literature; optimal policy where computable.
- **Outcomes:** PPO policies "consistently ... outperform state-of-art heuristics" and are near-optimal where the optimum is known. Three variance-reduction devices were necessary: a discounted relative value function, regenerative simulation, and an approximating-martingale control variate. Servers are forbidden to idle while their buffers are non-empty so that the initial policy is stable.
- **Limitations:** Stationary arrivals; scheduling only.
- **Implication:** Use an average-cost or high-discount formulation with strong variance reduction (large batches, GAE near 1, normalised advantages); start from a stable policy.

### E-38 Inpatient Overflow Management with Proximal Policy Optimization
- **Authors, year:** Sun J, Dai JG, Shi P. arXiv 2410.13767, 2024 (v6). Read: full text (model and method sections).
- **Link:** https://arxiv.org/abs/2410.13767
- **Design:** Periodic long-run-average-cost MDP for assigning waiting ED admissions to their primary ward or overflowing them to another, solved with PPO.
- **Setting:** Simulated hospitals with up to 20 patient classes and 20 wards, hourly decision epochs, time-varying arrivals and discharges.
- **State / action / reward:** State = patients per class, planned discharges per class, time-of-day index (2J+1 numbers). Action = overflow assignments, decomposed into sequential per-patient "atomic" actions. Cost per epoch = holding cost per waiting patient plus a one-time cost per overflow assignment.
- **Comparator:** Approximate dynamic programming (Dai and Shi 2019, infeasible beyond five wards) and simpler overflow rules.
- **Outcomes:** Matches approximate DP on the five-ward system and "matches or outperforms existing benchmarks" at 20 wards. A policy network sharing layers across hours with a separate last layer per epoch needed "only a few thousand simulation data samples" in a ten-ward system and beat designs needing 100 times more. Critic: linear in queueing-informed basis functions (LSTD). Authors' conclusion: "domain-aware adaptation is more critical ... than fine-tuning neural network parameters".
- **Limitations:** Simulation only; overflow decision only; numeric cost tables not extracted here.
- **Implication:** The best-matched precedent for HospitalGym's hourly bed-assignment head: include planned discharges and hour of day in the observation, split multi-patient decisions into sequential single assignments, share the trunk across times of day, and charge an explicit cost for off-service placement.

### E-39 Improving Emergency Department Efficiency by Patient Scheduling Using Deep Reinforcement Learning
- **Authors, year:** Lee S, Lee YH. Healthcare 8(2):77, 2020. Read: full text.
- **Link:** https://doi.org/10.3390/healthcare8020077 (PMC7349722)
- **Design:** Deep Q-network choosing which waiting patient a freed resource serves next, inside a discrete-event simulation.
- **Setting:** Simulated ED with arrival rate from 11,357 historical records over two months (Korea), five acuity levels, several treatment stages per patient.
- **State / action / reward:** State = resource information plus per-patient features of those waiting; action = pick a patient; reward = negative acuity-weighted waiting time (one minute of an acuity-1 patient's wait counts as 30) with penalties when acuity 1-2 patients exceed a waiting threshold. Network 64-32-2, epsilon-greedy, replay memory.
- **Comparator:** FCFS, shortest remaining processing time, critical ratio, and three acuity-weighted index rules.
- **Outcomes:** In the normal-load scenario "the performance of the RL and dispatching rule are not largely different"; the acuity-weighted-wait rule was "almost the same" as RL. As arrival rate rose, RL kept under 2% of acuity 1-2 patients over threshold while the rules did not; FCFS and critical ratio failed to protect them. Averages over 50 instances per scenario.
- **Limitations:** Small simulated ED, no boarding, staffing or abandonment; single hospital's data.
- **Implication:** Acuity-weighted waiting time is a workable dense reward; an acuity-weighted index rule is a baseline that RL only beats under overload.

### E-40 Integrating Deep Reinforcement Learning Networks with Health System Simulations
- **Authors, year:** Allen M, Monks T. arXiv 2008.07434, 2020. Read: full text.
- **Link:** https://arxiv.org/abs/2008.07434 ; code https://github.com/MichaelAllen1966/learninghospital
- **Design:** A pattern for wrapping SimPy discrete-event models in the Gym interface, with a hospital bed-capacity example.
- **State / action / reward:** Observations include weekday, beds, patients, spare beds, pending bed changes; actions request a change in staffed beds, which arrives after a delay; reward is zero or negative, the shortfall or excess against a target reserve of free staffed beds (default 5% of patients present); length of stay exponential.
- **Comparator / outcomes:** Demonstrates Double DQN, Duelling DDQN and noisy/bagging variants; no claim of beating an operational baseline.
- **Limitations:** Toy model; one environment per process.
- **Implication:** Precedent for delayed-effect capacity actions and a target-band reward; shows why a vectorised simulator is needed (SimPy runs one hospital at a time).

### E-41 Cyber-Physical Orchestration of Emergency Department Services Through a Bidirectional Digital Twin and a Deep Reinforcement Learning Agent
- **Authors, year:** Acuña JJS, García MA. Research Square preprint, 2026. Read: abstract. Not peer reviewed.
- **Link:** https://doi.org/10.21203/rs.3.rs-10475510/v1
- **Design:** SimPy discrete-event "digital twin" calibrated from literature distributions; DQN with a 17-dimensional state and six dispatch actions; reward weighs critical-patient wait, length of stay, peak occupancy, throughput and equity; ten seeds per configuration.
- **Comparator:** ESI-FIFO, shortest remaining processing time, a composite heuristic.
- **Outcomes:** At +40% demand, peak occupancy 76.2 to 67.4 patients (-11.5%) with no difference in mean stay (98.31 vs 98.48 min, p = 0.878). At baseline load all four policies were statistically indistinguishable. The authors show by Little's law that implied census exceeded the 25 installed beds (rho about 1.23), meaning the twin had no hard capacity blocking, and that their reported equity index of 0.000 was mathematically unattainable, an instrumentation artefact.
- **Implication:** Two lessons: learned dispatch only separates from heuristics in heavy traffic, and simulators must be checked against queueing identities (Little's law, utilisation under 1 with finite beds) before any RL result is believed.

### E-42 Forecasting emergency department crowding: a discrete event simulation
- **Authors, year:** Hoot NR, LeBlanc LJ, Jones I, Levin SR, Zhou C, Gadd CS, Aronsky D. Ann Emerg Med 52(2):116-125, 2008. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2007.12.011
- **Design:** Discrete-event simulation built "purely" from the literature, validated on one academic ED with a sliding window that keeps fitting and validation data separate in time.
- **Sample:** 52,560 consecutive 10-minute observations during 2006.
- **Outcomes:** Forecasts 2 to 8 hours ahead; lowest Pearson r at 8 hours: waiting count 0.56, waiting time 0.49, occupancy 0.78, length of stay 0.86, boarding count 0.79, boarding time 0.80; AUC for ambulance diversion at least 0.86; residual means unbiased except boarding time.
- **Implication:** A validation template: compare simulated and reference series for waiting count, occupancy, stay and boarding, and report correlations and bias, with calibration and validation periods separated.

### E-43 Discrete event simulation of emergency department activity: a platform for system-level operations research
- **Authors, year:** Connelly LG, Bair AE. Acad Emerg Med 11(11):1177-1185, 2004. Read: abstract.
- **Link:** https://doi.org/10.1197/j.aem.2004.08.021
- **Design:** EDSIM model of a Level I trauma centre ED, five days in July 2003, inputs from tracking data, billing records and review of 674 charts.
- **Outcomes:** Average service times within 10% of actual; individual paths poor (28% of treatment times within one hour, 59% within three). An acuity-ratio staffing scheme cut imaging bottlenecks and high-acuity treatment time but lengthened low-acuity service compared with fast track.
- **Implication:** Calibrate and claim accuracy at the level of means and distributions, never individual patients. Imaging is a real bottleneck worth modelling.

### E-44 A Simulation-Based Optimization approach for analyzing the ambulance diversion phenomenon in an Emergency-Department network
- **Authors, year:** Piermarini C, Roma M. arXiv 2309.00643, 2023 (earlier version 2108.04162). Read: abstract.
- **Link:** https://arxiv.org/abs/2309.00643
- **Design:** Discrete-event model of six large EDs in Lazio, Italy; bi-objective simulation-based optimisation (non-value-added patient time against network cost) under different diversion policies, giving a Pareto frontier per policy.
- **Implication:** Precedent for presenting results as a cost-versus-wait Pareto frontier, as HospitalGym's trade-off chart does; diversion only makes sense with a model of where diverted patients go.

---

## D. AI-simulated patients and automated scoring (short; adds to the teammate's clinical research)

Holderried et al. 2024 (GPT-4 history-taking feedback) and Cross et al. 2025 are already in
[clinical-research.md](clinical-research.md) and are not repeated.

### E-45 Large Language Models for Medical OSCE Assessment: A Novel Approach to Transcript Analysis
- **Authors, year:** Shakur AH, Holcomb MJ, Hein D, Kang S, Dalton TO, Campbell KK, Scott DJ, Jamieson AR. arXiv 2410.12858, 2024. Read: abstract.
- **Link:** https://arxiv.org/abs/2410.12858
- **Design:** Automated grading of one communication rubric item ("did the student summarize the patient's medical history?") from Whisper-v3 transcripts; zero-shot chain-of-thought, retrieval augmentation and ensembles.
- **Sample:** 2,027 video-recorded OSCE encounters, UT Southwestern, 2019-2022.
- **Comparator:** Human graders.
- **Outcomes:** GPT-4 Cohen's kappa 0.88 against human graders; open-source models "promising"; failure analysis provided.
- **Limitations:** One rubric item, one school; preprint.
- **Implication:** Item-level rubric scoring from transcripts can reach human-level agreement on a narrow, observable item; report agreement per rubric item, not one overall score.

### E-46 Application of Large Language Models in Medical Training Evaluation-Using ChatGPT as a Standardized Patient: Multimetric Assessment
- **Authors, year:** Wang C, Li S, Lin N, et al. J Med Internet Res 27:e59435, 2025. Read: abstract.
- **Link:** https://doi.org/10.2196/59435
- **Design:** ChatGPT as standardised patient and scorer; scripted poor, medium and good inquiries; prompt revision.
- **Outcomes:** Scores 74.7 (SD 5.44), 82.67 (5.30), 85 (3.27) for poor, medium, good; poor vs others significant, medium vs good not (P = .16). Revised prompt cut the score difference from the reference from 29.83% to 6.06% (SD 0.55 to 0.068); 3.21% on a separate script; language had no significant effect.
- **Limitations:** Scripted inquiries; sample size not in the abstract.
- **Implication:** An LLM scorer separates weak from adequate performance but not adequate from good, and its accuracy depends heavily on the prompt: keep deterministic, evidence-linked rubric checks as the primary grader.

### E-47 Simulated patient systems powered by large language model-based AI agents offer potential for transforming medical education (AIPatient)
- **Authors, year:** Yu H, Zhou J, Li L, et al. arXiv 2409.18924, 2024 (v4). Read: abstract.
- **Link:** https://arxiv.org/abs/2409.18924
- **Design:** Simulated patient built on a knowledge graph from MIMIC-III records with retrieval-augmented generation and six task-specific agents.
- **Outcomes:** 94.15% accuracy on record-based question answering with all six agents (lower with fewer); knowledge-base F1 0.89; stable across repeated runs (ANOVA F 0.61 and 0.78, p > 0.1); median Flesch Reading Ease 68.77.
- **Limitations:** Accuracy is against the record, so about 6% of answers were wrong; MIMIC-III is credentialed data.
- **Implication:** Grounding answers in a structured fact store (the project's fact-ID contract) is the disclosure-control technique with measured fidelity; expect a residual error of several percent and log every answer's fact IDs.

---

## E. Staffing: ratios, fatigue, turnover, absence

### E-48 California Code of Regulations, Title 22, section 70217, Nursing Service Staff
- **Source:** Regulation text via Cornell Legal Information Institute. Read: page.
- **Link:** https://www.law.cornell.edu/regulations/california/Cal-Code-Regs-Tit-22-SS-70217
- **Content:** (a)(8) "The licensed nurse-to-patient ratio in an emergency department shall be 1:4 or fewer at all times"; at least two licensed nurses present when a patient is present; one RN assigned to triage; 1:2 or fewer for critical care patients in the ED; registered nurse 1:1 for critical trauma patients. (a)(1) critical care 1:2. (a)(9) step-down 1:3 from 2008. (a)(10) telemetry 1:4 from 2008. (a)(11) medical/surgical 1:5 from 2005. (a)(7) post-anaesthesia recovery 1:2. (a)(2) one circulating RN per occupied operating room plus a scrub assistant. No averaging over a shift.
- **Implication:** The enforced ratios to use as the default constraint set for every unit type in the model.

### E-49 New Jersey Assembly Bill A1974 (2026-2027 session), "Patient Protection and Safe Staffing Act"
- **Source:** Bill text as introduced 13 January 2026, New Jersey Legislature. Read: full text PDF.
- **Link:** https://pub.njleg.state.nj.us/Bills/2026/A2000/1974_I1.PDF
- **Content:** Would require regulations providing at minimum one RN per four patients on a medical/surgical unit, one per three in step-down, telemetry or intermediate care, one per four in an emergency department, one per two in ED critical care, one per patient in ED trauma, one per five in behavioural health.
- **Limitations:** A bill, not law; committee and floor status were not verified. Existing New Jersey licensing staffing rules (N.J.A.C. 8:43G) were not fetched.
- **Implication:** New Jersey has no enacted California-style ED ratio as of this bill's introduction; show 1:4 as "California law / proposed in New Jersey".

### E-50 Hospital nurse staffing and patient mortality, nurse burnout, and job dissatisfaction
- **Authors, year:** Aiken LH, Clarke SP, Sloane DM, Sochalski J, Silber JH. JAMA 288(16):1987-1993, 2002. Read: abstract.
- **Link:** https://doi.org/10.1001/jama.288.16.1987
- **Sample:** 10,184 nurses, 232,342 surgical patients, 168 Pennsylvania hospitals.
- **Outcomes:** Each additional patient per nurse: 30-day mortality OR 1.07 (1.03-1.12), failure to rescue 1.07, burnout 1.23 (1.13-1.34), job dissatisfaction 1.15.
- **Limitations:** Cross-sectional; surgical ward patients, not ED.
- **Implication:** Ward mortality and nurse burnout terms: +7% and +23% odds per extra patient per nurse beyond the ratio.

### E-51 Decreased Nursing Staffing Adversely Affects Emergency Department Throughput Metrics
- **Authors, year:** Ramsey Z, Palter JS, Hardwick J, Moskoff J, Christian EL, Bailitz J. West J Emerg Med 19(3):496-500, 2018. Read: abstract.
- **Link:** https://doi.org/10.5811/westjem.2018.1.36327
- **Sample:** 105,887 patients in 2015, one urban safety-net ED (Chicago); 336 to 580 nursing hours a day, median 464.7.
- **Outcomes:** Lowest versus highest quartile of nursing hours: door-to-discharge stay +28.2 minutes per patient and nine more LWBS patients a day, independent of volume, occupancy and admission rate; door-to-admit unchanged.
- **Implication:** The ED-specific nurse-staffing effect size. *Derived*: 464.7 nurse-hours over about 290 patients a day is about 1.6 nurse-hours per visit; the bottom quartile should cost about half an hour of stay for discharged patients.

### E-52 Effect of reducing interns' work hours on serious medical errors in intensive care units
- **Authors, year:** Landrigan CP, Rothschild JM, Cronin JW, et al. N Engl J Med 351(18):1838-1848, 2004. Read: abstract.
- **Link:** https://doi.org/10.1056/nejmoa041406
- **Design:** Prospective randomised comparison of schedules with and without 24-hour-plus shifts; direct observation; 2,203 patient-days, 634 admissions.
- **Outcomes:** 35.9% more serious medical errors on the traditional schedule (136.0 vs 100.1 per 1,000 patient-days), 56.6% more non-intercepted, 20.8% more serious medication errors, 5.6 times as many serious diagnostic errors.

### E-53 Impact of extended-duration shifts on medical errors, adverse events, and attentional failures
- **Authors, year:** Barger LK, Ayas NT, Cade BE, et al. PLoS Med 3(12):e487, 2006. Read: abstract.
- **Link:** https://doi.org/10.1371/journal.pmed.0030487
- **Sample:** 2,737 interns, 17,003 monthly reports, US, case-crossover.
- **Outcomes:** Odds ratio of at least one fatigue-related significant medical error 3.5 (3.3-3.7) in months with one to four extended shifts and 7.5 (7.2-7.8) with five or more, versus none.
- **Limitations:** Self-report.

### E-54 The working hours of hospital staff nurses and patient safety
- **Authors, year:** Rogers AE, Hwang WT, Scott LD, Aiken LH, Dinges DF. Health Aff 23(4):202-212, 2004. Read: abstract (and AHRQ PSNet summary page).
- **Link:** https://doi.org/10.1377/hlthaff.23.4.202
- **Sample:** 393 nurses, 5,317 shifts (logbooks).
- **Outcomes:** About 40% of shifts exceeded twelve hours; error risk "significantly increased when work shifts were longer than twelve hours, when nurses worked overtime, or when they worked more than forty hours per week". The often-quoted odds ratio for shifts of 12.5 hours or more is not in the abstract and was not verified here.
- **Related (abstracts):** Scott LD et al., Am J Crit Care 2006 (502 critical-care nurses): longer work duration increased errors and near errors and decreased vigilance. Olds DM, Clarke SP, J Safety Res 2010: all adverse-event and error variables related to working over 40 hours a week; voluntary overtime also harmful.
- **Implication (E-52 to E-54):** Fatigue error multiplier 1.4 (observed) to 3.5 (self-reported); the trigger is hours past 12 in a shift, overtime, and weekly hours over 40, so the simulator's fatigue index should accumulate on overtime, not on ordinary busy hours.

### E-55 2026 NSI National Health Care Retention & RN Staffing Report
- **Source:** NSI Nursing Solutions, Inc., 2026 (survey January 2026 covering calendar 2025). Read: full text PDF.
- **Link:** https://www.nsinursingsolutions.com/Documents/Library/NSI_National_Health_Care_Retention_Report.pdf
- **Sample:** 527 hospitals in 40 states.
- **Outcomes:** Hospital turnover 18.5% (range 7.6% to 33.1%; 15.8% counting full- and part-time only); RN turnover 17.6% (range by bed size 5.6% to 40.0%); RN vacancy 8.6%; average cost of turnover for a bedside RN $60,090; average hospital loses $4.2 to $6.2 million a year; each 1% of RN turnover about $295,000. By specialty (chart): emergency about 20.7% in 2025 and 19.1% in 2024; behavioural health highest; five-year cumulative ED RN turnover 113.6%. First-year staff account for a large share of exits. Average time to recruit an experienced RN 78 days (56 to 102 by specialty; ER nurses 70 days). Travel nurses: hospital average fee $91.23 an hour ("range to $160/hour") against average staff RN pay of $59.46 an hour including 25.8% for benefits.
- **Limitations:** Industry survey, self-selected; the chart's year legend was inferred from the report text.
- **Implication:** Turnover 0.185 a year all staff, 0.21 ED nurses; replacement cost about $60,000 per nurse; a hire takes about 70 days to arrive; agency nurses cost about 1.9 times the base wage (1.5 times the loaded cost), *derived*.

### E-56 Absences from work of employed full-time wage and salary workers by occupation and industry (CPS Table 47)
- **Source:** US Bureau of Labor Statistics, Current Population Survey, 2025 annual averages. Read: page.
- **Link:** https://www.bls.gov/cps/cpsaat47.htm
- **Outcomes:** Absence rate / lost worktime rate: all employed 3.2% / 1.7%; healthcare practitioners and technical 3.7% / 2.1%; healthcare support 4.1% / 2.2%; health care and social assistance industry 3.8% / 2.1%. Illness or injury accounts for 1.2 to 1.3 points of lost worktime.
- **Implication:** Unplanned absence about 2.1% of scheduled hours for clinical staff (not the 3.5% placeholder).

---

## F. Equipment, spaces and events

### E-57 The Boston Marathon bombing: after-action review of the Brigham and Women's Hospital emergency radiology response
- **Authors, year:** Brunner J, Rocha TC, Chudgar AA, et al. Radiology 273(1):78-87, 2014. Read: abstract.
- **Link:** https://doi.org/10.1148/radiol.14140253
- **Outcomes:** 40 patients presented (16 admitted, 24 discharged, 10 emergent operations, no deaths); 31 (78%) imaged in the ED: 57 radiographs in 30 patients, 16 CTs in 7. Median blast-to-arrival 97 minutes (IQR 43-139); arrival to order 24 (12-50); order to completion 49 (26-70); completion to dictated report 75 (19-147). Annual medians for comparison: order-to-completion radiography 31 minutes (19-48), CT 72 (40-129); completion-to-report 74 (35-127).
- **Implication:** One hospital's mass-casualty load (40 patients over about three hours) and everyday imaging turnaround at an academic trauma centre.

### E-58 Root Cause Analysis of Delayed Emergency Department Computed Tomography Scans
- **Authors, year:** Dhanik A, Stenson BA, Levenson RB, Antkowiak PS, Sanchez LD, Chiu DT. West J Emerg Med 25(2):226-229, 2024. Read: abstract.
- **Link:** https://doi.org/10.5811/westjem.17831
- **Sample:** 5,685 CTs on 4,344 patients, urban tertiary ED, May-July 2021.
- **Outcomes:** Order-to-completion median 108 minutes (Q1 57, Q3 182); outliers over 369 minutes were 4.2% of patients, caused by unstable or non-compliant patients 22.8%, IV access 18.0%, contrast allergy 14.4%, kidney-function concerns 12.6%, protocol 12.0%, unknown 32.9%.
- **Implication:** CT order-to-completion of 72 to 108 minutes (IQR about 40 to 180) is the validation target for the imaging path; a right-skewed distribution with a 4% very long tail.

### E-59 Impact of 24/7/365 Attending Radiologist Coverage on the Turnaround Time in an Emergency and Trauma Radiology Department
- **Authors, year:** Jalal S, Ouellette H, Ante Z, Munk P, Khosa F, Nicolaou S. Can Assoc Radiol J, 2021. Read: abstract.
- **Link:** https://pubmed.ncbi.nlm.nih.gov/32103671/
- **Outcomes:** Round-the-clock attending coverage cut overall CT report turnaround by 7.83 hours for trauma and 6.07 hours for non-trauma cases (final report), of which 2.7 to 2.9 hours was completion-to-transcription.
- **Limitations:** Final signed reports at one Canadian centre; sample size not in the abstract.
- **Implication:** Report delay depends on radiologist coverage by shift: a staffing lever for nights, if the model gains a radiologist role.

### E-60 How is "downtime" defined for our CT? (service log)
- **Source:** Wiener Gesundheitsverbund medical physics web page for a Toshiba/Canon Aquilion LB CT. Read: page.
- **Link:** https://physik.gesundheitsverbund.at/html/downtime_ct.htm
- **Outcomes:** Downtime hours by year 2011-2022: 22.5, 11.5, 38.5, 0, 14, 0, 0, 0, 4, 3.2, 22.33, 0.33 against 2,500 operating hours a year (0.0% to 1.5%); vendor guarantee: downtime not above 2% a year; preventive-maintenance days count as downtime.
- **Limitations:** One scanner, weekday daytime operation, Austria; not a study.
- **Implication:** CT unavailability of about 0.4% (range 0 to 2%) of operating hours. No multi-site failure-rate study was found for CT, MRI, X-ray, ultrasound, ventilators, monitors or analysers; those stay assumed.

### E-61 Reduced isolation room turnover time using Lean methodology
- **Authors, year:** Ankrum AL, Neogi S, Morckel MA, Wilhite AW, Li Z, Schaffzin JK. Infect Control Hosp Epidemiol 40(10):1151-1156, 2019. Read: abstract.
- **Link:** https://doi.org/10.1017/ice.2019.199
- **Outcomes:** Median room turnover 130 minutes (range 93-294) to 65 (48-95); breakdown-to-cleaning-start 10 to 3 minutes; cleaning-complete to UV start 36 to 8; cleaning and curtain change 57 to 37 minutes.
- **Limitations:** Isolation rooms with UV disinfection at a children's hospital; sample size not in the abstract.

### E-62 Accelerating Care: Spotless Turnover to Smooth Handover
- **Source:** University of Texas MD Anderson Cancer Center, SHM Converge 2026 abstract 692. Read: page.
- **Link:** https://shmabstracts.org/abstract/accelerating-care-spotless-turnover-to-smooth-handover-2/
- **Outcomes:** Mean time from cleaning request to room cleaned, inspected and released to bed control: 115 minutes (Feb 2023-Feb 2024) to 68 minutes (Jan-Jun 2025), a 41% decrease.
- **Limitations:** Conference abstract; sample size not reported; no split of cleaning versus waiting.
- **Implication (E-61, E-62):** Inpatient bed turnaround about 65 to 70 minutes when well run, 115 to 130 when not; half of it is waiting, which makes environmental-services staffing a lever. Nothing was found for ED bay turnaround.

### E-63 Weekly US Influenza Surveillance Report, week 5, 2024-25 season
- **Source:** CDC FluView. Read: page.
- **Link:** https://www.cdc.gov/fluview/surveillance/2025-week-05.html
- **Outcomes:** Week ending 1 February 2025: 8.0% of ED visits had an influenza discharge diagnosis (NSSP); 7.8% of outpatient visits were for influenza-like illness against a 3.0% baseline, above baseline for the tenth consecutive week and still rising.
- **Implication:** Peak flu share of ED visits about 8% in a high-severity season; wave above baseline for at least ten weeks.

### E-64 Impact of seasonal and pandemic influenza on emergency department visits, 2003-2010, Ontario, Canada
- **Authors, year:** Schanzer DL, Schwartz B. Acad Emerg Med 20(4):388-397, 2013. Read: abstract.
- **Link:** https://doi.org/10.1111/acem.12111
- **Outcomes:** ED visits attributable to influenza: 500 per 100,000 population a year for seasonal influenza (450-550), 1,000 per 100,000 in the 2009 pandemic; only 7% (seasonal) and 38% (pandemic) were coded as influenza or influenza-like illness; during influenza periods significantly more people with non-respiratory complaints registered and left without being seen.
- **Implication:** Coded influenza understates the surge several-fold in ordinary seasons, and flu waves raise LWBS among everyone else: the wave should stress the queue, not only add respiratory patients.

### E-65 Community influenza outbreaks and emergency department ambulance diversion
- **Authors, year:** Schull MJ, Mamdani MM, Fang J. Ann Emerg Med 44(1):61-67, 2004. Read: abstract.
- **Link:** https://doi.org/10.1016/j.annemergmed.2003.12.008
- **Setting:** Toronto EDs, January 1996 onward, 170 weeks, mean 10,936 ED visits a week.
- **Outcomes:** Four seasons of 18 to 30 weeks; diversion averaged 3.4 hours a week per ED; +2.5 hours a week per 100 community influenza cases (1.2-3.9); 24.3% of diversion in influenza seasons attributable to influenza.
- **Implication:** A flu wave should raise diversion hours by about a quarter under a threshold diversion policy: a check on the event's realism.

### E-66 A day like no other: the Las Vegas mass shooting lessons from America's largest mass casualty event
- **Authors, year:** Lake CK. Trauma Surg Acute Care Open 10(Suppl 1):e001786, 2025. Read: full text.
- **Link:** https://doi.org/10.1136/tsaco-2025-001786
- **Outcomes:** Over 800 injured, 413 with gunshot wounds needing immediate treatment; 31 immediate deaths and 26 more within 24 hours at hospitals; victims largely self-transported to the nearest hospitals with no field triage or advance notice; one hospital had a line of private vehicles over a quarter mile long; registration systems could not keep pace; throughput mattered more than surge capacity.
- **Limitations:** Narrative review; per-hospital counts and arrival curves not given.
- **Implication:** The upper tail of the mass-casualty event: hundreds of unannounced, untriaged walk-in arrivals in the first hour at the nearest hospital. The arrival mode for this event should be mostly walk-in, not ambulance.

### E-67 Comfortable and maximum walking speed of adults aged 20-79 years: reference values and determinants
- **Authors, year:** Bohannon RW. Age Ageing 26(1):15-19, 1997. Read: abstract.
- **Link:** https://doi.org/10.1093/ageing/26.1.15
- **Sample:** 230 healthy volunteers over a 7.62 m walkway.
- **Outcomes:** Mean comfortable speed 127.2 cm/s (women in their seventies) to 146.2 cm/s (men in their forties); maximum 174.9 to 253.3 cm/s.
- **Implication:** Staff walking speed about 80 m/min (76 to 88); hurried up to about 150. No source was found for stretcher or wheelchair transport speed.

---

### E-68 Early Clinical Deterioration Among Emergency Department Boarders: A Retrospective Analysis
- **Authors, year:** Rizer NW, Klein E, Copenhaver MS, Zhao X, Kelen GD, Hinson JS. Ann Emerg Med 87(6):681-693, 2026. Read: abstract. (Section B topic; numbered late because it was found late.)
- **Link:** https://doi.org/10.1016/j.annemergmed.2026.01.023
- **Design:** Retrospective cohort, five-hospital US academic system, January 2018-June 2024; adults admitted to medicine at floor level who boarded 4 to 48 hours.
- **Sample:** 173,168 encounters.
- **Outcomes:** Early deterioration (escalation to intermediate or intensive care within 48 hours of the admission order) in 6,299 (3.6%); 2,823 (45%) of these while still in the ED. Median boarding 12.5 hours (IQR 8.2-20.7) with deterioration, 10.2 (6.9-18.3) without. Boarding duration adjusted OR 1.17 (1.10-1.24) overall and 1.58 (1.46-1.71) for deterioration in the ED: +0.8% and +2.4% relative risk per extra boarding hour. Safety-net hospital aOR 2.41; overnight admission 1.29; elevated lactate 1.93. 28-day mortality 13.0% after deterioration versus 3.9%.
- **Limitations:** One system; excludes patients boarding under 4 hours; treated, admitted patients, not people waiting to be seen.
- **Implication:** The only measured deterioration rate found. *Derived*: about 0.003 per boarding hour for floor-level admitted patients (3.6% over 12.5 hours), 0.0013 counting only events in the ED; mortality multiplies by about 3.3 after a deterioration. Baseline boarding medians of 10 to 12 hours in this system are far above the Wave 0 world.

### E-69 Association of sudden in-hospital cardiac arrest with emergency department crowding
- **Authors, year:** Chang YH, Shih HM, Chen CY, Chen WK, Huang FW, Muo CH. Resuscitation 138:106-109, 2019. Read: abstract.
- **Link:** https://doi.org/10.1016/j.resuscitation.2019.03.001
- **Setting:** One Taiwanese ED; sample size not in the abstract.
- **Outcomes:** Sudden in-hospital cardiac arrest incidence rose when ED bed occupancy exceeded 260% (rate ratio 1.50, 1.03-2.17); boarding over 24 hours (ward) or 48 hours (ICU) also raised it; the number of boarders alone did not.
- **Implication:** Supports a threshold rather than linear occupancy effect on catastrophic events; the threshold itself is setting-specific.

### E-70 A Discrete Event Simulation and Deep Reinforcement Learning Framework for Queue Management and Patient Prioritization in an Emergency Department
- **Authors, year:** Zattoni L. PhD thesis, University of Bologna, 2026 (supervisor E. Malaguti). Read: full text (abstract, MDP formulation, results, limitations). (Section C topic.)
- **Link:** https://amsdottorato.unibo.it/id/eprint/12809/1/zattoni_luca_tesi.pdf
- **Design:** Discrete-event simulation of the general ED of IRCCS Azienda Ospedaliero-Universitaria di Bologna, built from historical data and validated against real flow and length of stay; a deep-learning classifier estimates whether a patient is near the end of the pathway; A2C and PPO agents.
- **State / action / reward:** The action is an index into a fixed table of queue-sorting rules (combinations of severity weight, predicted discharge, waiting time and similar keys) used by physicians and service queues, so the agent chooses which prioritisation rule to apply now, not which patient. State: number of physicians on duty, time of day, and counts of patients grouped by severity, triage history and pathway phase. Reward: R = -sum over patients in the system of clip(penalty, 0, 4w), a piecewise-linear penalty in time in the system that steps up when a patient passes the target time to first assessment (0, 15, 60, 120, 240 minutes for severity 1-5; weights w = 1, 0.8, 0.6, 0.525, 0.5) and again past a maximum length of stay; the per-patient penalty is clipped because unbounded values destabilised training. Several simpler weightings were tried first.
- **Comparator:** The prioritisation policy in use at the hospital.
- **Outcomes:** Mean length of stay 397.8 minutes under the standard policy versus 365.8 (A2C) and 368.1 (PPO); median 379.0 versus 313.2 and 312.3; by severity, level 3 improved most (441.1 to about 376) and level 4 not at all (425.1 versus 418.6 and 428.5). Throughput unchanged. Door-to-doctor results mixed: most patients seen faster, a minority later, because agents "sometimes delay the first assessment when the system is already saturated" to avoid downstream bottlenecks.
- **Limitations (stated):** The simulation models physicians, patients and a few resources, "omits the explicit representation of nurses and treatment spaces", and does not model clinical deterioration from delay. A thesis, not peer-reviewed in this form.
- **Implication:** A meta-action over known dispatch rules is a low-risk action design that cannot do worse than the best rule and trained with standard A2C/PPO; expected gain about 8% in mean and 17% in median stay. Without a harm-from-delay term the agent learns to hold new patients back, which HospitalGym's deterioration and LWBS terms are there to price.

### E-71 Emergency Department Online Patient-Caregiver Scheduling
- **Authors, year:** Rosemarin H, Rosenfeld A, Kraus S. AAAI 2019. Read: full text (author-hosted PDF). (Section C topic.)
- **Link:** https://u.cs.biu.ac.il/~krauss/data/articles/aaai19er.pdf
- **Design:** Learning-based scheduling: offline instances are solved to optimality with a mixed-integer solver against an expert-weighted multi-objective, and a deep network is trained to imitate those solutions online.
- **Setting:** Simulation with real data from Rambam hospital's ED, Israel.
- **Comparator:** First-come-first-served with urgencies, described by the authors' expert panel as the backbone of most ED scheduling.
- **Outcomes:** Risk measure improved 10% (normal flow) and 15% (heavy flow); length of stay 5% and 11%; waits marginal (about 20 seconds); crowdedness unchanged; treatment interruptions about ten times less likely.
- **Implication:** Imitating an optimiser's solutions is an alternative to RL for the hourly dispatch head, and "FCFS with urgency override" is the realistic status-quo baseline. Gains again grow with load.

### E-72 NurseSchedRL: Attention-Guided Reinforcement Learning for Nurse-Patient Assignment
- **Authors, year:** Koduri H. arXiv 2509.18125, 2025. Read: abstract. (Section C topic.)
- **Link:** https://arxiv.org/abs/2509.18125
- **Design:** PPO with feasibility masks and attention over nurse skills, fatigue and location; simulation.
- **Outcomes:** "improved scheduling efficiency, better alignment of skills to patient needs, and reduced fatigue compared to baseline heuristic and unconstrained RL"; no numbers in the abstract.
- **Limitations:** Single-author preprint; results not quantified in the abstract.
- **Implication:** Weak evidence, cited only as a second instance of action masking for feasibility in a staffing problem. No published RL study of ED staffing levels (how many nurses or physicians per shift) was found.

---

### E-73 Resident and advanced-practice provider productivity (three records)
- Joseph JW, Henning DJ, Strouse CS, Chiu DT, Nathanson LA, Sanchez LD. Modeling Hourly Resident Productivity in the Emergency Department. Ann Emerg Med 70(2):185-190, 2017. https://doi.org/10.1016/j.annemergmed.2016.11.020 . Read: abstract. 75 residents, 14,364 shifts of 8-9 hours at one US academic ED, 2010-2015: mean 10.1 patients per shift (SD 3.2), 93.8% at ESI 3 or more acute; 2.14 (SD 1.2) in the first hour, falling every hour after, most in the second, third and final hours.
- Shaw DL, Kravitz MS, Stenson BA, Lewis JJ, Chiu DT. Emergency medicine resident productivity across consecutive shifts. AEM Educ Train 8(1):e10935, 2024. https://doi.org/10.1002/aet2.10935 . Read: abstract. 2,950 shifts, 32,379 encounters: first-year residents 0.88-0.96 patients per hour, second-year 1.61-1.75; no change across seven consecutive shifts, including nights (slope 0.001 to 0.011, not significant).
- Hamden K, Jeanmonod D, Gualtieri D, Jeanmonod R. Comparison of resident and mid-level provider productivity in a high-acuity emergency department setting. Emerg Med J 31(3):216-219, 2014. https://doi.org/10.1136/emermed-2012-201904 . Read: abstract. 55 mid-level and 98 resident shifts: 1.56 versus 1.23 patients per hour; 2.05 versus 2.73 relative value units per patient. Related: McDonnell WM et al., Pediatr Emerg Care 31(2):101-106, 2015 (abstract): attending-plus-nurse-practitioner pods 2.18 patients per hour versus 1.90 for attending-plus-resident pods (difference not significant).
- **Limitations:** Single sites; new-patient counts, not complexity-adjusted; ratios to attendings are across hospitals.
- **Implication:** *Derived* productivity relative to an attending (about 2.0 patients per hour, E-08): residents 0.6 (0.45 first year to 0.85 second year), advanced-practice providers 0.78. Working several days in a row did not slow residents, so day-to-day fatigue carry-over on productivity has no support; the within-shift decline does.

### E-74 Impact of scribes on emergency medicine doctors' productivity and patient throughput: multicentre randomised trial
- **Authors, year:** Walker K, Ben-Meir M, Dunlop W, et al. BMJ 364:l121, 2019. Read: abstract.
- **Link:** https://doi.org/10.1136/bmj.l121
- **Design:** Randomised by shift, five EDs in Victoria, Australia; 589 scribed shifts (5,098 patients), 3,296 non-scribed (23,838 patients).
- **Outcomes:** Patients per hour per doctor 1.13 to 1.31 (+15.9%); primary consultations 0.83 to 1.04 (+25.6%); no change in door-to-doctor time; median stay 192 (IQR 108-311) to 173 (96-208) minutes; largest gains with senior doctors at triage, least in fast track.
- **Implication:** A randomised effect size for a cheap staffing lever (a scribe adds about 16% to a physician's throughput). Also a second-country productivity anchor: 1.1 to 1.3 patients per doctor-hour across all grades in Australia, lower than US attending figures.

### E-75 Laboratory turnaround and point-of-care testing (two records)
- Vrijsen BEL, Haitjema S, Westerink J, et al. Shorter laboratory turnaround time is associated with shorter emergency department length of stay. BMC Emerg Med 22(1):207, 2022. https://doi.org/10.1186/s12873-022-00763-w . Read: abstract. 23,718 ED visits, one Dutch university hospital: median ED stay 199 minutes (IQR 146-268), time to testing 7.0 minutes (2.0-12.0), laboratory turnaround 51.1 minutes (41.1-65.0); the laboratory stage was a median 69% of turnaround; both times independently associated with stay.
- Hausfater P, Hajage D, Bulsei J, et al. Impact of Point-of-care Testing on Length of Stay of Patients in the Emergency Department: A Cluster-randomized Controlled Study. Acad Emerg Med 27(10):974-983, 2020. https://doi.org/10.1111/acem.14072 . Read: abstract. 23,231 patients, one French ED; 36% had blood drawn. Time to results 28 (SD 31) minutes with point-of-care testing versus 79 (SD 34) with the central laboratory (-51 minutes); ED stay 203 (SD 161) versus 210 (SD 168) minutes, difference -9 (95% CI -22 to 5), and -17 (-34.0 to 0.6) among those tested.
- **Implication:** Lab order-to-result about 50 to 80 minutes; *derived* lognormal mean 54, CV 0.35 from the Dutch median and IQR. Cutting lab time by 51 minutes moved ED stay by only 9: results are rarely the binding constraint, so a simulator in which faster labs produce large gains is mis-specified. Total ED stay SD/mean of 0.8 in the trial is another shape check.

### E-76 Fast for Real or Just a Feel? Reassessing Hallway Treatment Spaces and Their Impact on Emergency Department Operations
- **Authors, year:** Dilip M, Su H, Meng L, et al. J Am Coll Emerg Physicians Open 6(6):100257, 2025. Read: abstract.
- **Link:** https://doi.org/10.1016/j.acepjo.2025.100257
- **Sample:** 340,141 ED visits; 93,289 (27.4%) first evaluated and treated in a hallway space.
- **Outcomes:** Discharged hallway patients were placed 17.85 minutes faster (95% CI 14.28-20.71) but had 7.57 minutes longer bed-to-provider time and a 123.05-minute longer ED stay (82.03-166.81). Admitted hallway patients were placed 8.46 minutes faster with no significant difference in later intervals.
- **Limitations:** One system; observational; hallway patients may differ.
- **Implication:** Overflow hallway spaces should start care sooner (about 18 minutes) but lengthen the stay of patients who go home by about two hours. That is a throughput penalty rather than a "quality points" penalty; the catalog's hallway penalty stays assumed.

### E-77 Multicentre cross-sectional study to assess nursing workload in Belgian emergency departments
- **Authors, year:** Ganty T, Szecel J, Diep A, Ghuysen A, Paquay M. Emerg Med J 42(7):421-428, 2025. Read: full text.
- **Link:** https://doi.org/10.1136/emermed-2024-214334
- **Sample:** 161 nurses, 591 patients, several Belgian EDs.
- **Outcomes:** Median direct nursing care time per patient during the observation window 13.6 minutes (IQR 6-34.6); 10.6 (6-23.3) for patients whose whole visit fell inside it. Against triage level 3: level 1 +97.2 minutes (76.3-118.1), level 2 +30.2 (15.9-44.5), level 4 -22.0, level 5 -25.3 (univariate). Triage level plus two dependency items explained 67% of variation; each additional patient present added 45.22 minutes of total nursing care time.
- **Limitations:** Observation windows, not whole visits for most patients; the level 3 reference mean is not reported in the text read; Belgium.
- **Implication:** Nursing time rises steeply with acuity (level 1 about 100 minutes above level 3, levels 4-5 about 20-25 below), the same ordering as the catalog's `nurse_care_min_per_hour`; no per-hour figure could be derived, so those values stay assumed. About 45 nurse-minutes per patient present is a staffing rule of thumb to check against.

### E-78 Minor supporting figures (weak evidence, not used for catalog values)
- Al-Hindi AA, Al-Akhfash AA, Fareed AM, et al. Efficacy of implementation of a 5 scale pediatric triage and acuity scale in pediatric emergency, Saudi Arabia. Saudi Med J 35(9):999-1004, 2014. https://pubmed.ncbi.nlm.nih.gov/25228183/ . Abstract: 3,337 children triaged; triage took 5 minutes or less in 97% of cases; LWBS 6.25%. Consistent with the 3-6 minute triage placeholders.
- Hadi YH, Altalhi FK, Ali HM, et al. Enhancing CT examination efficiency with ChatGPT-4o for multilingual Hajj pilgrims. J Med Imaging Radiat Sci, 2025. https://doi.org/10.1016/j.jmir.2024.101781 . Abstract: mean CT examination time 15.4 (SD 2.1) minutes, 49.5 cases per shift, before a translation aid; 11.1 (1.7) after. Special population; suggests the 22-minute CT slot placeholder is on the long side.
- Brief abstract figures on intrahospital transport: Li N et al., J Perianesth Nurs 2026, https://pubmed.ncbi.nlm.nih.gov/42640243/ : mean transport duration 9.68 (SD 4.25) minutes for 255 post-anaesthesia transfers in one Chinese hospital. No distance given, so no speed can be derived.

---

## Sources searched for and not found, or found but not usable

- A per-hour, per-acuity probability of clinical deterioration in the waiting room: no study located. E-68 gives a rate for admitted boarders, used for ESI 2-3; ESI 1, 4 and 5 stay assumed.
- RL or approximate dynamic programming for ED staffing levels, or for ambulance diversion: none located (diversion work found is simulation-optimisation, E-44, and reviews, E-31). Dai and Shi's 2019 approximate-DP overflow paper is known only through E-38.
- Published failure and repair distributions for imaging equipment, ventilators, monitors and lab analysers: only one scanner's service log (E-60).
- ED treatment-bay cleaning and turnaround times: nothing ED-specific.
- Scan durations for CT, MRI, X-ray and ultrasound from a representative ED sample; stretcher and wheelchair transport speeds; nurse minutes per patient-hour by acuity; the effect of fatigue on working speed (as opposed to errors).
- A peer-reviewed arrival curve for a US mass-casualty event at a single hospital beyond E-57.
- The Rogers et al. 2004 odds ratio for shifts of 12.5 hours or more: appears in secondary summaries but not in any text fetched here, so it is not cited as a number.
- A national door-to-provider benchmark from the literature: left to the data workstream's Care Compare extract.
- Batt and Terwiesch's published-version regression tables: only the working paper was readable.
- New Jersey's current hospital staffing regulation text (N.J.A.C. 8:43G) and the legislative status of A1974 and its Senate companion.
