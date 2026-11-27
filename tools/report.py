"""Full review report for one SDS: Sections 10, 4, 5, 6 and 7.

Usage: python3 -I tools/report.py SDS_FILE OUT_DIR --declared EU|GB|US --type substance|mixture [--live]
Writes OUT_DIR/report.md. Every report ends with the "Not run" list: a row that did not run is not a pass.
Suggested corrections are drafted by the reviewer from the findings; they are not generated here.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_s10, check_s4, check_s567, coverage, refgate  # noqa: E401,E402

SECTIONS = [('10', check_s10.run), ('4', check_s4.run), ('5', check_s567.runner('5')), ('6', check_s567.runner('6')), ('7', check_s567.runner('7'))]


def product_name(s1):
    """Product name from Section 1: a 'Product name'/'Trade name' field first, then 'Product identifier'."""
    lines = [ln.strip() for ln in s1.split('\n')]
    for label in (r'product name|trade name|commercial name', r'product identifier|product description'):
        for i, ln in enumerate(lines):
            m = re.match(r'(?i)(?:1\.1\.?\s*)?(?:' + label + r')\b\s*[:.]?\s*(.*)$', ln)
            if m:
                val = m.group(1).strip()
                if not val or re.fullmatch(r'[\d\W]{1,12}', val):   # value on the next line, or only a code ("2565")
                    nxt = next((x for x in lines[i + 1:i + 4] if x and not re.match(r'(?i)(?:1\.\d|product (?:number|code)|ufi|cas|substance|synonym)', x)), '')
                    if nxt and not re.match(r'(?i)product (?:name|identifier)', nxt):
                        val = nxt if not val else val
                val = re.split(r'\s{2,}(?=[A-Z][a-z]+\s*:)|\s+(?:cat\.? no|cas|synonyms?|product (?:number|code))\b', val, flags=re.I)[0].strip(' :')
                if len(val) >= 2:
                    return val[:80]
    return None


def revision_date(full):
    for label, kind in ((r'revision date|date of revision|revised(?: on)?', ''), (r'date of issue|issue date', ' (date of issue)'),
                        (r'preparation date|date of preparation|date prepared|creation date', ' (preparation date; no revision date given)')):
        m = re.search(r'(?i)(?:' + label + r')\s*[:/]?\s*(?:date of revision\s*:?\s*)?(\d{1,2}(?:st|nd|rd|th)?[\s./-]+[A-Za-z0-9]+[\s./-]+\d{2,4}|\d{4}-\d{2}-\d{2})', full)
        if m:
            return m.group(1).strip() + kind
    return None


def coverage_warnings(sds, lk_dir, sds_type):
    """Main ingredients (>= 10 %) with no ICSC/CAMEO/NIOSH record: the reference-data checks did not cover them."""
    gate = refgate.Gate(sds, set(), sds_type)
    out = []
    for cas in sds['codes_by_section'].get('3', {}).get('CAS', []) or sds['codes_all']['CAS']:
        if cas == '7732-18-5' or gate.band(cas) != 'major':
            continue
        p = os.path.join(lk_dir, f'lookup_{cas}.json')
        d = json.load(open(p)) if os.path.exists(p) else {}
        if not refgate.has_reference_data(d):
            out.append(f'no ICSC, CAMEO or NIOSH record for main ingredient {gate.describe(cas)}: '
                       'the reference-data checks (D rows) did not cover it; check it manually (e.g. GESTIS, ECHA registration dossier)')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sds'); ap.add_argument('out_dir')
    ap.add_argument('--declared', choices=['EU', 'GB', 'US'], required=True)
    ap.add_argument('--type', choices=['substance', 'mixture'], required=True)
    ap.add_argument('--lookups', help='folder of lookup_<CAS>.json (default: run lookup.py into OUT_DIR)')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'sds_text.py'), a.sds, a.out_dir], check=True, capture_output=True)
    sds = json.load(open(os.path.join(a.out_dir, 'sds.json'))); sds['_path'] = os.path.join(a.out_dir, 'sds.json')
    cas = [c for c in sds['codes_all']['CAS']]
    lk = a.lookups or a.out_dir
    if not a.lookups and cas:
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'lookup.py'), a.out_dir] + cas, check=False, capture_output=True)
    have = any(os.path.exists(os.path.join(lk, f'lookup_{c}.json')) for c in cas if c != '7732-18-5')
    full = open(os.path.join(a.out_dir, 'sds.txt'), encoding='utf-8').read()
    name = product_name(sds.get('sections', {}).get('1', {}).get('text', ''))
    rev = revision_date(full)
    results = [(sec, fn(sds, lk, a.declared, a.type)) for sec, fn in SECTIONS]
    cover = coverage_warnings(sds, lk, a.type)
    gating = []
    for _, res in results:
        for n in res.get('gating', []):
            if n not in gating:
                gating.append(n)
    j = results[0][1]['jurisdiction']
    L = ['# SDS review: Sections 10, 4, 5, 6, 7', '',
         '**Review aid only: a competent person must verify every finding before any change is made to the SDS.**', '',
         f"- Product: {name or 'not found'}",
         f"- Revision date: {rev or 'not found'}",
         f"- Jurisdiction: declared {a.declared}; detected {j['detected']}" + (' (MISMATCH: checks run as declared)' if j['mismatch'] else ''),
         f'- SDS type: {a.type}', '', '## Summary', '', '| Section | Fail | Warning | Info | Not run |', '|---|---|---|---|---|']
    for sec, res in results:
        c = {k: sum(1 for f in res['findings'] if f['status'] == k) for k in ('fail', 'warning', 'info')}
        L.append(f"| {sec} | {c['fail']} | {c['warning']} | {c['info']} | {len(coverage.not_run(sec, a.declared, a.type, have))} |")
    L += ['', '## Findings', '', '| Section | Check | Status | SDS says | Expected | Source |', '|---|---|---|---|---|---|']
    for sec, res in results:
        for f in res['findings']:
            cell = lambda x: (x or '').replace('|', '/').replace('\n', ' ')[:200]
            L.append(f"| {cell(f['section'])} | {f['check']} | {f['status']} | {cell(f['sds_says'])} | {cell(f['expected'])} | {cell(f['source'])} |")
    L += ['', '## Reference data coverage', '']
    L += ([f'- **Warning:** {c}' for c in cover] or ['- Every main ingredient (≥ 10 %) has at least one reference record (ICSC, CAMEO or NIOSH).'])
    if a.type == 'mixture':
        L.append('- Limit and reference-data checks cover only the ingredients listed in Section 3; ingredients a mixture SDS may '
                 'legitimately leave out were not checked.')
    if gating:
        L += ['', 'Reference data not applied or capped (concentration and physical-form rules, config/reference_gating.json):', '']
        L += [f'- {g}' for g in gating]
    L += ['', '## Suggested corrections', '', 'Draft replacement wording is written by the reviewer from the findings above and marked as draft text for a competent person to review.', '',
          '## Not run', '', 'These Checklist rows did not run on this SDS. No finding for them is not a pass.', '']
    for sec, _ in results:
        nr = coverage.not_run(sec, a.declared, a.type, have)
        L.append(f'**Section {sec}** ({len(nr)}): ' + ('; '.join(f"{r['check']} ({r['why']})" for r in nr) if nr else 'none'))
        L.append('')
    open(os.path.join(a.out_dir, 'report.md'), 'w', encoding='utf-8').write('\n'.join(L))
    print(os.path.join(a.out_dir, 'report.md'))


if __name__ == '__main__':
    main()
