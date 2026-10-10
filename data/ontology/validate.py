#!/usr/bin/env python3
"""Validate ontology structure, synthetic graph, and optional acquisition envelopes.
No clinical, rights, calibration, or reviewer approval is conferred by this check.
"""
import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent

def read(name):
    return json.loads((ROOT / name).read_text())

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def fail(condition, message):
    if not condition:
        raise ValueError(message)

def timestamp(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))

def collect_refs(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith('_ref') and isinstance(child, str):
                yield child
            elif key.endswith('_refs') or key == 'caused_by':
                if isinstance(child, list):
                    yield from (x for x in child if isinstance(x, str))
            else:
                yield from collect_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from collect_refs(child)

def acyclic(edges, name):
    seen, active = set(), set()
    def visit(node):
        fail(node not in active, f'{name}: cycle at {node}')
        if node in seen:
            return
        active.add(node)
        for target in edges.get(node, []):
            visit(target)
        active.remove(node)
        seen.add(node)
    for node in edges:
        visit(node)

def validate_entities(entities, relationships):
    schema = Draft202012Validator(read('schemas/entity.schema.json'), format_checker=FormatChecker())
    rschema = Draft202012Validator(read('schemas/relationship.schema.json'), format_checker=FormatChecker())
    ids = {e['id']: e for e in entities}
    fail(len(ids) == len(entities), 'Duplicate entity identifier in version snapshot')
    relation_defs = {r['id']:r for r in read('vocabulary.json')['relationships']}
    parents, causes = {}, {}
    allocations = {}
    for e in entities:
        schema.validate(e)
        key, kind, a = e['id'], e['entity_type'], e['attributes']
        fail(bool(e['source_refs']), f'{key}: source lineage required')
        for reference in collect_refs(e):
            fail(reference in ids, f'{key}: dangling reference {reference}')
        for sr in e['source_refs']:
            fail(ids[sr]['entity_type'] == 'SourceRecord', f'{key}: source_refs must identify source records')
        interval = e.get('valid_time', {})
        if interval.get('start') and interval.get('end'):
            fail(timestamp(interval['start']) <= timestamp(interval['end']), f'{key}: reversed valid interval')
        for start, end in [('start_at','end_at'),('entered_at','exited_at'),('requested_at','decision_at')]:
            if a.get(start) and a.get(end):
                fail(timestamp(a[start]) <= timestamp(a[end]), f'{key}: reversed {start}/{end}')
        if kind == 'PhysicalLocation' and a.get('parent_ref'):
            parent = ids[a['parent_ref']]
            fail(parent['entity_type'] == 'PhysicalLocation', f'{key}: physical parent has wrong type')
            fail(parent['attributes']['facility_ref'] == a['facility_ref'], f'{key}: cross-facility containment requires separate relationship')
            parents[key] = [a['parent_ref']]
        if kind == 'Event':
            # Recorded time may precede reported occurrence for schedules; never silently rewrite either.
            causes[key] = a['caused_by']
            for c in a['caused_by']:
                fail(ids[c]['entity_type'] == 'Event', f'{key}: causal predecessor must be event')
                fail(timestamp(ids[c]['attributes']['occurred_at']) <= timestamp(a['occurred_at']), f'{key}: cause follows effect')
        if kind == 'Assertion':
            obj = a['object']
            object_keys = {'entity_ref','literal','quantity','coding','unknown_reason'}.intersection(obj)
            fail(len(object_keys) == 1, f'{key}: assertion object requires exactly one representation')
            if a['finding_state'] in {'unknown','pending','explicitly_absent'}:
                fail('quantity' not in obj, f'{key}: unavailable/absent finding cannot contain measured quantity')
        if kind == 'Observation' and a['finding_state'] in {'unknown','pending','explicitly_absent'}:
            fail('value' not in a['value'], f'{key}: unavailable observation must not contain measured value')
        if kind == 'CapacitySnapshot':
            fail(a['count'] >= 0, f'{key}: capacity count negative')
        if kind == 'InventoryLot':
            fail(a['quantity'] >= 0, f'{key}: stock negative')
        if kind == 'Shift':
            fail(0 <= a['availability_fraction'] <= 1, f'{key}: availability out of bounds')
        if kind == 'IdentityMapping' and 'confidence' in a:
            fail(0 <= a['confidence'] <= 1, f'{key}: confidence out of bounds')
        if kind == 'ResourceAllocation':
            fail(a['quantity'] > 0, f'{key}: allocation quantity must be positive')
            if a['allocation_kind'] == 'active':
                allocations.setdefault(a['resource_ref'], []).append(e)
        if kind == 'QueueEntry' and a['censoring'] == 'none':
            fail('exited_at' in a, f'{key}: complete queue interval needs exit')
        if kind == 'FinancialAmount':
            fail(len(a['currency']) == 3 and a['currency'].isupper(), f'{key}: expected ISO currency code')
        if kind == 'ReviewDecision':
            target = ids[a['target_ref']]
            fail(target['version'] == a['target_version'], f'{key}: review version mismatch')
        if e['review_status'] == 'approved':
            approvals = [r for r in entities if r['entity_type']=='ReviewDecision' and r['attributes']['target_ref']==key and r['attributes']['target_version']==e['version'] and r['attributes']['decision']=='approve']
            fail(bool(approvals), f'{key}: approved label without exact-version review decision')
    acyclic(parents, 'Physical containment')
    acyclic(causes, 'Event causality')
    for resource, assignments in allocations.items():
        # This fixture validator treats individually tracked beds as exclusive. Pooled capacities need engine accounting.
        if ids[resource]['entity_type'] != 'Resource' or ids[resource]['attributes']['resource_kind'] != 'bed':
            continue
        for i, left in enumerate(assignments):
            for right in assignments[i+1:]:
                l, r = left['attributes'], right['attributes']
                lend = timestamp(l['end_at']) if l.get('end_at') else datetime.max.replace(tzinfo=timestamp(l['start_at']).tzinfo)
                rend = timestamp(r['end_at']) if r.get('end_at') else datetime.max.replace(tzinfo=timestamp(r['start_at']).tzinfo)
                fail(not (timestamp(l['start_at']) < rend and timestamp(r['start_at']) < lend), f'{resource}: overlapping bed allocations')
    rel_ids = set()
    for edge in relationships:
        rschema.validate(edge)
        fail(edge['id'] not in rel_ids, 'Duplicate relationship ID')
        rel_ids.add(edge['id'])
        for reference in collect_refs(edge):
            fail(reference in ids, f'Dangling edge reference {reference}')
        d = relation_defs[edge['relation_type']]
        fail(ids[edge['subject_ref']]['entity_type'] in d['domain'], f'{edge["id"]}: incorrect domain')
        fail(ids[edge['object_ref']]['entity_type'] in d['range'], f'{edge["id"]}: incorrect range')

def negative_checks(entities, edges):
    tests = [
        ('unknown becomes numeric', 'example:unknown', lambda x: x['attributes'].update(object={'quantity':{'value':0,'unit':'mg'}})),
        ('invalid shift interval', 'example:shift', lambda x: x['attributes'].update(end_at='2026-10-10T11:00:00Z')),
        ('false approval label', 'example:case', lambda x: x.update(review_status='approved')),
        ('unresolvable reference', 'example:encounter', lambda x: x['attributes'].update(patient_ref='missing:patient')),
        ('capacity negative', 'example:capacity', lambda x: x['attributes'].update(count=-1)),
        ('causal ordering reversed', 'example:assessment_start', lambda x: x['attributes'].update(occurred_at='2026-10-10T11:00:00Z')),
        ('wrong review version', 'example:review', lambda x: x['attributes'].update(target_version='0.0.0')),
    ]
    for label, target, mutate in tests:
        bad = copy.deepcopy(entities)
        mutate(next(x for x in bad if x['id']==target))
        try:
            validate_entities(bad, edges)
        except Exception as error:
            # Only schema/semantic failures count; programming errors must not be swallowed.
            from jsonschema.exceptions import ValidationError
            if not isinstance(error, (ValueError, ValidationError)):
                raise
        else:
            raise ValueError(f'Negative test accepted: {label}')
    bad = copy.deepcopy(entities)
    duplicate = copy.deepcopy(next(x for x in bad if x['id']=='example:allocation'))
    duplicate['id']='example:allocation-overlap'
    bad.append(duplicate)
    try:
        validate_entities(bad, edges)
    except ValueError:
        pass
    else:
        raise ValueError('Negative test accepted: bed double booking')
    return len(tests)+1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--normalized-dir', type=Path, help='Also check JSONL acquisition envelopes, without graph promotion')
    args = parser.parse_args()
    v = read('vocabulary.json')
    names = [e['id'] for e in v['entities']]
    fail(len(names)==len(set(names)), 'Duplicate vocabulary entity')
    for e in v['entities']:
        fail(e['context'] in v['contexts'], 'Unknown bounded context')
        attrs = [a['name'] for a in e['attributes']]
        fail(len(attrs)==len(set(attrs)), 'Duplicate attribute')
    for r in v['relationships']:
        fail(set(r['domain']+r['range']) <= set(names), 'Unknown relationship endpoint type')
    for path in (ROOT/'schemas').glob('*.json'):
        Draft202012Validator.check_schema(json.loads(path.read_text()))
    from project_krail import projection
    native, mapping = projection()
    fail(native == json.loads((ROOT.parent/'.ontology/ontology.yaml').read_text()), 'KRAIL projection is stale; run project_krail.py')
    fail(mapping == read('krail-projection-map.json'), 'Projection mapping is stale')
    entities = rows(ROOT/'examples/synthetic-journey.jsonl')
    edges = rows(ROOT/'examples/synthetic-relationships.jsonl')
    validate_entities(entities, edges)
    nnegative = negative_checks(entities, edges)
    count=0
    if args.normalized_dir:
        validator = Draft202012Validator(read('schemas/normalized-record.schema.json'), format_checker=FormatChecker())
        seen = set()
        for path in sorted(args.normalized_dir.glob('*.jsonl')):
            for number, row in enumerate(rows(path), 1):
                try:
                    validator.validate(row)
                    fail(row['record_id'] not in seen, f'Duplicate record_id {row["record_id"]}')
                    seen.add(row['record_id'])
                except Exception as e:
                    raise ValueError(f'{path}:{number}: {e}') from e
                count += 1
    print(f'PASS: {len(names)} entity types, {len(v["relationships"])} relationship types, {len(entities)} synthetic entities, {len(edges)} edges, {nnegative} rejected invalid fixtures; {count} acquisition envelopes checked.')
    print('Structural checks only. Full cardinality, authority, clinical validity, rights, and simulation conservation require their own scoped validators/review.')

if __name__ == '__main__':
    main()
