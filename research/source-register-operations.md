# Source register: operations additions

Additions to [source-register.md](source-register.md) for the operations workstream, prepared October 10, 2026
during the overnight build. It follows the same convention: the register explains provenance and verification
limits; citations appear beside the findings in [operations-evidence.md](operations-evidence.md), whose record
numbers (`E-n`) are used below. Nothing here grants a license to redistribute the original materials; only
derived findings and short quotations are published.

## How sources were obtained

| Route | What it returned | Used for |
|---|---|---|
| Europe PMC REST API (`europepmc.org` web services) | Title, authors, journal, year, volume, pages, DOI and the publisher's abstract for PubMed-indexed papers; full-text XML for open-access papers | Most clinical and health-services records. Bibliographic details in the evidence file are taken from these metadata records |
| arXiv API and PDFs | Abstracts and full text of preprints | Queueing and reinforcement-learning records (E-35 to E-38, E-40, E-44, E-45, E-47) |
| Direct fetch of publisher, agency or institutional pages and PDFs | Regulation text, bill text, statistical tables, reports, an author-hosted working paper, an NSF public-access manuscript | E-01, E-02, E-04, E-06, E-48, E-49, E-55, E-56, E-60, E-62, E-63 |
| Web search | Leads only. A search-result summary was never used as the source of a number; anything that could not then be fetched is listed under "Not verified" |  |

Each evidence record states how much was read: abstract, full text, or page. "Abstract" means the claim rests on
the publisher's abstract and the paper's methods and tables were not inspected.

## Public sources and what they establish

| Source group | Finding supported | Records |
|---|---|---|
| Batt and Terwiesch working paper (Wharton, author-hosted) and the published abstract on RePEc | LWBS share and mean wait by triage level in one large US ED; effect of visible queue length, arrivals and early test ordering on leaving | E-01 |
| Western Journal of Emergency Medicine open-access articles (Rathlev 2020; Pielsticker 2015; Ramsey 2018; Dhanik 2024; Delgado 2013) | LWBS odds by door-to-provider time, queue length, boarders and arrival mode; door-to-room thresholds; nurse-hours and throughput; CT order-to-completion times; diversion simulation review | E-02, E-04, E-51, E-58, E-31 |
| Large administrative cohort studies (Guttmann 2011 BMJ full text; Jones 2022; Sun 2013; Hsia 2011; Sax 2023; Schull 2007; Joseph 2025; abstracts) | Mortality and admission after long ED stays; boarding dose-response; LWBS variation between hospitals; mis-triage rate; low-acuity spillover; outcomes of patients who leave | E-09, E-15, E-19, E-03, E-11, E-30, E-05 |
| Single-site and multi-site cohort studies of boarding (Singer 2011; Sprivulis 2006; Richardson 2002; Roussel 2023; McCarthy 2009; Epstein 2012; abstracts) | Boarding time against mortality and inpatient stay; crowding against waits, boarding and errors | E-16, E-17, E-20, E-18, E-21, E-22 |
| Systematic reviews and meta-analyses (Oredsson 2011; Rowe 2011; Benabbas 2020; Jeyaraman 2022; Hinson 2019; Hoot and Aronsky 2008; Morley 2018; Bernstein 2009; abstracts) | Strength of evidence and pooled effects for fast track, physician or advanced-practice triage; triage-scale performance; causes and consequences of crowding | E-25 to E-28, E-13, E-34 |
| Intervention and modelling studies of flow levers (Sanchez 2006; Hsieh 2023; Powell 2012; Green 2006; Shen and Hsia 2011; abstracts) | Effect sizes for fast track, vertical split flow, discharge timing, arrival-matched staffing; diversion harm | E-24, E-29, E-23, E-33, E-32 |
| Arrival and productivity studies (Whitt and Zhang 2017 author manuscript; McCarthy 2008 abstract; Joseph 2018 full text; Wrede 2020 full text; Eitel 2003 abstract) | Time-varying arrivals and overdispersion; Poisson hourly counts; physician pickup rate by shift hour; physician minutes per patient by ESI; admission and mortality by ESI | E-06, E-07, E-08, E-10, E-14 |
| Queueing and RL preprints and papers (QGym; Che, Dong and Namkoong; Dai and Gluzman; Sun, Dai and Shi; Allen and Monks; Lee and Lee 2020 full text; Acuña and García preprint abstract; Piermarini and Roma abstract) | State, action and reward designs; baselines; training settings; where RL beat or lost to heuristics; GPU and differentiable queueing simulators | E-35 to E-41, E-44 |
| Published ED discrete-event simulations (Hoot 2008; Connelly and Bair 2004; abstracts) | How ED simulations were calibrated and validated, and the accuracy achieved | E-42, E-43 |
| AI standardized-patient and automated-scoring studies (Shakur 2024; Wang 2025; Yu 2024; abstracts) | Agreement of LLM rubric scoring with human graders; scoring sensitivity to prompts; accuracy of a knowledge-graph-grounded simulated patient | E-45 to E-47 |
| California Code of Regulations, Title 22, section 70217 (Cornell Legal Information Institute copy) | Enforced nurse-to-patient ratios by unit type, including the emergency department | E-48 |
| New Jersey Legislature, Assembly bill A1974 as introduced January 13, 2026 | Proposed (not enacted) New Jersey ratios | E-49 |
| Nurse staffing, fatigue and work-hours studies (Aiken 2002; Landrigan 2004; Barger 2006; Rogers 2004; Scott 2006; Olds and Clarke 2010; abstracts) | Mortality and burnout per patient per nurse; error rates on extended shifts | E-50, E-52 to E-54 |
| NSI Nursing Solutions 2026 retention report (industry survey PDF) | Hospital and RN turnover, vacancy, cost of RN turnover, turnover by specialty | E-55 |
| US Bureau of Labor Statistics, Current Population Survey Table 47 (2025 annual averages) | Absence and lost-worktime rates for healthcare occupations | E-56 |
| Imaging and room-turnaround sources (Brunner 2014 abstract; Jalal 2021 abstract; Ankrum 2019 abstract; MD Anderson conference abstract; Vienna hospital CT downtime page) | Imaging turnaround medians; effect of radiologist coverage; bed turnaround; one scanner's downtime log | E-57, E-59, E-61, E-62, E-60 |
| Event sources (CDC FluView week 5 of 2025; Schanzer and Schwartz 2013; Schull 2004; Lake 2025 full text; Brunner 2014) | Influenza share of ED visits and attributable visits; influenza and diversion; mass-casualty sizes and arrival timing | E-63 to E-66, E-57 |
| Bohannon 1997 (abstract) | Adult walking speeds | E-67 |
| Second-pass additions: Rizer 2026 and Chang 2019 (abstracts); Zattoni 2026 PhD thesis and Rosemarin 2019 AAAI paper (full text); Koduri 2025 preprint (abstract) | Deterioration among ED boarders; cardiac arrest and occupancy; an ED simulation with A2C/PPO rule selection, its reward design and results; imitation-learned ED scheduling; masked PPO for nurse assignment | E-68 to E-72 |
| Productivity and ancillary-service studies: Joseph 2017, Shaw 2024, Hamden 2014, McDonnell 2015 (abstracts); Walker 2019 scribe trial; Vrijsen 2022 and Hausfater 2020 on laboratory turnaround; Dilip 2025 on hallway spaces (abstracts); Ganty 2025 nursing workload (full text) | Resident and advanced-practice productivity; scribe effect; lab turnaround and the effect of point-of-care testing; hallway treatment times; nursing time by triage level | E-73 to E-77 |
| Weak supporting abstracts (Al-Hindi 2014; Hadi 2025; Li 2026) | Triage duration, CT examination time, transport duration; recorded but not used for catalog values | E-78 |

