"""Checklist coverage: which rows ran, and which did not (and why).

checklist/coverage.csv mirrors the Status column of the Checklist tab in the Sheet:
  check_id, jurisdictions (EU,GB,US), sds_types (substance,mixture), status (coded | manual | not yet coded), reason
Every report ends with not_run(): a row that did not run is never reported as passed.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, 'checklist', 'coverage.csv')


def load():
    with open(CSV, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def section_of(check_id):
    head = check_id.split('-')[0]
    return head if head != 'X' else 'all'


def owners(section):
    """Rows whose results are reported under this section's run (linked rows count where they are computed)."""
    s10 = {'5-C1', '5-C2', '6-C1', '7-C1', '10-J1'}
    rows = load()
    if section == '10':
        return [r for r in rows if r['check_id'].startswith('10-') or r['check_id'] in s10]
    if section == '4':
        return [r for r in rows if r['check_id'].startswith(('4-', '2-L'))]
    return [r for r in rows if r['check_id'].startswith(section + '-') and r['check_id'] not in s10]


def not_run(section, jurisdiction, sds_type, have_reference_data=True):
    """List of {'check', 'why'} for rows of this section that did not run on this SDS."""
    out = []
    for r in owners(section):
        cid = r['check_id']
        if r['status'] == 'manual':
            out.append({'check': cid, 'why': 'manual: ' + r['reason']})
        elif r['status'] != 'coded':
            out.append({'check': cid, 'why': 'not yet coded' + (': ' + r['reason'] if r['reason'] and r['reason'] != 'not yet coded' else '')})
        elif jurisdiction and jurisdiction not in r['jurisdictions'].split(','):
            out.append({'check': cid, 'why': f"not applicable: {r['jurisdictions']} only"})
        elif sds_type and sds_type not in r['sds_types'].split(','):
            out.append({'check': cid, 'why': f"not applicable: {r['sds_types']} SDSs only"})
        elif not have_reference_data and '-D' in cid:
            out.append({'check': cid, 'why': 'no reference data (no lookup found for any CAS in Section 3)'})
    return out


def print_not_run(section, jurisdiction, sds_type, have_reference_data=True):
    rows = not_run(section, jurisdiction, sds_type, have_reference_data)
    print(f'  Not run ({len(rows)}): no finding is not the same as passed')
    for r in rows:
        print(f"    {r['check']:<8} {r['why']}")
