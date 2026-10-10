# Timing calibration conflict resolution

Four source-audit records are in [`calibration-timing.json`](calibration-timing.json). All remain external references, not RWJ measurements. Rio's parameter convention can be interpreted from Arena documentation, but the reported fit itself remains unresolved and quantitatively blocked.

## Rio ED: copied expressions and fit/validation ambiguity

The publisher PDF was inspected through SciELO. It reports 3.81 minutes as the T1 triage mean (95% CI 3.76–3.85), while Table 7 gives `1.5 + LOGN(1.86, 1.32)` and Appendix 2 gives `1.5 + LOGN(1.05, 0.848)`. The paper says input fitting used Arena Input Analyzer; no fitting sample count or fit window is given, and 55.07% of triage durations are missing. No public corrigendum or supplement surfaced in targeted searches of the journal/SciELO record and exact-DOI/title queries. That is a search result, not evidence that no correction exists.

Arena's manufacturer-authored guide defines `LOGN(LogMean, LogStd)` arguments as the arithmetic mean and standard deviation of the lognormal random variable. Under that convention, and reading the paper's `1.5 +` as an additive shift, the expressions imply means of 3.36 and 2.55 minutes. Those are arithmetic implications, not published sample estimates, and neither matches the reported 3.81-minute mean. This clarifies the convention while making the source discrepancy no less unresolved. Retain both expressions for provenance; do not choose one as a calibrated input.

Appendix 2 prints fit-test statistic columns and parenthetical `<0.05` annotations; for example, T1 triage lists 1.0 and 52.7. The table does not clearly identify those parenthetical values as p-values. Separately, the body describes observed-versus-simulated comparisons of stage/total lengths of stay, and Appendix 6 reports p<0.05 for these comparisons. That downstream comparison is evidence of a mismatch, not evidence that an input distribution passed a goodness-of-fit test. In the inspected English full text, I did not find a statement that all fit-test p-values exceeded 0.05. The earlier summary's asserted opposite body result is therefore not independently substantiated by this audit. Do not claim validated fit or validated stage timing.

Sources inspected: [publisher full-text PDF](https://www.scielo.br/j/gp/a/Kv5ScCmWSCwzsNYLDvTMqhx/?format=pdf&lang=en), [Arena User's Guide PDF](https://medarbejdere.au.dk/fileadmin/www.medarbejdere.au.dk/it/BSS_Analysevaerktoejer/Arena/Arena_User_s_Guide_EN.pdf). The guide is manufacturer-authored but hosted at Aarhus University and is older than the Rio article; it establishes notation only.

## Beirut radiology timing: endpoint choice

The paper's Methods define transportation TAT as cashier order processing to PACS-recorded radiographer study initiation. Methods then define study-initiation-to-study-completion as a separate interval. The Discussion later calls transportation TAT “order processing to study completion.” Because the operational Methods definition and separate-stage decomposition agree, this record follows the Methods endpoint and preserves the Discussion wording as a reporting conflict. Reported means/SDs and threshold shares refer to this study-specific interval, not imaging acquisition completion or preliminary report time.

Sources inspected: [publisher full text](https://link.springer.com/article/10.1186/s12913-017-2488-5), [institutional repository PDF](https://scholarworks.aub.edu.lb/bitstreams/e1498a13-03fb-4e0e-8bc9-9189ba6920af/download).

## Status

- **Convention resolved:** Arena `LOGN` argument meaning, with an older manufacturer-authored guide as the evidence.
- **Not resolved:** intended Rio T1 triage expression; interpretation of Appendix 2 fit-test parenthetical annotations; fit validity.
- **Interpretable with caveat:** Beirut transportation endpoint, using the explicit Methods definition and flagging the Discussion's conflicting shorthand.
- **No local calibration:** every record is labeled `external_reference_not_RWJ`.

Parent manual check also confirms `GAMM(Beta, Alpha)` uses scale then shape and `EXPO(Mean)` uses the arithmetic mean, not an exponential rate (printed pp. 116–117). These clarified conventions do not remove the fit-validity block.
