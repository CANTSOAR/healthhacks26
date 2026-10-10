# Emergency encounter timing evidence

This is a bounded set of external timing references for scenario design. Every record is labeled `external_reference_not_RWJ`. It keeps queue wait, staff service duration, and elapsed process turnaround distinct. Reported empirical summaries remain summaries; no mean was converted into a distribution, and no independence or cross-stage correlation is asserted.

## Sources and interpretation

### Rio de Janeiro ED administrative-record study

[Performance evaluation of an emergency department in Rio de Janeiro: a hybrid approach using Discrete Events Simulation and Data Envelopment Analysis](https://doi.org/10.1590/1806-9649-2024v31e1024), DOI 10.1590/1806-9649-2024v31e1024. Publisher full text, including Table 7 and the appendix fit table, inspected. Correction after full English PDF inspection: our earlier claim that the body says all fit-test p-values exceed 0.05 was unsupported and is withdrawn. Appendix 2 has ambiguously formatted fit statistics and <0.05 annotations; Appendix 6 reports a separate observed-versus-simulated comparison. T1 triage also has two different lognormal expressions in the table and appendix. Both triage and consultation fit records are blocked from quantitative use pending fit review and source resolution; the expressions are preserved as printed. Triage duration is missing in 55.07% and consultation duration in 16.46%; stage sample sizes are absent. The shift-specific empirical means remain separate from these disputed fits.

### Quebec ambulatory ED simulation study

[Discrete-event simulation and design of experiments to study ambulatory patient waiting time in an emergency department](https://doi.org/10.1080/01605682.2018.1510805), DOI 10.1080/01605682.2018.1510805. Full author manuscript inspected. One week included 1,035 arrivals, of whom 640 were ambulatory. The paper lists simulation inputs for triage, registration and consultations, including triangular assumptions. It does not give fit counts or a clear fitting method for each distribution. Triangular inputs are explicitly stored as model assumptions, not observed quantiles or proven empirical fits. Applicability is limited to the study's ambulatory ED setting.

### Beirut ED radiology transport process

[Improving Emergency Department radiology transportation time: a successful implementation of lean methodology](https://doi.org/10.1186/s12913-017-2488-5), DOI 10.1186/s12913-017-2488-5. Publisher full text inspected. Methods define transportation TAT as cashier order processing to PACS-recorded radiographer study initiation. The Discussion later describes it as extending to study completion; the JSON follows the explicit Methods endpoint and records the discrepancy. The cohort included 6,186 radiographs in 2012-10-17 to 2013-04-17 and 4,879 in 2013-05-19 to 2013-11-19, after a washout. Overnight cases, AMA departures, and transfers were excluded. Means, SDs, and the share at or below 10 minutes are reported; these do not provide the full distribution.

## Gaps

These sources do not establish RWJ timing. No sufficiently inspected primary timing record in this set gives a usable room-turnaround distribution, a full transport distribution, or a detailed empirical imaging-processing distribution. Values requiring a model family must retain their source status and parameter convention. The Rio ARENA notation is copied as printed; do not reinterpret software parameters until its conventions are checked. Do not combine stage distributions under an independence assumption.

Retrieval time recorded in the JSON is 2026-10-10T20:55:17Z. The JSON records each source locator, evidence basis, access status, limitations, and scenario use.
