"""Verify the Classification calculator's P-statement selection against CLP Annex IV / Annex I (read-only).

  python3 -I tools/verify_p_calculator.py --engine ../Classification/verification/engine.js \
      [--cases regression/cases.json --sds-dir DIR] [--cases local/blind_test/cases.json] --out OUT_DIR

Expected statements are derived only from the bundled legal tables in data/legal/ (built by tools/legal_tables.py):
- Annex IV Part 1 rows (the selection criteria, Art. 22(2)): every statement whose rows list the class and category;
- Annex I label tables for the classes added by Regulation (EU) 2023/707 (ED, PBT/vPvB, PMT/vPvM), which have no
  Annex IV Part 1 rows in the consolidated text.
Statements are compared by component (P301+P310 = P301, P310), because Annex IV lists both the combinations and
their parts. Where Annex I and Annex IV disagree for a class, the codes in question count as either.

Writes OUT_DIR/results.json and OUT_DIR/test_table.md. Needs Node 18+ for tools/pcalc_harness.js.
"""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEGAL = os.path.join(ROOT, 'data', 'legal')
sys.path.insert(0, HERE)

# Calculator-computed classes (verification/engine.js classify()); every other class reaches Article 28 only as a
# manual entry with user-typed H-codes.
CALCULATED = {'flammable_liquids', 'acute_oral', 'acute_dermal', 'acute_inhalation', 'skin_corrosion', 'skin_irritation',
              'eye_damage', 'eye_irritation', 'respiratory_sensitisation', 'skin_sensitisation', 'mutagenicity',
              'carcinogenicity', 'reproductive_toxicity', 'lactation', 'stot_se', 'stot_se_3_resp', 'stot_se_3_narc',
              'stot_re', 'aspiration', 'aquatic_acute', 'aquatic_chronic', 'ozone', 'ed_human_health', 'ed_environment',
              'pbt', 'pmt'}
SECTION_OF = [(r'^P1', 'general'), (r'^P2', 'prevention (S7/S8; S10 for P210-P235, P250)'), (r'^P3', 'response (S4/S5/S6)'),
              (r'^P4', 'storage (S7; S10 for P410-P420)'), (r'^P5', 'disposal (S13)')]


def latest(prefix):
    files = sorted(glob.glob(os.path.join(LEGAL, prefix + '*.json')))
    return json.load(open(files[-1], encoding='utf-8'))


def comps(codes):
    return {x.strip('[]') for c in codes for x in c.split('+')}


# Annex IV "conditions for use" (column 5) decide how a missing statement is graded
CONDITIONAL = re.compile(r'(?:^|—\s*)(?:if|for|except|where|when|unless)\b', re.I)
OMIT_IF = re.compile(r'(?:omit where|may be omitted (?:if|when)) (P\d{3}(?:\s*\+\s*P\d{3})*) is (?:used|given)', re.I)
# Annex IV lists skin corrosion "Category 1" for only some statements; Annex I Table 3.2.5 gives Category 1 and
# sub-categories 1A/1B/1C one column, so Category 1 takes the 1A/1B/1C rows as well.
# Annex I headings "Category 1 (Category 1A, 1B)" for CMR: Annex IV lists 1A and 1B only.
EQUIVALENT = {('skin_corrosion', '1'): ('skin_corrosion', '1A'), ('mutagenicity', '1'): ('mutagenicity', '1A'),
              ('carcinogenicity', '1'): ('carcinogenicity', '1A'), ('reproductive_toxicity', '1'): ('reproductive_toxicity', '1A')}
# Pyrophoric gases and chemically unstable gases A/B are always classified in Category 1A (Annex I 2.2.2.1)
INCLUDES = {('flammable_gases', 'Pyrophoric gas'): ('flammable_gases', '1A'), ('flammable_gases', 'A'): ('flammable_gases', '1A'),
            ('flammable_gases', 'B'): ('flammable_gases', '1A')}
PREFIX = set()   # statements that only open a combination ("IF SWALLOWED:", "In case of fire:"); filled from Annex IV


def tiers(codes_conditions, audience):
    """-> (required, conditional, optional) code sets for one class/category and audience."""
    req, cnd, opt = set(), set(), set()
    for code, c in codes_conditions.items():
        if code in PREFIX:
            continue
        if 'consumer products' in c.lower() and audience != 'consumer':
            opt.add(code)
        elif CONDITIONAL.search(c.replace('Manufacturer', '')) and not c.startswith('— text'):
            cnd.add(code)
        else:
            req.add(code)
    for code, c in codes_conditions.items():
        m = OMIT_IF.search(c)
        if m and re.sub(r'\s*\+\s*', '+', m.group(1)) in req | cnd:
            req.discard(code); cnd.discard(code); opt.add(code)
    return req, cnd, opt


