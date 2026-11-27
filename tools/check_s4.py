"""Section 4 (first-aid measures) checker: applies the Section 4 checklist rules to one SDS.

Inputs : sds.json from sds_text.py, lookup_<CAS>.json files from lookup.py.
Usage  : python3 -I check_s4.py SDS_JSON LOOKUP_DIR --declared GB|EU|US --type substance|mixture [--out findings.json]

Review aid only: a competent person must verify every finding. Keyword heuristics tuned on the regression set.
US precautionary-statement wording (OSHA App C) is published as images and is not verified: US text is matched
against the CLP wording. GHS Rev.10 codes P316-P319 are treated as equivalents per the approved rule; that mapping
has not been verified against the GHS Rev.10 text (unece.org not reachable from this environment).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_s10 as s10  # noqa: E402

# health hazard statements -> codes (for SDSs that print text without codes)
H_TEXT = [
    (r'fatal if swallowed', 'H300'), (r'toxic if swallowed', 'H301'), (r'harmful if swallowed', 'H302'),
    (r'may be fatal if swallowed and enters airways', 'H304'), (r'fatal in contact with skin', 'H310'),
    (r'toxic in contact with skin', 'H311'), (r'harmful in contact with skin', 'H312'),
    (r'causes severe skin burns and eye damage', 'H314'), (r'causes skin irritation', 'H315'),
    (r'may cause an allergic skin reaction', 'H317'), (r'causes serious eye damage', 'H318'),
    (r'causes serious eye irritation', 'H319'), (r'fatal if inhaled', 'H330'), (r'toxic if inhaled', 'H331'),
    (r'harmful if inhaled', 'H332'), (r'allergy or asthma symptoms', 'H334'), (r'may cause respiratory irritation', 'H335'),
    (r'may cause drowsiness or dizziness', 'H336'), (r'genetic defects', 'H340'), (r'may cause cancer', 'H350'),
    (r'suspected of causing cancer', 'H351'), (r'damage fertility|damage the unborn', 'H360'),
    (r'causes damage to organs(?! through prolonged)', 'H370'), (r'damage to organs through prolonged or repeated', 'H372'),
]
URGENT = {'H300', 'H301', 'H304', 'H310', 'H330', 'H314', 'H318'}          # P310 classes (CLP Annex IV)
ROUTE_TRIGGERS = {
    'ingestion': {'H300', 'H301', 'H302', 'H304', 'H314'},
    'skin': {'H310', 'H311', 'H312', 'H314', 'H315', 'H317', 'H224', 'H225', 'H226', 'H250', 'H260', 'H261'},
    'eyes': {'H314', 'H318', 'H319'},
    'inhalation': {'H330', 'H331', 'H332', 'H314', 'H334', 'H335', 'H336'},
}
HEALTH = {c for v in ROUTE_TRIGGERS.values() for c in v if c not in {'H224', 'H225', 'H226', 'H250', 'H260', 'H261'}} | {
    'H340', 'H341', 'H350', 'H351', 'H360', 'H361', 'H362', 'H370', 'H371', 'H372', 'H373'}
SYMPTOMS = {'H314': r'burn|corros', 'H318': r'eye damage|blind|burn', 'H319': r'eye irritation|irritat\w* (?:to |of )?(?:the )?eyes?|\bredness',
            'H315': r'skin irritation|\bredness|irritat', 'H335': r'respiratory|cough|sore throat|breath',
            'H336': r'drows|dizz|headache|narco', 'H317': r'rash|allerg|sensiti', 'H334': r'asthma|wheez|breath'}
# first-aid P-statements: code -> (text pattern to find it in Section 2, action pattern expected in Section 4)
P_ACTIONS = {
    'P330': (r'rinse mouth', r'rinse mouth|clean mouth|mouth with water'),
    'P331': (r'do not induce vomiting', r'do not induce vomiting|do not induce'),
    'P352': (r'wash with plenty of', r'wash\w* (?:off )?(?:\w+ )?with (?:plenty of )?(?:soap and )?water|wash off'),
    'P353': (r'rinse skin with water', r'rinse skin|shower|wash off'),
    'P361': (r'take off immediately all contaminated', r'(?:remove|take off)\w* (?:\w+ ){0,3}contaminated cloth'),
    'P362': (r'take off contaminated clothing', r'(?:remove|take off)\w* (?:\w+ ){0,3}contaminated cloth'),
    'P363': (r'wash contaminated clothing before reuse', r'wash\w* (?:\w+ ){0,6}before re-?use'),
    'P340': (r'remove (?:person|victim) to fresh air', r'fresh air|remove from exposure'),
    'P351': (r'rinse cautiously with water', r'rinse|irrigate|flush'),
    'P338': (r'remove contact lenses', r'contact lens'),
    'P310': (r'immediately call a poison cent', r'immediate|urgent|at once'),
    'P335': (r'brush off loose particles', r'brush off'),
    'P334': (r'immerse in cool water', r'immerse'),
    'P336': (r'thaw frosted parts', r'thaw'),
}
REV10 = {'P316': 'P310/P315', 'P317': 'P311/P313', 'P318': 'P308+P313', 'P319': 'P312/P314'}  # approved equivalence; GHS Rev.10 text not verified
ROUTE_LABELS = [
    ('eyes', r'(?:eye contact|eyes?|after eye contact|in case of eye contact|if in eyes)\b'),
    ('skin', r'(?:skin contact|skin|after skin contact|in case of skin contact|if on skin)\b'),
    ('inhalation', r'(?:inhalation|after inhalation|if inhaled|breathing)\b'),
    ('ingestion', r'(?:ingestion|after (?:ingestion|swallowing)|if swallowed|swallowing)\b'),
    ('general', r'general advice\b'),
    ('firstaider', r'(?:self-protection of the first aider|personal protection for first|protection of first[- ]aiders?)'),
    ('symptoms', r'most important symptoms'),
    ('physician', r'notes? to physician'),
]
NOINFO = r'no (?:further )?(?:relevant )?(?:information|data)(?: is)? available|not available|no data'
POS_VOMIT = r'(?<!not )(?<!never )(?<!n\'t )\binduce vomiting'


def low(x):
    return (x or '').lower()


def classification(sds):
    codes = s10.classification(sds)
    t = low(sds['sections'].get('2', {}).get('text', ''))
    for rx, code in H_TEXT:
        if re.search(rx, t):
            codes.add(code)
    return codes


def p_in_section2(sds):
    s2 = sds['sections'].get('2', {})
    codes = set(sds['codes_by_section'].get('2', {}).get('P', []))
    singles = {c for combo in codes for c in combo.split('+')}
    t = low(' '.join(s2.get('text', '').split()))
    for code, (rx, _) in P_ACTIONS.items():
        if re.search(rx, t):
            singles.add(code)
    for code in REV10:
        if code in singles:
            singles.add(code)
    return singles, codes


def routes(text):
    out, cur = {}, None
    for ln in text.split('\n'):
        stripped = re.sub(r'^\s*4\.\d\.?\s*', '', ln)
        hit = None
        for name, rx in ROUTE_LABELS:
            m = re.match(r'\s*' + rx + r'[ :\-–]*(.*)$', stripped, re.I)
            if m:
                hit = name
                out[name] = (out.get(name, '') + ' ' + m.group(1)).strip()
                break
        if hit:
            cur = hit
        elif cur and ln.strip() and not re.match(r'\s*4\.\d', ln):
            out[cur] += ' ' + ln.strip()
    return {k: ' '.join(v.split()) for k, v in out.items()}


def run(sds, lookup_dir, declared, sds_type):
    full = open(os.path.join(os.path.dirname(sds['_path']), 'sds.txt'), encoding='utf-8').read()
    findings = []

    def add(section, cid, status, says, expected, source):
        findings.append({'section': section, 'check': cid, 'status': status, 'sds_says': says[:300], 'expected': expected, 'source': source})

    detected, score, why = s10.detect_jurisdiction(full)
    J = declared or detected
    EUGB = J in ('EU', 'GB')
    juris = {'declared': declared, 'detected': detected, 'evidence': why[detected], 'mismatch': bool(declared and declared != detected)}
    if juris['mismatch']:
        add('All', '10-J1', 'warning', f"Detected {detected} ({'; '.join(why[detected])})", f'Declared {declared}; checks run as {declared}', 'Run rule')
    sec4 = sds['sections'].get('4')
    if not sec4:
        add('4', '4-A1', 'fail', 'Section 4 not found', 'Section 4 "First aid measures"', 'Annex II Part B / 1910.1200(g)(2)(iv)')
        return {'jurisdiction': juris, 'findings': findings}
    subs = sec4.get('subsections', {})
    s41 = subs.get('4.1', sec4['text'])
    r = routes(s41 if EUGB and '4.1' in subs else sec4['text'])
    s42 = ' '.join(re.sub(r'^\s*4\.2\.?[^\n]*\n', '', subs.get('4.2', '')).split()) if '4.2' in subs else r.get('symptoms', '')
    s43 = ' '.join(re.sub(r'^\s*4\.3\.?[^\n]*\n', '', subs.get('4.3', '')).split()) if '4.3' in subs else r.get('physician', '')
    s4 = low(' '.join(sec4['text'].split()))
    H = classification(sds)
    P, Pcodes = p_in_section2(sds)
    cas = sds['codes_all']['CAS']
    lk = s10.lookups(cas, lookup_dir)

    # ---- A: required content
    if EUGB:
        miss = [k for k in ('4.1', '4.2', '4.3') if k not in subs]
        if miss:
            add('4', '4-A2', 'fail', 'Missing: ' + ', '.join(miss), 'Numbered 4.1-4.3', 'Annex II Part B')
        blank = [k for k, v in (('4.2', s42), ('4.3', s43)) if k in subs and not v]
        if blank:
            add('4', '4-A4', 'fail', 'Blank: ' + ', '.join(blank), 'No blank subsections', 'Annex II 0.4')
        noinfo = [f'{k}: "{v[:50]}"' for k, v in (('4.2', s42), ('4.3', s43)) if re.search(NOINFO, low(v))]
        if noinfo:
            add('4', '4-A4', 'info', '; '.join(noinfo), '"No data" without a reason is allowed in Section 4 (no reasons rule)', 'Annex II 0.4 / s.4')
    else:
        miss = [n for n, ok in (('(a) routes', any(k in r for k in ('eyes', 'skin', 'inhalation', 'ingestion'))),
                                ('(b) symptoms', bool(s42)), ('(c) medical attention', bool(s43) or 'medical attention' in s4)) if not ok]
        if miss:
            add('4', '4-A3', 'fail', 'Missing: ' + ', '.join(miss), 'App D s.4 (a)-(c)', 'App D Table D.1 s.4')
    need = sorted(k for k, trig in ROUTE_TRIGGERS.items() if H & trig and k not in r)
    if need:
        add('4.1', '4-A6', 'fail', 'Routes given: ' + ', '.join(sorted(k for k in r if k in ROUTE_TRIGGERS)),
            'Route(s) required by classification: ' + ', '.join(need), 'Annex II 4.1.1 / App D s.4(a)')
    gaps = []
    if not re.search(r'medical|physician|doctor|poison', s4):
        gaps.append('whether medical attention is needed')
    if not re.search(r'fresh air|remove from exposure', s4):
        gaps.append('moving to fresh air')
    if not re.search(r'cloth|shoes', s4):
        gaps.append('removing/handling clothing and shoes')
    if not ('firstaider' in r or re.search(r'first[- ]?aider|rescuer|responder|pocket mask|mouth-to-mouth', s4)):
        gaps.append('PPE for first-aid responders')
    if gaps:
        add('4.1', '4-A7', 'warning' if EUGB else 'info', '4.1 does not say: ' + '; '.join(gaps), 'Advice on all four 4.1.2 points', 'Annex II 4.1.2')
    if H & URGENT and not re.search(r'immediate|urgent|at once|without delay', s4):
        add('4', '4-A8', 'fail' if EUGB else 'warning', 'No urgent wording', f'Immediate medical attention ({", ".join(sorted(H & URGENT))}: P310 classes)', 'Annex II s.4 preamble; CLP Annex IV P310')
    if EUGB:
        clin = [w for w in ('oxygen', 'gastric lavage', 'lavage', 'emesis', 'inject', 'intubat', 'administer') if any(w in low(v) for k, v in r.items() if k in ROUTE_TRIGGERS)]
        if clin:
            add('4.1', '4-A9', 'warning', 'Clinical steps in 4.1: ' + ', '.join(clin), 'Untrained responder, no special equipment; move clinical steps to 4.3', 'Annex II s.4 preamble')

    # ---- B: classification-driven
    ing = low(r.get('ingestion', ''))
    if re.search(POS_VOMIT, ing):
        asp_cor = H & {'H304', 'H314'}
        add('4.1', '4-B1', 'fail' if asp_cor else 'warning', r.get('ingestion', ''),
            '"Induce vomiting" ' + ('contradicts P331 (Asp. Tox. 1 / Skin Corr. 1)' if asp_cor else 'should be reviewed'), 'CLP Annex IV P331 conditions')
    elif H & {'H304', 'H314'} and 'induce vomiting' not in ing:
        add('4.1', '4-B1', 'warning', r.get('ingestion', ''), '"Do NOT induce vomiting" (P331)', 'CLP Annex IV P331')
    if 'H314' in H and not re.search(P_ACTIONS['P330'][1], ing) and 'ingestion' in r:
        add('4.1', '4-B1', 'warning', r.get('ingestion', ''), 'Rinse mouth (P301+P330+P331)', 'CLP Annex IV')
    skin = low(r.get('skin', ''))
    if 'skin' in r:
        want = []
        if H & {'H314', 'H224', 'H225', 'H226'}:
            if not re.search(P_ACTIONS['P361'][1], skin):
                want.append('take off contaminated clothing immediately (P361)')
            if not re.search(r'rinse|shower|wash|water', skin):
                want.append('rinse skin with water/shower (P353)')
        if H & {'H312', 'H315', 'H317'} and not re.search(r'wash|water|soap', skin):
            want.append('wash with plenty of water (P302+P352)')
        if want:
            add('4.1', '4-B2', 'warning', r.get('skin', ''), '; '.join(want), 'CLP Annex IV P303+P361+P353, P302+P352')
    eyes = low(r.get('eyes', ''))
    if H & {'H314', 'H318', 'H319'} and 'eyes' in r:
        if not re.search(r'rinse|irrigate|flush', eyes):
            add('4.1', '4-B3', 'fail', r.get('eyes', ''), 'Rinse with water (P305+P351+P338)', 'CLP Annex IV')
        elif 'contact lens' not in eyes:
            add('4.1', '4-B3', 'warning', r.get('eyes', ''), 'Remove contact lenses if present and easy to do; continue rinsing (P338)', 'CLP Annex IV P305+P351+P338')
    if H & ROUTE_TRIGGERS['inhalation'] and 'inhalation' in r and not re.search(r'fresh air|remove from exposure', low(r['inhalation'])):
        add('4.1', '4-B4', 'warning', r['inhalation'], 'Fresh air, keep comfortable for breathing (P304+P340)', 'CLP Annex IV')
    if H & {'H340', 'H341', 'H350', 'H351', 'H360', 'H361', 'H362', 'H370', 'H371', 'H372', 'H373'} and not re.search(r'medical advice|medical attention|physician', s4):
        add('4.1-4.3', '4-B5', 'warning', '', 'Medical advice after exposure (P308+P313 / P308+P311 / P314)', 'CLP Annex IV')
    p334_quote = ('CLP Annex IV P302+P335+P334: "IF ON SKIN: Brush off loose particles from skin. Immerse in cool water [or wrap in wet bandages]." '
                  'Condition for water-reactives (2.12): standalone P334 row "Use only \'immerse in cool water.\' Text in square brackets should not be used."; '
                  'combined row "use only \'Immerse in cold water\'" (the source itself differs: cool/cold)')
    if H & {'H260', 'H261'} and 'skin' in r:
        if re.search(r'wet bandage', skin):
            add('4.1', '4-B6', 'fail', r['skin'], 'No "wrap in wet bandages" for water-reactives (4.1 wording)', p334_quote)
        elif re.search(r'water|wash|rinse|immerse', skin) and not re.search(r'brush off|remove (?:loose )?particles', skin):
            add('4.1', '4-B6', 'fail', r['skin'], 'Brush off loose particles BEFORE applying water (P335 then P334)', p334_quote)
    if 'H271' in H and 'skin' in r and not re.search(r'rinse\w* (?:\w+ )*cloth\w* (?:\w+ )*before', skin):
        add('4.1', '4-B6', 'warning', r['skin'], 'Rinse contaminated clothing and skin before removing clothes (P306+P360)', 'CLP Annex IV')
    if 'H281' in H and not re.search(r'thaw|lukewarm', s4):
        add('4.1', '4-B6', 'fail', '', 'Thaw frosted parts with lukewarm water; do not rub (P336+P315)', 'CLP Annex IV')
    if P & {'P320', 'P321'} and not re.search(r'antidote|specific treatment|see (?:section|label)', low(s43)):
        add('4.3', '4-B7', 'fail' if EUGB else 'warning', s43, 'Specific treatment/antidote referred to by P320/P321', 'CLP Annex IV P320/P321')

    # ---- Section 2 findings arising from the Section 4 review
    s2 = low(' '.join(sds['sections'].get('2', {}).get('text', '').split()))
    if H & {'H260', 'H261'} and 'wet bandage' in s2:
        add('2.2', '2-L1', 'fail', 'Section 2: "...wrap in wet bandages"', 'Bracketed P334 text must not be used for water-reactives', p334_quote)
    rev10 = sorted(c for c in Pcodes for c in c.split('+') if c in REV10)
    if rev10:
        add('2.2', '2-L2', 'warning' if EUGB else 'info', 'GHS Rev.10 code(s): ' + ', '.join(rev10),
            ('EU/GB CLP Annex IV has no P316-P319: use ' if EUGB else 'Equivalent to ') + ', '.join(REV10[c] for c in rev10),
            'CLP Annex IV (EU 1.7.2026, GB); mapping per approved rule, GHS Rev.10 text not verified')

    # ---- C: cross-section (do not repeat a gap a 4-B row already reports)
    covered = set()
    for f in findings:
        e = f['expected']
        for code in re.findall(r'P\d{3}', e):
            covered.add(code)
        if f['check'] == '4-B6':
            covered |= {'P334', 'P335'}
    missing, contra = [], []
    for code in sorted(P):
        eq = code
        if code in REV10:
            continue
        if code in P_ACTIONS and code not in ('P310',) and code not in covered:
            if not re.search(P_ACTIONS[code][1], s4):
                missing.append(code)
    if 'P331' in P and re.search(POS_VOMIT, s4):
        contra.append('P331 on label vs "induce vomiting" in Section 4')
    if (P & {'P310', 'P315'} or P & {'P316'}) and not re.search(r'immediate|urgent|at once', s4):
        missing.append('P310/P316 (immediate medical help)')
    if contra or missing:
        add('4.1 ↔ 2', '4-C1', 'fail' if contra else 'warning', '; '.join(contra) or '',
            'Label first-aid statements not reflected in Section 4: ' + ', '.join(missing) if missing else 'No contradiction',
            'Annex II 2.2, 4.1; CLP Annex IV (P316-P319 matched as P310-P315 equivalents)')
    hc = H & HEALTH
    if hc and re.search(NOINFO, low(s42)) and len(s42) < 80:
        add('4.2 ↔ 2/11', '4-C2', 'fail', s42, f'Symptoms for the classified hazards ({", ".join(sorted(hc))})', 'Annex II 4.2, 11')
    elif hc:
        miss = [c for c, rx in SYMPTOMS.items() if c in hc and not re.search(rx, low(s42))]
        if miss:
            add('4.2 ↔ 2/11', '4-C2', 'warning', s42[:150], 'Symptoms missing for: ' + ', '.join(miss), 'Annex II 4.2, 11')
    if H & {'H300', 'H301', 'H330', 'H331'} and not re.search(r'mouth-to-mouth|pocket mask|first[- ]?aider', s4):
        add('4.1 ↔ 8', '4-C3', 'warning', '', 'Protect the first-aider (no mouth-to-mouth; PPE as Section 8)', 'Good practice (not binding)')
    s11 = low(' '.join(sds['sections'].get('11', {}).get('text', '').split())).replace('acute and delayed', '').replace('acute & delayed', '')
    if re.search(r'delayed (?:effect|onset|symptom|reaction)|(?:effects|symptoms) may be delayed|oedema|edema|may cause sensiti', s11) and not re.search(r'delay|later|hours', low(s42 + ' ' + s43)):
        add('4.2/4.3 ↔ 11', '4-C4', 'warning', s42[:100], 'Delayed effects in Section 11 reflected in 4.2/4.3', 'Annex II 4.2, 4.3, 11')

    # ---- D: data spot-checks
    gaps, srcs, fails = [], set(), []
    key = {'ingestion': [(r'do not induce vomiting', 'Do NOT induce vomiting')], 'eyes': [(r'rinse|irrigate|flush', 'rinse with plenty of water')],
           'skin': [(r'remove contaminated cloth', 'remove contaminated clothes')], 'inhalation': [(r'fresh air|remove from exposure', 'fresh air')]}
    delayed, special = [], []
    for c, d in lk.items():
        if c == '7732-18-5':
            continue
        for res in d['results']:
            if res['source'] == 'ICSC' and res['status'] == 'ok':
                for card in res['cards']:
                    for route, info in (card.get('first_aid') or {}).items():
                        fa = low(info.get('first_aid'))
                        for rx, label in key.get(route, []):
                            if re.search(rx, fa) and route in r and not re.search(rx if label != 'remove contaminated clothes' else P_ACTIONS['P361'][1], low(r[route])):
                                if label == 'Do NOT induce vomiting' and re.search(POS_VOMIT, low(r[route])):
                                    fails.append(f'{route}: ICSC {card["card"]} says "Do NOT induce vomiting"; SDS says to induce it')
                                elif not ({'ingestion': {'P331'}, 'eyes': {'P351'}, 'skin': {'P361'}, 'inhalation': {'P340'}}[route] & covered):
                                    gaps.append(f'{route}: {label}')
                                srcs.add(f'ICSC {card["card"]}')
                        if 'refer immediately' in fa and route in r and not re.search(r'immediate|urgent', low(r[route])):
                            gaps.append(f'{route}: refer immediately for medical attention')
                            srcs.add(f'ICSC {card["card"]}')
                    notes = low(card.get('notes'))
                    if re.search(r'do not become manifest|may be delayed|medical observation', notes):
                        delayed.append(f'ICSC {card["card"]}')
                    if re.search(r'antidote|specific treatment|calcium gluconate|removal by a physician', notes):
                        special.append(f'ICSC {card["card"]} ({c})')
    if fails or gaps:
        add('4.1', '4-D1', 'fail' if fails else 'warning', '', '; '.join(fails + sorted(set(gaps))), ', '.join(sorted(srcs)))
    if special and not re.search(r'antidote|specific treatment|physician|ophthalmolog|removal', low(s43)):
        add('4.3', '4-D2', 'warning', s43[:100], 'Specific treatment recorded in reference data: ' + ', '.join(special), 'ICSC notes')
    if delayed and not re.search(r'delay|observation|hours', low(s42 + ' ' + s43)):
        add('4.2/4.3', '4-D3', 'warning', (s42 + ' | ' + s43)[:120], 'Delayed effects (lung oedema; medical observation) recorded in ' + ', '.join(sorted(set(delayed))), 'ICSC notes')
    return {'jurisdiction': juris, 'H': sorted(H), 'P_section2': sorted(P), 'routes': r, 'findings': findings}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sds_json'); ap.add_argument('lookup_dir')
    ap.add_argument('--declared', choices=['EU', 'GB', 'US']); ap.add_argument('--type', choices=['substance', 'mixture'], required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    sds = json.load(open(a.sds_json)); sds['_path'] = a.sds_json
    res = run(sds, a.lookup_dir, a.declared, a.type)
    j = res['jurisdiction']
    print(f"jurisdiction: declared={j['declared']} detected={j['detected']}" + ('  ** MISMATCH **' if j['mismatch'] else ''))
    print('H:', res.get('H'), '| P(s2):', res.get('P_section2'), '| routes:', sorted(res.get('routes', {})))
    for f in res['findings']:
        print(f"  {f['check']:<9} {f['status']:<8} {f['sds_says'][:80]!r} -> {f['expected'][:120]}")
    if a.out:
        json.dump(res, open(a.out, 'w'), indent=1, ensure_ascii=False)
