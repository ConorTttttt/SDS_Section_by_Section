"""Re-run the regression set (Sections 10 and 4) and compare with the expected findings.

Usage:
  python3 -I tools/run_regression.py SDS_DIR [--live] [--section 10|4] [--write-expected]

SDS_DIR holds the supplier test SDSs named in regression/cases.json (not in the repo). Synthetic cases
("repo_file", regression/synthetic/) are in the repo and need no SDS_DIR.
Each file is checked against its recorded SHA-256 first.
By default the stored lookup snapshots in regression/lookups are used, so results are repeatable;
--live re-queries ICSC/NIOSH/CAMEO/PubChem instead (results can drift as those sources change).
--write-expected overwrites regression/expected/ with the current results. Use it only for an intended,
reviewed rule change, and commit it together with that change.

Exit code 0 = every case matches; 1 = at least one difference (printed).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(os.path.dirname(HERE), 'regression')
sys.path.insert(0, HERE)
import check_s10  # noqa: E402
import check_s4  # noqa: E402

CHECKERS = {'10': check_s10, '4': check_s4}


def summary(res):
    return sorted([{'check': f['check'], 'status': f['status'], 'section': f['section']}
                   for f in res['findings'] if 'GESTIS' not in f['check']], key=lambda x: (x['check'], x['status']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sds_dir')
    ap.add_argument('--live', action='store_true')
    ap.add_argument('--section', choices=sorted(CHECKERS))
    ap.add_argument('--write-expected', action='store_true')
    a = ap.parse_args()
    cases = json.load(open(os.path.join(REG, 'cases.json')))['cases']
    sections = [a.section] if a.section else ['10', '4']
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for c in cases:
            path = os.path.join(os.path.dirname(REG), c['repo_file']) if c.get('repo_file') else os.path.join(a.sds_dir, c['file'])
            print(f"== {c['id']}  ({c['declared']}, {c['type']})")
            if not os.path.exists(path):
                print('   MISSING FILE', path); failures += 1; continue
            if hashlib.sha256(open(path, 'rb').read()).hexdigest() != c['sha256']:
                print('   FILE CHANGED: SHA-256 differs from the regression record'); failures += 1; continue
            work = os.path.join(tmp, c['id'])
            subprocess.run([sys.executable, '-I', os.path.join(HERE, 'sds_text.py'), path, work], check=True, capture_output=True)
            sds = json.load(open(os.path.join(work, 'sds.json')))
            sds['_path'] = os.path.join(work, 'sds.json')
            lk_dir = os.path.join(REG, 'lookups')
            if a.live:
                lk_dir = os.path.join(work, 'lookups')
                subprocess.run([sys.executable, '-I', os.path.join(HERE, 'lookup.py'), lk_dir] + sds['codes_all']['CAS'],
                               check=True, capture_output=True)
            for sec in sections:
                res = CHECKERS[sec].run(sds, lk_dir, c['declared'], c['type'])
                got = summary(res)
                exp_path = os.path.join(REG, 'expected', f'section{sec}', c['id'] + '.json')
                if a.write_expected:
                    os.makedirs(os.path.dirname(exp_path), exist_ok=True)
                    json.dump({'case': c['id'], 'section': sec,
                               'jurisdiction': {k: res['jurisdiction'][k] for k in ('declared', 'detected', 'mismatch')},
                               'findings': got}, open(exp_path, 'w'), indent=1, ensure_ascii=False)
                    print(f'   S{sec}: expected written ({len(got)} findings)')
                    continue
                if not os.path.exists(exp_path):
                    print(f'   S{sec}: no expected file'); failures += 1; continue
                exp_doc = json.load(open(exp_path))
                g = {(f['check'], f['status']) for f in got}
                e = {(f['check'], f['status']) for f in exp_doc['findings']}
                j_ok = (res['jurisdiction']['detected'] == exp_doc['jurisdiction']['detected']
                        and res['jurisdiction']['mismatch'] == exp_doc['jurisdiction']['mismatch'])
                if g != e or not j_ok:
                    failures += 1
                    print(f'   S{sec}: DIFFERS')
                    if not j_ok:
                        print(f"      jurisdiction: expected {exp_doc['jurisdiction']}, got {res['jurisdiction']}")
                    for x in sorted(e - g):
                        print('      missing :', x)
                    for x in sorted(g - e):
                        print('      new     :', x)
                else:
                    print(f"   S{sec}: OK ({len(got)} findings; jurisdiction {res['jurisdiction']['detected']}"
                          + (', mismatch flagged' if res['jurisdiction']['mismatch'] else '') + ')')
    if not a.write_expected:
        print('\nALL CASES MATCH' if not failures else f'\n{failures} CHECK(S) DIFFER')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