def build_expectations():
    iv = latest('clp_annex_iv_eu_')
    lab = {(e['class_key'], e['category']): e for e in latest('clp_annex_i_label_p_eu_')['entries']}
    cat_h = latest('clp_category_h_eu_')['entries']
    by_cls = collections.defaultdict(set)
    cond = collections.defaultdict(dict)
    PREFIX.update(s['code'] for s in iv['statements'] if '+' not in s['code'] and s['text'].rstrip().endswith(':'))
    for s in iv['statements']:
        for r in s['rows']:
            for c in r['categories']:
                by_cls[(r['class_key'], c)].add(s['code'])
                cond[(r['class_key'], c)][s['code']] = r['conditions']
    for k, other in list(EQUIVALENT.items()) + list(INCLUDES.items()):
        by_cls[k] |= by_cls[other]
        for code, c in cond[other].items():
            cond[k].setdefault(code, c)
    rows, seen = [], set()
    for e in cat_h:
        k = (e['class_key'], e['category'])
        if k in seen:
            continue
        seen.add(k)
        ivset = by_cls.get(k, set())
        a1 = lab.get(k)
        either = set()
        if ivset:
            source = 'Annex IV Part 1'
            cc = cond.get(k, {})
            if a1:
                either = comps(a1['p']) ^ comps(ivset)
        elif a1 and a1['p']:
            source = 'Annex I ' + a1['source'].split(' ')[1].rstrip('.')
            cc = {c: '' for c in a1['p']}
        else:
            source, cc = 'no precautionary statements listed', {}
        t = {}
        for aud in ('industrial', 'consumer'):
            req, cnd, opt = tiers(cc, aud)
            rc = comps(req)
            t[aud] = {'required': sorted(rc), 'conditional': sorted(comps(cnd) - rc), 'optional': sorted(comps(opt) - rc - comps(cnd))}
        exp = set(t['industrial']['required']) | set(t['industrial']['conditional'])
        h = e['h'] + [x for x in next((y['h'] for y in cat_h if (y['class_key'], y['category']) == INCLUDES.get(k)), []) if x not in e['h']]
        rows.append({'class_key': k[0], 'category': k[1], 'h': h, 'expected': sorted(exp), 'tiers': t, 'either': sorted(either),
                     'source': source, 'annex_iv_codes': sorted(ivset), 'conditions': cond.get(k, {}),
                     'signal': a1['signal'] if a1 else None, 'calculated': k[0] in CALCULATED})
    return iv, rows


def annex_vi_label(class_key, category):
    """The Annex VI Table 1.1 code the calculator uses as an outcome label (None if there is none)."""
    codes = latest('clp_annex_vi_codes_')['entries']
    if class_key.startswith('acute_'):
        return f"Acute Tox. {category} ({class_key[6:]})"
    if class_key.startswith('stot_se_3_'):
        return 'STOT SE 3 (' + ('respiratory irritation' if class_key.endswith('resp') else 'narcotic effects') + ')'
    if class_key == 'gases_under_pressure':
        return 'Press. Gas'
    e = next((e for e in codes if e['class_key'] == class_key and category in e['categories']), None)
    if not e:
        return None
    inc = INCLUDES.get((class_key, category))
    return (annex_vi_label(*inc) + '; ' if inc else '') + e['code']


