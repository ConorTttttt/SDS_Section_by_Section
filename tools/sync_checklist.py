"""Sync the Checklist Status from the Sheet (the master copy) into checklist/coverage.csv.

The Sheet "SDS Resources by Section (Sections 4-8)", tab Checklist, is the master copy. This script never
edits the Sheet. The Sheet is reachable only through the Claude Docs connector, not from Python, so a sync
has two steps:

  1. Claude reads the Checklist tab with the connector: columns B (Check ID) and F:G (Applies to, Status),
     rows 1 to the last filled row, at the same Sheet revision.
  2. python3 -I tools/sync_checklist.py --from-transcript
     finds the latest two such read results in this session's transcript, writes them to
     checklist/sheet_export.json (the raw cells, with the Sheet revision and the date read) and rewrites
     checklist/coverage.csv from them.

  python3 -I tools/sync_checklist.py            rebuild coverage.csv from the committed sheet_export.json
  python3 -I tools/sync_checklist.py --check    CI: fail if coverage.csv differs from sheet_export.json

Parsing rules (anything else is an error, so a typo in the Sheet stops the sync instead of being guessed):
  Applies to: "EU, GB, US · substance, mixture". Jurisdictions are the EU/GB/US tokens before "·", ignoring
              any bracketed note; none named (e.g. "Any SDS with NFPA ratings") means all three. SDS types
              come after "·"; no "·" means both.
  Status:     "coded", "not yet coded", "manual: <reason>" or "not yet coded: <reason>".
"""
import argparse
import csv
import datetime
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(ROOT, 'checklist', 'sheet_export.json')
CSV = os.path.join(ROOT, 'checklist', 'coverage.csv')
SHEET_URL = 'https://claude.ai/artifact/YU3qDgtuqh4mMq5BxX3wHd'
ID_RE = re.compile(r'^(?:\d{1,2}|X)-[A-Z]+\d+$')


