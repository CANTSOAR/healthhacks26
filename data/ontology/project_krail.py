#!/usr/bin/env python3
"""Generate KRAIL's simple class/property projection; rich constraints stay in JSON."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def projection():
    v = json.loads((ROOT / 'vocabulary.json').read_text())
    native = {'uri': 'https://github.com/CANTSOAR/healthhacks26/ontology/hospital/0.1',
              'classes': [], 'data_properties': [], 'object_properties': []}
    mapping = []
    for entity in v['entities']:
        name = entity['id']
        native['classes'].append({'name': name, 'description': entity['definition']})
        for field in entity['attributes']:
            # Native property range is primitive. Structured values are JSON text in this projection.
            primitive = {'number': 'decimal', 'integer': 'integer', 'datetime': 'datetime'}.get(field['type'], 'string')
            native['data_properties'].append({'name': name + '__' + field['name'], 'domain': name, 'range': primitive})
    for relation in v['relationships']:
        for domain in relation['domain']:
            for target in relation['range']:
                name = relation['id'] + '__' + domain + '__' + target
                native['object_properties'].append({'name': name, 'domain': domain, 'range': target})
                mapping.append({'native_name': name, 'relation_type': relation['id'], 'domain': domain, 'range': target})
    return native, mapping

if __name__ == '__main__':
    native, mapping = projection()
    # JSON is a valid YAML 1.2 document; no YAML dependency is needed.
    target = ROOT.parent / '.ontology' / 'ontology.yaml'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(native, indent=2) + '\n')
    (ROOT / 'krail-projection-map.json').write_text(json.dumps(mapping, indent=2) + '\n')
    print(f'Projected {len(native["classes"])} classes and {len(native["object_properties"])} typed edges to {target}')
