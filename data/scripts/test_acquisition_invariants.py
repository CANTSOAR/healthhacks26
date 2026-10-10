#!/usr/bin/env python3
"""Offline regressions for source-quarter/hospital identity and staffing semantics."""
from acquire_ops_wave2 import parse_staffing
HOSPITAL='Example Hospital'
def section(date,value,daily=False):
 label='Emergency Department Number of Patients: 100' if daily else 'Med-Surg'
 measure='Daily Staff' if daily else 'Number of Patients per Staff'
 return f'<h3>Staffing for Quarter Ending {date}</h3><table><tr><td class="black11bold">{label}</td></tr><tr><td>{measure}</td></tr><tr><td></td><td>Registered Professional Nurse</td><td></td><td>{value}</td></tr></table>'
def parse(body,hospital=HOSPITAL):
 return parse_staffing(body,hospital,'2026-10-10T00:00:00Z','https://example.org','','')
header=f'<h1>Report of Hospital Patient Care Staffing {HOSPITAL}</h1><a>Hospital Profile</a>'
html=header+section('September 30, 2026','999')+section('June 30, 2026','5')+section('March 31, 2026','888')
returned_hospital,period,rows=parse(html)
assert period=='2026-06-30' and len(rows)==1
assert rows[0]['patients_per_staff_as_published']['Registered Professional Nurse']=='5'
for bad in [header+section('September 30, 2026','999'),html.replace(HOSPITAL,'Another Hospital')]:
 try:parse(bad)
 except RuntimeError:pass
 else:raise AssertionError('Missing quarter or wrong hospital accepted')
returned_hospital,period,rows=parse(header+section('June 30, 2026','10',daily=True))
assert rows[0]['measure_type']=='daily_staff_counts'
assert rows[0]['daily_patient_count_as_published']=='100'
assert 'patients_per_staff_as_published' not in rows[0]
print('PASS: exact quarter despite newer report, hospital identity rejection, missing quarter rejection, daily counts not ratios')
