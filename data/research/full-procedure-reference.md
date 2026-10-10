# Complete FY2027 ICD-10-PCS code and title reference

The data workspace now includes a complete normalized code/title catalog extracted from the retained original CMS FY2027 ZIP: [catalog manifest](../catalog/cms-icd10pcs-2027-full.json), [JSONL records](../normalized/cms-icd10pcs-2027-full.jsonl), and the deterministic builder [acquire_full_pcs.py](../scripts/acquire_full_pcs.py).

The ZIP is CMS's [2027 ICD-10-PCS Codes File](https://www.cms.gov/files/zip/2027-icd-10-pcs-codes-file.zip). Its `icd10pcs_codes_2027.txt` member has 79,256 lines. Every line parsed as one seven-character code and nonempty title; all 79,256 code identifiers are unique. The parser rejects malformed rows and duplicate codes. It checks the retained ZIP SHA-256 against the acquired source manifest before producing output. The ZIP's separate addenda member is not included because it is not part of the code/title file.

CMS's [ICD-10 files page](https://www.cms.gov/medicare/coding-billing/ICD-10-codes) identifies the 2027 PCS files and lists this Codes File for discharges from October 1, 2026 through March 31, 2027. Check CMS for subsequent FY2027 updates and applicable official coding guidelines before operational use.

Each JSONL record carries the code and title, a dataset-scoped record ID, source URL, source retrieval timestamp, original ZIP SHA-256 and path, code-file line locator, source scope, and terminology-reference limitations. The normalized output is 87,898,750 bytes (about 87.9 MB decimal). It is a code catalog: its 79,256 rows do not count procedures performed, establish what RWJ offers or can perform, provide utilization or outcomes, or define a treatment protocol. The selected 444-code dataset remains separately scoped; it is not overwritten by this full reference.
