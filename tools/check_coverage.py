"""CI coverage check: Checklist rows marked "coded" must match the check IDs the engines implement.

Fails (exit 1) when:
  - a row is "coded" in checklist/coverage.csv but no engine declares it;
  - an engine declares an ID that the CSV marks manual / not yet coded, or that is missing from the CSV;
  - a declared ID never appears in its engine's source (so the registry cannot claim code that does not exist).
Usage: python3 -I tools/check_coverage.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_s10  # noqa: E402
import check_s4  # noqa: E402
import check_s567  # noqa: E402
import coverage  # noqa: E402
import dedupe  # noqa: E402

ENGINES = {'check_s10.py': check_s10.CODED, 'check_s4.py': check_s4.CODED, 'check_s567.py': check_s567.CODED, 'dedupe.py': dedupe.CODED}


def main():
    rows = {r['check_id']: r for r in coverage.load()}
    declared = set().union(*ENGINES.values())
    problems = []
    for cid, r in sorted(rows.items()):
        if r['status'] == 'coded' and cid not in declared:
            problems.append(f'{cid}: marked coded in the Checklist but no engine implements it')
        if r['status'] != 'coded' and cid in declared:
            problems.append(f"{cid}: implemented by an engine but marked '{r['status']}' in the Checklist")
    for cid in sorted(declared - set(rows)):
        problems.append(f'{cid}: implemented by an engine but missing from the Checklist')
    for fname, ids in ENGINES.items():
        src = open(os.path.join(HERE, fname), encoding='utf-8').read()
        for cid in sorted(ids):
            dynamic = fname == 'check_s567.py' and re.fullmatch(r'[567]-A[123]', cid)
            literal = f"'{cid}'" in src or (cid == 'X-R1' and 'def dedupe' in src)
            if not (literal or dynamic):
                problems.append(f'{cid}: declared in {fname} but never emitted there')
    total = len(rows)
    coded = sum(1 for r in rows.values() if r['status'] == 'coded')
    by = {}
    for cid, r in rows.items():
        sec = coverage.section_of(cid)
        by.setdefault(sec, [0, 0])
        by[sec][1] += 1
        by[sec][0] += r['status'] == 'coded'
    print('Coverage by section (coded / total):', ', '.join(f'{k}: {v[0]}/{v[1]}' for k, v in sorted(by.items())))
    print(f'All rows: {coded}/{total} coded')
    if problems:
        print('\nCOVERAGE MISMATCH:')
        for p in problems:
            print('  ' + p)
        sys.exit(1)
    print('Checklist status and engine registries agree.')


if __name__ == '__main__':
    main()