def run_node(engine, tests):
    p = subprocess.run(['node', os.path.join(HERE, 'pcalc_harness.js'), engine], input=json.dumps(tests),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def case_hcodes(cases_file, sds_dir):
    import check_s567 as s567
    doc = json.load(open(cases_file))
    base = os.path.dirname(os.path.abspath(cases_file))
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for c in doc['cases']:
            if c.get('repo_file'):
                path = os.path.join(ROOT, c['repo_file'])
            elif 'expected_dir' in doc:
                path = os.path.join(base, c['file'])
            else:
                path = os.path.join(sds_dir or '', c['file'])
            if not os.path.exists(path):
                out.append({'id': c['id'], 'missing': True})
                continue
            work = os.path.join(tmp, c['id'])
            subprocess.run([sys.executable, '-I', os.path.join(HERE, 'sds_text.py'), path, work], check=True, capture_output=True)
            sds = json.load(open(os.path.join(work, 'sds.json')))
            sds['_path'] = os.path.join(work, 'sds.json')
            H = sorted(h for h in s567.classification(sds) if re.match(r'^(?:EU)?H\d{3}', h))
            P = sorted(sds['codes_by_section'].get('2', {}).get('P', []))
            out.append({'id': c['id'], 'declared': c['declared'], 'h': H, 'p_on_sds': P})
    return out


def compare(tier, either, got):
    g, e = comps(got), set(either)
    allowed = set(tier['required']) | set(tier['conditional']) | set(tier['optional']) | e
    return (sorted(set(tier['required']) - g - e), sorted(set(tier['conditional']) - g - e), sorted(g - allowed))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', required=True)
    ap.add_argument('--cases', action='append', default=[])
    ap.add_argument('--sds-dir')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    iv, rows = build_expectations()
    texts = {s['code']: s['text'] for s in iv['statements']}

    # outcomes labelled as the calculator labels them (Annex VI codes); a second run gives H-codes only
    tests = [{'id': f"{r['class_key']}|{r['category']}", 'outcomes': [{'h': r['h'], 'label': annex_vi_label(r['class_key'], r['category']) or ' '.join(r['h'])}],
              'settings': {'audience': 'industrial', 'intendedUse': 'verification'}} for r in rows]
    tests += [{'id': 'h-only|' + f"{r['class_key']}|{r['category']}", 'outcomes': [{'h': r['h'], 'label': ' '.join(r['h'])}],
               'settings': {'audience': 'industrial', 'intendedUse': 'verification'}} for r in rows]
    tests += [{'id': 'consumer|' + f"{r['class_key']}|{r['category']}", 'outcomes': [{'h': r['h'], 'label': 'x'}],
               'settings': {'audience': 'consumer', 'intendedUse': 'verification'}} for r in rows]
    # H-code -> all (class, category) rows carrying it, for case expectations
    by_h = collections.defaultdict(list)
    by_tuple = collections.defaultdict(list)
    for r in rows:
        by_tuple[tuple(r['h'])].append(r)
        for h in r['h']:
            by_h[h].append(r)
    cases = []
    for cf in a.cases:
        cases += case_hcodes(cf, a.sds_dir)
    for c in cases:
        if not c.get('missing'):
            tests.append({'id': 'case|' + c['id'], 'outcomes': [{'h': [h], 'label': h} for h in c['h']],
                          'settings': {'audience': 'industrial', 'intendedUse': 'verification'}})
    res = run_node(a.engine, tests)
    rules = res.pop('_rules')

    table = []
    for r in rows:
        got = res[f"{r['class_key']}|{r['category']}"]
        # "class to confirm": held back because the H-code fits several classes; not proposed as eligible
        codes = [c['code'] for c in got['candidates'] if c['decision'] != 'class to confirm']
        missing, missing_cond, extra = compare(r['tiers']['industrial'], r['either'], codes)
        ho = res['h-only|' + f"{r['class_key']}|{r['category']}"]
        h_codes = [c['code'] for c in ho['candidates'] if c['decision'] != 'class to confirm']
        h_missing, _, h_extra = compare(r['tiers']['industrial'], r['either'], h_codes)
        table.append({**r, 'label': annex_vi_label(r['class_key'], r['category']), 'calculator': codes, 'selected': got['selected'],
                      'missing': missing, 'missing_conditional': missing_cond, 'extra': extra, 'uncovered': got['uncovered'],
                      'pass': not missing and not extra,
                      'h_only': {'missing': h_missing, 'extra': h_extra, 'held': [c['code'] for c in ho['candidates'] if c['decision'] == 'class to confirm'],
                                 'pass': not h_missing and not h_extra}})
    case_rows = []
    for c in cases:
        if c.get('missing'):
            case_rows.append({'id': c['id'], 'status': 'SDS file not available here'})
            continue
        got = res['case|' + c['id']]
        codes = [x['code'] for x in got['candidates'] if x['decision'] != 'class to confirm']
        ti = lambda x: x['tiers']['industrial']
        allrows = [x for h in c['h'] for x in by_h.get(h, [])]
        possible = set().union(*[set(ti(x)['required']) | set(ti(x)['conditional']) | set(ti(x)['optional']) | set(x['either'])
                                 for x in allrows]) if allrows else set()
        # certain: required statements shared by every class/category behind each H-code
        certain, cond_ = set(), set()
        for h in c['h']:
            rs = by_h.get(h, [])
            if rs:
                certain |= set.intersection(*[set(ti(x)['required']) for x in rs])
                cond_ |= set.intersection(*[set(ti(x)['conditional']) | set(ti(x)['required']) for x in rs])
        g = comps(codes)
        case_rows.append({'id': c['id'], 'h': c['h'], 'p_on_sds': c['p_on_sds'], 'calculator': codes, 'selected': got['selected'],
                          'uncovered': got['uncovered'], 'missing': sorted(certain - g), 'missing_conditional': sorted(cond_ - certain - g),
                          'extra': sorted(g - possible), 'pass': not (certain - g) and not (g - possible),
                          'h_not_in_annex_i': [h for h in c['h'] if h not in by_h]})
    # H-codes whose classes/categories need different statements: the calculator keys on H-codes only
    ambiguous = []
    for h, rs in sorted(by_tuple.items()):
        sets = {tuple(x['expected']) for x in rs}
        if len(sets) > 1:
            ambiguous.append({'h': '+'.join(h), 'rows': [(x['class_key'], x['category']) for x in rs],
                              'differ': sorted(set().union(*map(set, sets)) - set.intersection(*map(set, sets)))})
    wording = []
    norm = lambda s: re.sub(r'\s+', ' ', s.replace('…', '...').replace('/ ', '/').strip()).rstrip('.')
    for r in rules:
        law = texts.get(r['code'])
        wording.append({'code': r['code'], 'calculator': r['text'], 'annex_iv': law,
                        'same': law is not None and norm(law) == norm(r['text'])})
    consumer = []
    for r in rows:
        got = res['consumer|' + f"{r['class_key']}|{r['category']}"]
        codes = [c['code'] for c in got['candidates']]
        missing, missing_cond, extra = compare(r['tiers']['consumer'], r['either'], codes)
        consumer.append({'row': f"{r['class_key']} {r['category']}", 'has_P101_P102': 'P101' in codes and 'P102' in codes,
                         'P103': 'P103' in codes, 'P501': 'P501' in codes, 'missing': missing, 'extra': extra,
                         'blockers': [x['code'] for x in got['review'] if x['severity'] == 'blocker']})
    os.makedirs(a.out, exist_ok=True)
    json.dump({'class_rows': table, 'case_rows': case_rows, 'ambiguous_h': ambiguous, 'wording': wording,
               'consumer': consumer, 'rules': rules}, open(os.path.join(a.out, 'results.json'), 'w'), indent=1, ensure_ascii=False)
    with open(os.path.join(a.out, 'test_table.md'), 'w', encoding='utf-8') as f:
        f.write('| Class | Cat. | H | Calculated? | Required (source) | Conditional | Calculator candidates | Missing required | '
                'Missing conditional | Not eligible | Result |\n|---|---|---|---|---|---|---|---|---|---|---|\n')
        for t in table:
            ti = t['tiers']['industrial']
            f.write(f"| {t['class_key']} | {t['category']} | {' '.join(t['h'])} | {'yes' if t['calculated'] else 'manual H only'} | "
                    f"{' '.join(ti['required']) or '-'} ({t['source']}) | {' '.join(ti['conditional']) or '-'} | "
                    f"{' '.join(t['calculator']) or '-'} | {' '.join(t['missing']) or '-'} | {' '.join(t['missing_conditional']) or '-'} | "
                    f"{' '.join(t['extra']) or '-'} | {'PASS' if t['pass'] else 'FAIL'} |\n")
        f.write('\n| Case | H (Section 2) | Calculator candidates | Missing required | Missing conditional | Not eligible | Result |\n'
                '|---|---|---|---|---|---|---|\n')
        for c in case_rows:
            if 'status' in c:
                f.write(f"| {c['id']} | {c['status']} | | | | | n/a |\n")
                continue
            f.write(f"| {c['id']} | {' '.join(c['h']) or '-'} | {' '.join(c['calculator']) or '-'} | {' '.join(c['missing']) or '-'} | "
                    f"{' '.join(c['missing_conditional']) or '-'} | {' '.join(c['extra']) or '-'} | {'PASS' if c['pass'] else 'FAIL'} |\n")
    n = sum(t['pass'] for t in table)
    print(f"class/category rows: {n}/{len(table)} pass; calculated classes: "
          f"{sum(t['pass'] for t in table if t['calculated'])}/{sum(t['calculated'] for t in table)} pass")
    print(f"H-code-only inputs: {sum(t['h_only']['pass'] for t in table)}/{len(table)} pass")
    print(f"cases: {sum(c.get('pass', False) for c in case_rows)}/{len(case_rows)} pass")
    print(f"wording differences: {[w['code'] for w in wording if not w['same']]}")
    print(f"ambiguous H-codes: {[x['h'] for x in ambiguous]}")


if __name__ == '__main__':
    main()
