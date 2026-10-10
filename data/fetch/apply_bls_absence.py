"""Write the BLS CPS absence figure into catalog/staff.yaml. The table itself (data/processed/bls_cps_absences_table47_2025.json) was TRANSCRIBED,
not downloaded by a script: www.bls.gov answers 403 to scripted clients. Source tag is therefore 'literature'."""
import json

from _catalog_edit import set_attr
from _common import PROCESSED

t = json.loads((PROCESSED / "bls_cps_absences_table47_2025.json").read_text())
r = {x["group"]: x for x in t["rows"]}
prac, supp = r["Healthcare practitioners and technical occupations"], r["Healthcare support occupations"]
print(set_attr("catalog/staff.yaml", ["shared", "absence_rate"], {
    "value": prac["lost_worktime_total"] / 100, "unit": "fraction of scheduled shifts", "source": "literature",
    "citation": f"{t['table']}: lost worktime rate, total, for 'Healthcare practitioners and technical occupations' = {prac['lost_worktime_total']} percent of usual hours",
    "url": t["url"], "file": "data/processed/bls_cps_absences_table47_2025.json", "range": [prac["lost_worktime_total"] / 100, supp["absence_rate_total"] / 100],
    "note": "Published table value, transcribed (bls.gov blocks scripted download; read via a fetch tool twice with matching figures - re-verify in a browser). Lost worktime rate = "
            "hours absent / hours usually worked, the closest published analogue of a share of scheduled shifts missed. range upper end = the absence rate of healthcare support "
            f"occupations ({supp['absence_rate_total']}% of workers absent in the reference week; practitioners {prac['absence_rate_total']}%). 2025 averages exclude October. "
            "Wave 0 placeholder was 0.035."}))
