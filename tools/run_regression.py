"""Re-run the Section 10 regression set and compare with the expected findings.

Usage:
  python3 -I tools/run_regression.py SDS_DIR [--live]

SDS_DIR holds the test SDS files named in regression/section10/cases.json. They are not in the repo
(supplier documents); each file is checked against its recorded SHA-256 first.
By default the stored lookup snapshots in regression/section10/lookups are used, so results are repeatable.
--live re-queries ICSC/NIOSH/CAMEO/PubChem instead (results can drift as those sources change).

Exit code 0 = every case matches; 1 = at least one difference (printed).
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REG = os.path.join(ROOT, 'regression', 'section10')
sys.path.insert(0, HERE)
import check_s10  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sds_dir, live = sys.argv[1], '--live' in sys.argv
    cases = json.load(open(os.path.join(REG, 'cases.json')))['cases']
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for c in cases:
            path = os.path.join(sds_dir, c['file'])
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
            if live:
                lk_dir = os.path.join(work, 'lookups')
                subprocess.run([sys.executable, '-I', os.path.join(HERE, 'lookup.py'), lk_dir] + sds['codes_all']['CAS'], check=True, capture_output=True)
            res = check_s10.run(sds, lk_dir, c['declared'], c['type'])
            got = sorted([(f['check'], f['status']) for f in res['findings'] if 'GESTIS' not in f['check']])
            exp_doc = json.load(open(os.path.join(REG, 'expected', c['id'] + '.json')))
            exp = sorted([(f['check'], f['status']) for f in exp_doc['findings']])
            j_ok = (res['jurisdiction']['detected'] == exp_doc['jurisdiction']['detected']
                    and res['jurisdiction']['mismatch'] == exp_doc['jurisdiction']['mismatch'])
            extra, missing = sorted(set(got) - set(exp)), sorted(set(exp) - set(got))
            if extra or missing or not j_ok:
                failures += 1
                if not j_ok:
                    print(f"   jurisdiction: expected {exp_doc['jurisdiction']}, got {res['jurisdiction']}")
                for x in missing:
                    print('   missing :', x)
                for x in extra:
                    print('   new     :', x)
            else:
                print(f"   OK ({len(got)} findings; jurisdiction {res['jurisdiction']['detected']}"
                      + (', mismatch flagged' if res['jurisdiction']['mismatch'] else '') + ')')
    print('\nALL CASES MATCH' if not failures else f'\n{failures} CASE(S) DIFFER')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