def from_transcript():
    """Latest Checklist reads of column B and columns F:G from Claude Docs read calls in this session."""
    files = sorted(glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')), key=os.path.getmtime)
    if not files:
        sys.exit('No session transcript found.')
    reads = set()
    found = {}
    for line in open(files[-1], encoding='utf-8'):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        content = d.get('message', {}).get('content')
        if not isinstance(content, list):
            continue
        for c in content:
            if c.get('type') == 'tool_use' and c.get('name') == 'mcp__Claude_Docs__read':
                reads.add(c['id'])
            if c.get('type') == 'tool_result' and c.get('tool_use_id') in reads:
                parts = c['content'] if isinstance(c['content'], list) else [{'text': c['content']}]
                for p in parts:
                    try:
                        v = json.loads(p.get('text', ''))['value']
                    except (ValueError, KeyError, TypeError):
                        continue
                    if v.get('sheet') != 'Checklist':
                        continue
                    rng = v.get('range', '')
                    if re.fullmatch(r'B1:B\d+', rng):
                        found['B'] = v
                    elif re.fullmatch(r'F1:G\d+', rng):
                        found['FG'] = v
    if set(found) != {'B', 'FG'}:
        sys.exit('Read the Checklist tab first: ranges B1:B<last row> and F1:G<last row> (missing: '
                 + ', '.join(sorted({'B', 'FG'} - set(found))) + ').')
    if found['B']['revision'] != found['FG']['revision']:
        sys.exit(f"The two reads are from different Sheet revisions ({found['B']['revision']} and "
                 f"{found['FG']['revision']}); read both again.")
    return {'source': SHEET_URL, 'sheet': 'Checklist', 'revision': found['B']['revision'],
            'read_on': datetime.date.today().isoformat(),
            'columns': {'B': found['B']['rows'], 'F:G': found['FG']['rows']}}


def parse_applies(text, cid):
    left, _, right = text.partition('·')
    left = re.sub(r'\(.*?\)', '', left)
    jur = [j for j in ('EU', 'GB', 'US') if re.search(rf'\b{j}\b', left)] or ['EU', 'GB', 'US']
    if right:
        types = [t for t in ('substance', 'mixture') if t in right.lower()]
        if not types:
            raise ValueError(f'{cid}: cannot read the SDS type in "Applies to": {text!r}')
    else:
        types = ['substance', 'mixture']
    return ','.join(jur), ','.join(types)


def parse_status(text, cid):
    t = (text or '').strip()
    m = re.fullmatch(r'(coded|manual|not yet coded)\s*(?::\s*(.+))?', t, re.I | re.S)
    if not m or (m.group(1).lower() == 'coded' and m.group(2)):
        raise ValueError(f'{cid}: Status must be "coded", "manual: <reason>" or "not yet coded"; found {t!r}')
    status, reason = m.group(1).lower(), (m.group(2) or '').strip()
    if status == 'manual' and not reason:
        raise ValueError(f'{cid}: a manual row needs a reason ("manual: <reason>")')
    return status, reason


def build_csv(export):
    ids, fg = export['columns']['B'], export['columns']['F:G']
    if ids.get('1', [''])[0] != 'Check ID' or fg.get('1') != ['Applies to', 'Status']:
        raise ValueError('Unexpected header row: the Checklist columns have moved (expected B = Check ID, '
                         'F = Applies to, G = Status).')
    out, seen, errors = io.StringIO(newline=''), set(), []
    w = csv.writer(out, lineterminator='\r\n')
    w.writerow(['check_id', 'jurisdictions', 'sds_types', 'status', 'reason'])
    for row in sorted((int(k) for k in ids if k != '1')):
        cid = (ids[str(row)] or [''])[0].strip()
        if not cid:
            continue
        try:
            if not ID_RE.match(cid):
                raise ValueError(f'row {row}: not a check ID: {cid!r}')
            if cid in seen:
                raise ValueError(f'row {row}: duplicate check ID {cid}')
            seen.add(cid)
            applies, status = (fg.get(str(row)) or ['', ''])[:2]
            jur, types = parse_applies(applies or '', cid)
            st, reason = parse_status(status, cid)
            w.writerow([cid, jur, types, st, reason])
        except ValueError as e:
            errors.append(str(e))
    if errors:
        raise ValueError('\n'.join(errors))
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-transcript', action='store_true', help='take the Sheet reads from this session')
    ap.add_argument('--check', action='store_true', help='fail if coverage.csv is not what the export gives')
    a = ap.parse_args()
    if a.from_transcript:
        export = from_transcript()
        try:
            text = build_csv(export)
        except ValueError as e:
            sys.exit('Sheet not synced; fix these in the Checklist tab:\n' + str(e))
        old = open(EXPORT, encoding='utf-8').read() if os.path.exists(EXPORT) else ''
        json.dump(export, open(EXPORT, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print(f"Read Sheet revision {export['revision']} on {export['read_on']}"
              + (' (export unchanged apart from the date)' if old and json.loads(old)['columns'] == export['columns'] else ''))
    else:
        export = json.load(open(EXPORT, encoding='utf-8'))
        try:
            text = build_csv(export)
        except ValueError as e:
            sys.exit('checklist/sheet_export.json has rows this script cannot read; fix them in the Checklist '
                     'tab and sync again:\n' + str(e))
    current = open(CSV, encoding='utf-8', newline='').read() if os.path.exists(CSV) else ''
    if a.check:
        if current != text:
            print('coverage.csv does not match checklist/sheet_export.json (Sheet revision '
                  f"{export['revision']}). Run python3 -I tools/sync_checklist.py and commit the result.")
            old_rows = set(current.splitlines()); new_rows = set(text.splitlines())
            for r in sorted(new_rows - old_rows):
                print('  Sheet  :', r)
            for r in sorted(old_rows - new_rows):
                print('  CSV    :', r)
            sys.exit(1)
        print(f"coverage.csv matches the Sheet export (revision {export['revision']}, read {export['read_on']}).")
        return
    if current == text:
        print('coverage.csv already up to date.')
    else:
        open(CSV, 'w', encoding='utf-8', newline='').write(text)
        print(f'coverage.csv rewritten ({text.count(chr(10)) - 1} rows).')


if __name__ == '__main__':
    main()
