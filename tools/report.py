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
import check_s10, check_s4, check_s567, coverage  # noqa: E401,E402

SECTIONS = [('10', check_s10.run), ('4', check_s4.run), ('5', check_s567.runner('5')), ('6', check_s567.runner('6')), ('7', check_s567.runner('7'))]


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
    s1 = ' '.join(sds['sections'].get('1', {}).get('text', '').split())
    full = open(os.path.join(a.out_dir, 'sds.txt'), encoding='utf-8').read()
    name = re.search(r'(?:product name|product description|trade name)\s*:?\s*(.{2,80}?)(?:\s{2,}|cat no|cas|synonym|$)', s1, re.I)
    rev = re.search(r'revision date\s*:?\s*([0-9A-Za-z./ -]{6,20}?\d{2,4})', full, re.I)
    results = [(sec, fn(sds, lk, a.declared, a.type)) for sec, fn in SECTIONS]
    j = results[0][1]['jurisdiction']
    L = ['# SDS review: Sections 10, 4, 5, 6, 7', '',
         '**Review aid only: a competent person must verify every finding before any change is made to the SDS.**', '',
         f"- Product: {name.group(1).strip() if name else 'not found'}",
         f"- Revision date: {rev.group(1).strip() if rev else 'not found'}",
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