## Verification boundaries

- **Abstract-only records.** About two thirds of the clinical records rest on the abstract. Effect sizes quoted are
  the abstract's headline numbers; subgroup results, model specifications and tables were not checked.
- **Derived numbers.** Exponential patience means, per-hour death hazards, the boarding length-of-stay penalty per
  hour, per-acuity patients per hour, the CT failure probability, the flu arrival multiplier and the
  mass-casualty arrival window were computed by the research agent from published figures. Each is labelled
  `derived` in the parameter file and "DERIVED" in the catalog note, with the formula. They are approximations for
  a simulator, not findings of the cited studies.
- **Observational evidence.** Almost all mortality and length-of-stay effects of waiting, boarding and staffing
  come from observational cohorts with residual confounding; sicker patients wait and board longer. The
  simulator may use them to scale a harm term but must not present outputs as forecasts for a real hospital.
- **Settings.** Several sources are outside the United States (Ontario, England, Western Australia, France,
  Germany, Israel, Korea, Austria) or older than fifteen years; each record states its setting and period.
- **Preprints and non-peer-reviewed material.** E-35 to E-38, E-40, E-44, E-45 and E-47 are arXiv preprints
  (some since published; publication status was not checked); E-41 is a Research Square preprint; E-55 is an
  industry survey; E-62 is a conference abstract; E-60 is a hospital web page describing one machine; E-70 is a
  doctoral thesis; E-72 is a single-author preprint.
- **Chart reading.** The emergency-specialty RN turnover figures in E-55 were read from a chart in extracted PDF
  text; the assignment of the two columns to 2024 and 2025 was inferred from the report's prose.

## Not verified, and therefore not cited as findings

| Item | Status |
|---|---|
| Odds ratio for nurse errors on shifts of 12.5 hours or more (Rogers 2004) | Seen only in secondary summaries; the abstract and the AHRQ PSNet page give no number. Not used |
| Cost range and time-to-fill figures from earlier NSI report editions | Seen only in secondary news summaries. Not used |
| Per-hospital patient counts for the 2017 Las Vegas shooting | Slide decks and news reports only; the peer-reviewed review read (E-66) gives city-wide totals |
| Abdulwahid et al. 2016 meta-analysis of senior doctor triage; Burke et al. evaluation of the Massachusetts diversion ban; Pham et al. 2006 diversion review | Identified by search, not fetched. Not cited |
| New Jersey's existing hospital staffing rules (N.J.A.C. 8:43G) and the current status of A1974 and S3022 | Not fetched |
| Published journal versions of the arXiv preprints, and the regression tables of the published Batt and Terwiesch paper | Not checked |
| Emergency Severity Index mortality figures from Thai and Korean cohorts returned by search | Not fetched. Not cited |
