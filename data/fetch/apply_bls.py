"""Write BLS OEWS wages into catalog/staff.yaml (wage_per_hour per role). Run after bls_oews.py."""
import pandas as pd

from _catalog_edit import set_attr
from _common import PROCESSED

df = pd.read_csv(PROCESSED / "bls_oews_staff_wages.csv").set_index(["area", "soc"])
URL = "https://www.bls.gov/oes/"
F = "data/processed/bls_oews_staff_wages.csv"
yr = int(df["year"].iloc[0])
DS = f"BLS Occupational Employment and Wage Statistics, May {yr} estimates, New Jersey statewide, all industries (BLS public API series OEUS3400000000000<SOC><datatype>)"


def w(soc, col="hourly_mean", area="nj_state"):
    return float(df.loc[(area, soc), col])


def S(role, value, how, note):
    print(role, set_attr("catalog/staff.yaml", ["variants", role, "attributes", "wage_per_hour"],
                         {"value": round(value, 2), "unit": "usd/hour", "source": "measured", "citation": f"{DS}; {how}", "url": URL, "file": F, "note": note}))


def metro(soc, col="hourly_mean"):
    return f"New York-Newark-Jersey City metro {col.replace('hourly_', '')}: {w(soc, col, 'ny_newark_metro'):.2f}."


S("attending", w("29-1214", "hourly_median"), "SOC 29-1214 Emergency Medicine Physicians, hourly MEDIAN",
  f"Median, not mean: the distribution is bimodal (25th percentile {w('29-1214', 'hourly_p25'):.2f}, 75th {w('29-1214', 'hourly_p75'):.2f}, mean {w('29-1214'):.2f}), "
  f"which suggests trainees are coded in the same occupation. {metro('29-1214', 'hourly_median')} Base wage only; benefits are applied through staff.shared.benefits_load.")
S("app", (w("29-1171") + w("29-1071")) / 2, f"unweighted mean of SOC 29-1171 Nurse Practitioners ({w('29-1171'):.2f}) and SOC 29-1071 Physician Assistants ({w('29-1071'):.2f}), hourly mean",
  f"All specialties, not ED-specific. {metro('29-1171')}")
S("rn", w("29-1141"), "SOC 29-1141 Registered Nurses, hourly mean", f"All settings, not ED-specific. {metro('29-1141')}")
S("charge_rn", w("29-1141", "hourly_p75"), "SOC 29-1141 Registered Nurses, hourly 75th percentile",
  f"There is no charge-nurse occupation code; the RN 75th percentile is used as a proxy for a senior nurse (a mapping assumption). {metro('29-1141', 'hourly_p75')}")
S("tech", (w("29-2042") + w("31-1131")) / 2, f"unweighted mean of SOC 29-2042 Emergency Medical Technicians ({w('29-2042'):.2f}) and SOC 31-1131 Nursing Assistants ({w('31-1131'):.2f}), hourly mean",
  "There is no ED-technician occupation code; hospitals fill the role with EMT-certified or nursing-assistant staff. " + metro("29-2042"))
S("registration", w("43-4111"), "SOC 43-4111 Interviewers, Except Eligibility and Loan (the code that covers hospital admitting / registration interviewers), hourly mean", metro("43-4111"))
S("pharmacist", w("29-1051"), "SOC 29-1051 Pharmacists, hourly mean", metro("29-1051"))
S("imaging_tech", w("29-2034"), "SOC 29-2034 Radiologic Technologists and Technicians, hourly mean", "CT/MRI technologists (SOC 29-2035) earn more; not fetched. " + metro("29-2034"))
S("transport", w("31-1132"), "SOC 31-1132 Orderlies, hourly mean", metro("31-1132"))
S("evs", w("37-2011"), "SOC 37-2011 Janitors and Cleaners, Except Maids and Housekeeping Cleaners, hourly mean", "All industries. " + metro("37-2011"))
