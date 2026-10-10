# Diagnostics workflow gaps: external evidence

This file adds external evidence for laboratory specimen handling, turnaround and rejection; imaging transport, scheduling and reporting; and emergency blood-bank workflows. Every measure below is an external reference, not a measurement of Robert Wood Johnson University Hospital (RWJ). The records are available in [`gaps-diagnostics.json`](gaps-diagnostics.json).

## What the sources establish

- **Laboratory lifecycle:** A tertiary hospital documented accession sorting, manual exception logging, rejection criteria, and monthly review. In its 2018 retrospective sample of 113,817 hematology and chemical-pathology specimens, 1,688 (1.48%) had a recorded preanalytical error. Among those errors, unlabeled specimens were the largest reported category (604/1,688; 35.8%). The rejection mix is conditional on that site's logged errors and should not be assigned to RWJ.
- **Laboratory turnaround:** A prospective before-after ED study at Massachusetts General Hospital found median collection-to-result TAT improvements after sample-flow redesign, including troponin T 86 to 53 minutes and urine sedimentation 117 to 29 minutes. These are observed medians, not distributions; the accessible abstract did not report exact test counts or dates.
- **Imaging:** An academic ED CT quality-improvement study reported order-to-final-report time averaging 5.9 hours (median 4.2) across 10,063 pre-period orders. A multidisciplinary intervention was associated with 1.2 hours lower turnaround in the post period despite 13.8% more orders. A separate ED plain-film study measured transport TAT falling from 22.89 to 9.87 minutes after a pending-request dashboard and a peak-hours dedicated transporter. These endpoints cover different workflows and modalities.
- **Blood bank:** A Level I trauma-center MTP study distinguished immediately available uncrossmatched RBCs from subsequent patient-specific crossmatched products. In selected massive-transfusion patients, mean arrival-to-first documented crossmatched RBC time fell from 115 to 71 minutes after implementation. Another center's ED refrigerator study observed 158 adult recipients and 292 emergency-stock units over 15 months, but did not measure request-to-issue minutes.

## Scenario implications

The evidence supports modeling diagnostics as linked but separate resources and states: specimen collection, identification, transport, accession/acceptance, rejection and recollection, analysis, reflex testing, result reporting; imaging order/protocoling, preparation, transport, modality queue/acquisition, interpretation and report; blood-bank emergency release, compatibility testing, dispatch, transfusion and reconciliation. Scheduling, transporter availability, staffing, equipment queues and handoffs can each delay the endpoint. The published summary statistics do not justify inventing service-time distributions or RWJ-specific rates.

## Source access and limitations

Access provenance is recorded per evidence record. I inspected the original IFCC journal PDF for the specimen-rejection study, the publisher abstract (not full text) for the lab TAT study, Europe PMC fullTextXML for the plain-film transport and ED refrigerator studies, and the original article PDF mirror for the MTP study. The CT article remains marked `search_index_only_pending_primary_inspection`: PubMed Central returned a verification wall and its Europe PMC fullTextXML endpoint returned HTTP 500. Its numbers remain provisional until the primary text can be inspected. Source access status and inspected URLs are in the JSON. Where an accessible abstract omitted counts or dates, that absence is stated. Evidence is paraphrased.

## Sources

1. Alavi et al., *eJIFCC* (2020), “Challenges in Preanalytical Phase of Laboratory Medicine: Rate of Blood Sample Nonconformity in a Tertiary Care Hospital.” [Journal PDF](https://cms.ifcc.org/wp-content/uploads/2020/03/ejifcc2020vol31no1.pdf); [PubMed Central record](https://pmc.ncbi.nlm.nih.gov/articles/PMC7109505/).
2. White et al., *American Journal of Emergency Medicine* (2015), “Applying Lean methodologies reduces ED laboratory turnaround times.” [Article record and abstract](https://www.em-consulte.com/article/1011139/figures/applying-lean-methodologies-reduces-ed-laboratory-). DOI: [10.1016/j.ajem.2015.06.013](https://doi.org/10.1016/j.ajem.2015.06.013).
3. Makkar et al., “Improving Emergency Department Flow: Reducing Turnaround Time for Emergent CT Scans.” [Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC6371246/).
4. Al Rafea et al., “Improving Emergency Department radiology transportation time: a successful implementation of lean methodology.” [Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC5584336/).
5. Riskin et al., *Journal of the American College of Surgeons* (2009), “Massive Transfusion Protocols: The Role of Aggressive Resuscitation Versus Product Ratio in Mortality Reduction.” [Original paper PDF mirror](https://pqcnc-documents.s3.amazonaws.com/aim/aimexpert/PQCNCOBHMassiveTransfusionProtocolsAmCollegeofSurgeons20090416.pdf). DOI: [10.1016/j.jamcollsurg.2009.04.016](https://doi.org/10.1016/j.jamcollsurg.2009.04.016).
6. “Experience with uncrossmatched blood refrigerator in emergency department.” [Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC6203135/).
