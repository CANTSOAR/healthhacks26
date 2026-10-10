#!/usr/bin/env python3
"""Acquire bounded NJ public hospital facility and staffing snapshots.

The NJ licensing endpoint contains unnecessary contact fields, so its retained
JSON is an explicit field projection. Staffing reports are published as
server-rendered HTML; only Q2 2026 inpatient ratios and ED/PACU daily staffing
summaries are kept.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'raw' / 'w2-ops-nj'
HOSPITALS = {
    '11202': 'Robert Wood Johnson University Hospital - New Brunswick',
    '11205': "Saint Peter's University Hospital - New Brunswick",
}
TARGET_STAFFING_END = 'June 30, 2026'
TARGET_STAFFING_QUARTER = '2026-Q2'
FACILITY_LIMIT = 200
CMS_PAGE_LIMIT = 5000


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def get(url, data=None, opener=None):
    headers = {'User-Agent': 'HealthHacks-public-research/1.0'}
    if data:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Referer'] = url
    req = urllib.request.Request(url, data=data, headers=headers)
    return (opener or urllib.request.build_opener()).open(req, timeout=45).read()


def write_raw(name, body):
    p = RAW / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return str(p.relative_to(ROOT.parent)), hashlib.sha256(body).hexdigest()


def save_dataset(slug, title, url, scope, rights, limits, records, raw_paths, retrieved, extra=None):
    normalized = ROOT / 'normalized' / f'{slug}.jsonl'
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in records))
    cat = {
        'dataset_id': slug, 'source_id': slug, 'title': title, 'source_url': url,
        'scope': scope, 'access': 'public_no_authentication', 'rights': rights,
        'acquisition_status': 'acquired', 'raw_paths': raw_paths,
        'normalized_path': str(normalized.relative_to(ROOT.parent)),
        'record_count': len(records), 'limits': limits,
        'provenance': {'retrieved_at': retrieved},
    }
    if extra:
        cat.update(extra)
    if cat.get('raw_artifact_kind'):
        cat['provenance']['raw_artifact_kind'] = cat['raw_artifact_kind']
    p = ROOT / 'catalog' / f'{slug}.json'
    p.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'dataset_id': slug, 'record_count': len(records), 'raw_paths': raw_paths}))


def envelope(slug, rid, kind, data, url, stamp, path, digest, limitations=None):
    return {
        'record_id': f'{slug}:{rid}', 'source_id': slug, 'source_record_id': str(rid),
        'record_type': kind, 'data': data,
        'provenance': {'source_url': url, 'retrieved_at': stamp, 'raw_path': path,
                       'raw_sha256': digest, 'acquisition_method': 'public HTTP API/form',
                       'transformation': 'field projection; source values retained as published'},
        'evidence_kind': 'reported_operational_measure', 'review_status': 'unreviewed',
        'mapping_status': 'unmapped', 'limitations': limitations or [],
    }


class Node:
    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def text(self):
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children)


class TreeParser(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def descendants(node, tag=None):
    for child in node.children:
        if isinstance(child, Node):
            if tag is None or child.tag == tag:
                yield child
            yield from descendants(child, tag)


def acquire_facilities():
    slug = 'w2-ops-nj-licensed-facilities'
    stamp = now()
    base = 'https://data.nj.gov/resource/mrzk-zrvp.json'
    params = {
        '$where': "facility_type='GENERAL ACUTE CARE HOSPITAL'",
        '$select': 'facid,facility_type,lic,licensed_name,fac_city,fac_st,zip,county,lic_expires,hospbedtotal',
        '$order': 'facid', '$limit': str(FACILITY_LIMIT),
    }
    url = base + '?' + urllib.parse.urlencode(params)
    rows = json.loads(get(url))
    if (not isinstance(rows, list) or not rows or len(rows) >= FACILITY_LIMIT
            or any(r.get('facility_type') != 'GENERAL ACUTE CARE HOSPITAL' or r.get('fac_st') != 'NJ'
                   or not r.get('facid') for r in rows)
            or len({r['facid'] for r in rows}) != len(rows)):
        raise RuntimeError('NJ facility response failed nonempty, geography, uniqueness or page-limit checks')
    projection = {'source_url': url, 'retrieved_at': stamp,
                  'raw_artifact_kind': 'projected_response',
                  'transformation': 'selected licensing, location and hospital-bed fields; contact and owner fields excluded',
                  'returned_count': len(rows), 'results': rows}
    body = (json.dumps(projection, ensure_ascii=False, indent=2) + '\n').encode()
    path, digest = write_raw('nj-licensed-facilities.json', body)
    records = [envelope(slug, r['facid'], 'FacilityCapacitySnapshot', r, url, stamp, path, digest,
                        ['hospbedtotal is the source-reported hospital bed total; the endpoint does not specify that these are staffed or currently available beds.']) for r in rows]
    save_dataset(slug, 'NJ general acute-care licensed facility inventory and reported hospital bed total',
                 'https://data.nj.gov/Health/Search-for-Hospitals-Ambulatory-Care-and-other-Acu/9aig-5kq7',
                 f"{len(rows)} rows with facility_type='GENERAL ACUTE CARE HOSPITAL' from NJ's licensed/certified health-facility inventory; snapshot queried {stamp}.",
                 {'basis': 'New Jersey public open-data factual records', 'source_license': 'unspecified in catalog',
                  'redistribution': 'selected factual fields; attribution and source link retained'},
                 ['Snapshot only; license expiry is not a validation of current status.',
                  'Hospital bed total is not a measure of staffed, open, occupied or immediately available capacity.',
                  'Facility license identifiers are retained; CMS CCN crosswalk is not asserted.'],
                 records, [path], stamp,
                 {'upstream_dataset_id': 'mrzk-zrvp', 'raw_artifact_kind': 'projected_response',
                  'queries': [{'url': url, 'returned_count': len(rows)}]})


def parse_staffing(html, hospital, stamp, source_url, path, digest):
    full_text = re.sub(r'\s+', ' ', TreeParser(html).root.text()).strip()
    identity_match = re.search(r'Report of Hospital Patient Care Staffing\s+(.*?)\s*Hospital Profile', full_text, re.I)
    if not identity_match:
        raise RuntimeError(f'No returned hospital identity heading for {hospital}')
    returned_hospital = identity_match.group(1).strip()
    if returned_hospital.casefold() != hospital.casefold():
        raise RuntimeError(f'Requested hospital {hospital!r}, response identifies {returned_hospital!r}')

    heading_pattern = r'Staffing for Quarter Ending ([A-Za-z]+ \d{1,2}, \d{4})'
    headings = list(re.finditer(heading_pattern, html))
    target = next((m for m in headings if m.group(1) == TARGET_STAFFING_END), None)
    if not target:
        raise RuntimeError(f'Report quarter ending {TARGET_STAFFING_END} was not returned for {hospital}')
    later_heading = next((m for m in headings if m.start() > target.start()), None)
    target_section = html[target.start():later_heading.start() if later_heading else len(html)]
    tree = TreeParser(target_section)
    text = tree.root.text()
    period_match = re.search(heading_pattern, text)
    if not period_match:
        raise RuntimeError(f'No quarter heading in staffing response for {hospital}')
    if period_match.group(1) != TARGET_STAFFING_END:
        raise RuntimeError(f'Parsed wrong staffing quarter for {hospital}: {period_match.group(1)}')
    report_date = dt.datetime.strptime(period_match.group(1), '%B %d, %Y').date().isoformat()
    slug = 'w2-ops-nj-staffing'
    records = []
    # Each unit is rendered in a nested table. Keep the published staff labels
    # and numeric strings without reinterpreting them.
    for table in descendants(tree.root, 'table'):
        unit_cells = [td for td in descendants(table, 'td') if 'black11bold' in td.attrs.get('class', '').split()]
        if len(unit_cells) != 1:
            continue
        unit = unit_cells[0]
        table_text = table.text()
        if 'Number of Patients per Staff' not in table_text and 'Daily Staff' not in table_text:
            continue
        unit_name = unit.text().strip()
        unit_name = re.sub(r'\s+', ' ', unit_name).strip()
        daily_count = None
        if 'Number of Patients:' in unit_name:
            unit_name, daily_count = [x.strip() for x in unit_name.split('Number of Patients:', 1)]
        rows = list(descendants(table, 'tr'))
        staff = {}
        for row in rows:
            cells = [c.text().strip() for c in row.children if isinstance(c, Node) and c.tag == 'td']
            if len(cells) >= 4 and cells[1] in ('Registered Professional Nurse', 'Licensed Practical Nurse', 'Unlicensed Assistive Personnel'):
                staff[cells[1]] = cells[-1]
        if staff:
            daily = 'Daily Staff' in table_text
            data = {'hospital_name': hospital, 'nj_hospital_identifier': None,
                    'report_quarter_ending': report_date, 'unit_type_as_published': unit_name,
                    'measure_type': 'daily_staff_counts' if daily else 'average_daily_patients_per_staff',
                    ('daily_staff_count_by_type_as_published' if daily else 'patients_per_staff_as_published'): staff}
            if daily_count is not None:
                data['daily_patient_count_as_published'] = daily_count
            # Correct identifier is set by the caller after parsing.
            records.append((unit_name, data))
    unique = {}
    for unit, data in records:
        unique[unit] = data
    if not unique:
        raise RuntimeError(f'No staffing observations parsed for {hospital}')
    return returned_hospital, report_date, list(unique.values())


def acquire_staffing():
    slug = 'w2-ops-nj-staffing'
    landing = 'https://healthapps.nj.gov/nursestaffing/quarterly.aspx'
    stamp = now()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    page = get(landing, opener=opener).decode('utf-8', 'replace')
    # Extract only ASP.NET hidden state needed for the public report form post.
    form = re.search(r'<form method="post" action="\./quarterly.aspx"[^>]*>(.*?)</form>', page, re.I | re.S)
    if not form:
        raise RuntimeError('NJ staffing report form not found')
    fields = {m.group(1): m.group(2) for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form.group(1), re.I) if m.group(1).startswith('__')}
    all_records = []
    paths = []
    report_dates = set()
    for hosp_id, hosp_name in HOSPITALS.items():
        payload = dict(fields)
        target_year, target_quarter = TARGET_STAFFING_QUARTER.split('-Q')
        payload.update({'ctl00$middleContent$ddlHospitals': hosp_id,
                        'ctl00$middleContent$ddlYear': target_year,
                        'ctl00$middleContent$ddlQuarter': target_quarter,
                        'ctl00$middleContent$Go': 'Go'})
        html = get(landing, urllib.parse.urlencode(payload).encode(), opener).decode('utf-8', 'replace')
        # The result page is large (it may contain all available history). Persist
        # only an exact text projection of the requested period, not page history.
        returned_hospital, report_date, projected = parse_staffing(html, hosp_name, stamp, landing, '', '')
        if report_date != dt.date(2026, 6, 30).isoformat():
            raise RuntimeError(f'Unexpected target reporting date for {hosp_name}: {report_date}')
        report_dates.add(report_date)
        for idx, d in enumerate(projected):
            d['nj_hospital_identifier'] = hosp_id
            d['report_quarter'] = TARGET_STAFFING_QUARTER
        projection = {'source_url': landing, 'retrieved_at': stamp,
                      'request': {'hospital_id': hosp_id, 'report_year': target_year, 'report_quarter': target_quarter},
                      'report_quarter_ending': report_date, 'hospital_name': returned_hospital,
                      'raw_artifact_kind': 'projected_response',
                      'transformation': 'retained Q2 2026 inpatient patient-to-staff ratios and ED/PACU daily staffing summaries; full HTML/history omitted',
                      'results': projected}
        body = (json.dumps(projection, ensure_ascii=False, indent=2) + '\n').encode()
        path, digest = write_raw(f'nj-staffing-{hosp_id}-2026q2.json', body)
        paths.append(path)
        for i, d in enumerate(projected):
            all_records.append(envelope(slug, f'{hosp_id}|{TARGET_STAFFING_QUARTER}|{i}', 'NurseStaffingObservation', d,
                                        landing, stamp, path, digest,
                                        ['NJDOH says staffing reports should not be used to compare hospitals or state averages; ratios do not reflect all caregivers or patient acuity.',
                                         'Quarterly values are reported averages, not current staffing or guaranteed staffing plans.']))
    save_dataset(slug, 'NJ Hospital Patient Care Staffing Quarterly Reports: RWJUH New Brunswick and Saint Peter’s, 2026 Q2',
                 landing,
                 'Publicly reported Q2 2026 inpatient unit average daily patient-to-staff ratios and ED/PACU daily staffing summaries for two New Brunswick general hospitals; quarter ending June 30, 2026.',
                 {'basis': 'New Jersey Department of Health public factual reports', 'source_license': 'not established',
                  'redistribution': 'limited selected factual values; original report URLs retained'},
                 ['Do not divide reported daily patient averages by daily RN/staff averages to infer a concurrent patient-to-staff ratio; these data do not provide time-aligned census and staffing observations.',
                  'Report quarter is 2026 Q2 (ended June 30, 2026); not live staffing.',
                  'NJDOH explicitly cautions that the reports should not be used to compare hospitals/state averages because patient needs, policy and layout differ.',
                  'Reports exclude many caregivers and are based on reported monthly averages from facility daily posting forms.',
                  'ED and PACU daily staff/patient summaries are retained where reported; other report history and sections were not acquired.'],
                 all_records, paths, stamp,
                 {'raw_artifact_kind': 'projected_response', 'provenance': {'retrieved_at': stamp,
                   'raw_artifact_kind': 'projected_response',
                   'data_period': {'start': '2026-04-01', 'end': '2026-06-30'}},
                  'queries': [{'hospital_id': k, 'quarter': TARGET_STAFFING_QUARTER, 'source_url': landing} for k in HOSPITALS]})


def acquire_cms_cost_reports():
    slug = 'w2-ops-cms-cost-report-2023'
    stamp = now()
    version = 'f08d4c46-c0e4-4bcb-a54a-c62c87d59251'
    landing = 'https://data.cms.gov/provider-compliance/cost-reports/hospital-provider-cost-report'
    base = f'https://data.cms.gov/data-api/v1/dataset/{version}/data'
    records, raw_paths, queries = [], [], []
    for ccn in ('310038', '310070'):
        params = {'filter[filter-1][condition][path]': 'Provider CCN',
                  'filter[filter-1][condition][operator]': '=',
                  'filter[filter-1][condition][value]': ccn, 'size': CMS_PAGE_LIMIT, 'offset': 0}
        url = base + '?' + urllib.parse.urlencode(params)
        rows = json.loads(get(url))
        if (not isinstance(rows, list) or not rows or len(rows) >= CMS_PAGE_LIMIT
                or any(r.get('Provider CCN') != ccn for r in rows)
                or any(not r.get('rpt_rec_num') for r in rows)):
            raise RuntimeError(f'CMS cost report returned unexpected records for CCN {ccn}')
        body = json.dumps(rows, ensure_ascii=False, indent=2).encode() + b'\n'
        path, digest = write_raw(f'cms-cost-report-2023-{ccn}.json', body)
        raw_paths.append(path)
        queries.append({'url': url, 'returned_count': len(rows), 'ccn': ccn})
        for row in rows:
            rid = f"{ccn}|{row.get('rpt_rec_num')}|{row.get('Fiscal Year Begin Date')}|{row.get('Fiscal Year End Date')}"
            records.append(envelope(slug, rid, 'AnnualHospitalCostReportObservation', row,
                                    url, stamp, path, digest,
                                    ['CMS cost reports are provider-reported annual financial/accounting and utilization records, not observed live operations.',
                                     'Fiscal periods can differ from calendar years; this acquired 2023 release is not a claim that all target reports cover the same interval.']))
    save_dataset(slug, 'CMS Hospital Provider Cost Report (2023 release; CCNs 310038 and 310070)', landing,
                 'All returned 2023-release report rows filtered by CMS Provider CCN for RWJUH New Brunswick (310038) and Saint Peter’s University Hospital (310070).',
                 {'basis': 'CMS public factual dataset', 'source_license': 'U.S. government data; CMS dataset API public access',
                  'redistribution': 'factual public rows retained with CMS attribution'},
                 ['Annual Medicare cost-report filings are retrospective and may have differing fiscal-year begin/end dates.',
                  'The same CCN may have multiple report records/statuses; inspect report IDs and status before selecting one.',
                  'Beds/FTE/utilization are reported fields, not current staffed capacity, available beds or hourly throughput.',
                  'Reported charges, expenses, costs and payment fields have distinct accounting meanings and do not establish patient liability.',
                  'CMS notes data are contractor-extracted from provider submissions; users must interpret fields with the CMS methodology and dictionary.'],
                 records, raw_paths, stamp,
                 {'upstream_dataset_id': version, 'upstream_modified': '2026-10-05',
                  'raw_artifact_kind': 'reformatted_api_response',
                  'data_period': {'start': '2023-01-01', 'end': '2023-12-31'},
                  'queries': queries})


if __name__ == '__main__':
    acquire_facilities()
    acquire_staffing()
    acquire_cms_cost_reports()
