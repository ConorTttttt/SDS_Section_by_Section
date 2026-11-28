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
from dedupe import dedupe  # noqa: E402
import refgate  # noqa: E402
import textinterp as ti  # noqa: E402

# Checklist rows this engine implements (checked against checklist/coverage.csv by tools/check_coverage.py)
CODED = ({f'4-A{i}' for i in range(1, 11)} | {f'4-B{i}' for i in range(1, 8)} | {f'4-C{i}' for i in range(1, 5)}
         | {f'4-D{i}' for i in range(1, 4)} | {'2-L1', '2-L2'})

# health hazard statements -> codes (for SDSs that print text without codes)
H_TEXT = [
    # "May be fatal if swallowed and enters airways" is H304, not H300 (blind test, ATF lubricant)
    (r'fatal if swallowed(?! and enters airways)', 'H300'), (r'toxic if swallowed', 'H301'), (r'harmful if swallowed(?! and enters airways)', 'H302'),
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
SYMPTOMS = {'H314': r'burn|corros', 'H318': ti.SYNONYMS['eye_symptoms'], 'H319': r'eye irritation|irritat\w* (?:to |of )?(?:the )?eyes?|\bredness',
            'H315': r'skin irritation|\bredness|irritat', 'H335': r'respiratory|cough|sore throat|breath',
            'H336': r'drows|dizz|headache|narco', 'H317': r'rash|allerg|sensiti', 'H334': r'asthma|wheez|breath'}
# first-aid P-statements: code -> (text pattern to find it in Section 2, action pattern expected in Section 4)
P_ACTIONS = {
    # (label text in Section 2, what Section 4 must say: textinterp synonyms so "flush" = "rinse" = "wash with water")
    'P330': (r'rinse mouth', ti.SYNONYMS['rinse_mouth']),
    'P331': (r'do not induce vomiting', ti.SYNONYMS['no_vomit']),
    'P352': (r'wash with plenty of', ti.SYNONYMS['rinse_water']),
    'P353': (r'rinse skin with water', ti.SYNONYMS['rinse_water']),
    'P361': (r'take off immediately all contaminated', ti.SYNONYMS['remove_clothing']),
    'P362': (r'take off contaminated clothing', ti.SYNONYMS['remove_clothing']),
    'P363': (r'wash contaminated clothing before reuse', ti.SYNONYMS['wash_clothing']),
    'P340': (r'remove (?:person|victim) to fresh air', ti.SYNONYMS['fresh_air']),
    'P351': (r'rinse cautiously with water', ti.SYNONYMS['rinse_eyes']),
    'P338': (r'remove contact lenses', ti.SYNONYMS['contact_lenses']),
    'P310': (r'immediately call a poison cent', ti.SYNONYMS['urgent']),
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
    ('general', r'general(?: advice| information| notes?)?\b'),
    ('firstaider', r'(?:self[- ]protection of the first[- ]aider|personal protection for first|protection of first[- ]aiders?)'),
    ('symptoms', r'most important symptoms'),
    ('physician', r'notes? to physician'),
]
ROUTE_PREFIX = r'(?:first[- ]aid measures?\s+)?'   # "First-aid measures after ingestion :" (label-style layouts)


def noinfo(v):
    return ti.is_no_data(v)


def pos_vomit(text):
    return ti.affirmed(text, ti.SYNONYMS['induce_vomit'])


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
            m = re.match(r'\s*' + ROUTE_PREFIX + rx + r'[ :\-–]*(.*)$', stripped, re.I)
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

    def add(section, cid, status, says, expected, source, items=None, prefix=None, suffix=''):
        f = {'section': section, 'check': cid, 'status': status, 'sds_says': says[:300], 'expected': expected, 'source': source}
        if items:
            f.update(items=items, prefix=prefix, suffix=suffix)
        findings.append(f)

    detected, score, why = s10.detect_jurisdiction(full)
    J = declared or detected
    EUGB = J in ('EU', 'GB')
    juris = {'declared': declared, 'detected': detected, 'evidence': why[detected], 'mismatch': bool(declared and declared != detected)}
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
    gate = refgate.Gate(sds, H, sds_type)

    # ---- A: required content
    if EUGB:
        miss = [k for k in ('4.1', '4.2', '4.3') if k not in subs]
        if miss:
            add('4', '4-A2', 'fail', 'Missing: ' + ', '.join(miss), 'Numbered 4.1-4.3', 'Annex II Part B')
        blank = [k for k, v in (('4.2', s42), ('4.3', s43)) if k in subs and not v]
        if blank:
            add('4', '4-A4', 'fail', 'Blank: ' + ', '.join(blank), 'No blank subsections', 'Annex II 0.4')
        nd = [f'{k}: "{v[:50]}"' for k, v in (('4.2', s42), ('4.3', s43)) if noinfo(v)]
        if nd:
            add('4', '4-A4', 'info', '; '.join(nd), '"No data" without a reason is allowed in Section 4 (no reasons rule)', 'Annex II 0.4 / s.4')
    else:
        miss = [n for n, ok in (('(a) routes', any(k in r for k in ('eyes', 'skin', 'inhalation', 'ingestion'))),
                                ('(b) symptoms', bool(s42)), ('(c) medical attention', bool(s43) or 'medical attention' in s4)) if not ok]
        if miss:
            add('4', '4-A3', 'fail', 'Missing: ' + ', '.join(miss), 'App D s.4 (a)-(c)', 'App D Table D.1 s.4')
    if not EUGB:
        empty = [k for k in ('eyes', 'skin', 'inhalation', 'ingestion', 'symptoms', 'physician') if k in r and not r[k]]
        if empty:
            add('4', '4-A5', 'fail', 'Empty: ' + ', '.join(empty), 'Mark "no applicable information available"', '1910.1200(g)(3)')
    if not (H & HEALTH) and (not s42 or noinfo(s42)):
        add('4.2', '4-A10', 'warning', s42[:100], 'Most important acute and delayed symptoms summarised (or why none are expected)', 'Annex II 4.2; App D s.4(b)')
    need = sorted(k for k, trig in ROUTE_TRIGGERS.items() if H & trig and k not in r)
    if need:
        add('4.1', '4-A6', 'fail', 'Routes given: ' + ', '.join(sorted(k for k in r if k in ROUTE_TRIGGERS)),
            'Route(s) required by classification: ' + ', '.join(need), 'Annex II 4.1.1 / App D s.4(a)')
    gaps = []
    if not re.search(ti.SYNONYMS['medical'], s4):
        gaps.append(('gen:medical', 'whether medical attention is needed'))
    if not re.search(ti.SYNONYMS['fresh_air'], s4):
        gaps.append(('P:P340', 'moving to fresh air'))
    if not re.search(r'cloth|shoes|garment', s4):
        gaps.append(('P:P361', 'removing/handling clothing and shoes'))
    if not ('firstaider' in r or re.search(ti.SYNONYMS['firstaider_ppe'], s4)):
        gaps.append(('gen:ppe', 'PPE for first-aid responders'))
    if gaps:
        st = 'warning' if EUGB else 'info'
        add('4.1', '4-A7', st, '4.1 does not say: ' + '; '.join(t for _, t in gaps), 'Advice missing on: ' + '; '.join(t for _, t in gaps), 'Annex II 4.1.2',
            items=[{'key': k, 'text': t, 'status': st} for k, t in gaps], prefix='Advice missing on: ')
    if H & URGENT and not re.search(r'immediate|urgent|at once|without delay', s4):
        add('4', '4-A8', 'fail' if EUGB else 'warning', 'No urgent wording', f'Immediate medical attention ({", ".join(sorted(H & URGENT))}: P310 classes)', 'Annex II s.4 preamble; CLP Annex IV P310')
    if EUGB:
        # clinical steps for an untrained first-aider; a step limited to trained/medical personnel is acceptable in 4.1
        sents = [x for k, v in r.items() if k in ROUTE_TRIGGERS for x in s10.sentences(v)]
        clin = sorted({w for w in ('oxygen', 'gastric lavage', 'lavage', 'emesis', 'inject', 'intubat', 'administer')
                       for x in sents if w in low(x) and not re.search(r'trained|qualified|medical personnel|physician|doctor|paramedic', low(x))})
        if clin:
            add('4.1', '4-A9', 'warning', 'Clinical steps in 4.1: ' + ', '.join(clin), 'Untrained responder, no special equipment; move clinical steps to 4.3', 'Annex II s.4 preamble')

    # ---- B: classification-driven
    def one(key, status, text):
        return [{'key': key, 'status': status, 'text': text}]
    ing = low(r.get('ingestion', ''))
    if pos_vomit(ing):
        asp_cor = H & {'H304', 'H314'}
        st = 'fail' if asp_cor else 'warning'
        txt = '"Induce vomiting" ' + ('contradicts P331 (Asp. Tox. 1 / Skin Corr. 1)' if asp_cor else 'should be reviewed (no Asp. Tox. 1 / Skin Corr. 1, so not a P331 contradiction)')
        add('4.1', '4-B1', st, r.get('ingestion', ''), txt, 'CLP Annex IV P331 conditions', items=one('P:P331', st, txt), prefix='')
    elif H & {'H304', 'H314'} and not ti.says(ing, 'no_vomit') and not ti.says(s4, 'no_vomit'):
        add('4.1', '4-B1', 'warning', r.get('ingestion', ''), '"Do NOT induce vomiting" (P331)', 'CLP Annex IV P331',
            items=one('P:P331', 'warning', '"Do NOT induce vomiting" (P331)'), prefix='')
    if 'H314' in H and not re.search(P_ACTIONS['P330'][1], ing) and 'ingestion' in r:
        add('4.1', '4-B1', 'warning', r.get('ingestion', ''), 'Rinse mouth (P301+P330+P331)', 'CLP Annex IV',
            items=one('P:P330', 'warning', 'Rinse mouth (P301+P330+P331)'), prefix='')
    skin = low(r.get('skin', ''))
    if 'skin' in r:
        want = []
        if H & {'H314', 'H224', 'H225', 'H226'}:
            if not re.search(P_ACTIONS['P361'][1], skin):
                want.append(('P:P361', 'take off contaminated clothing immediately (P361)'))
            if not re.search(ti.SYNONYMS['rinse_water'], skin):
                want.append(('P:P353', 'rinse skin with water/shower (P353)'))
        if H & {'H312', 'H315', 'H317'} and not re.search(ti.SYNONYMS['rinse_water'] + r'|soap', skin):
            want.append(('P:P352', 'wash with plenty of water (P302+P352)'))
        if want:
            add('4.1', '4-B2', 'warning', r.get('skin', ''), '; '.join(t for _, t in want), 'CLP Annex IV P303+P361+P353, P302+P352',
                items=[{'key': k, 'status': 'warning', 'text': t} for k, t in want], prefix='')
    eyes = low(r.get('eyes', ''))
    if H & {'H314', 'H318', 'H319'} and 'eyes' in r:
        if not re.search(ti.SYNONYMS['rinse_eyes'], eyes):
            add('4.1', '4-B3', 'fail', r.get('eyes', ''), 'Rinse with water (P305+P351+P338)', 'CLP Annex IV',
                items=one('P:P351', 'fail', 'Rinse with water (P305+P351+P338)'), prefix='')
        elif not re.search(ti.SYNONYMS['contact_lenses'], eyes):
            t = 'Remove contact lenses if present and easy to do; continue rinsing (P338)'
            add('4.1', '4-B3', 'warning', r.get('eyes', ''), t, 'CLP Annex IV P305+P351+P338', items=one('P:P338', 'warning', t), prefix='')
    if H & ROUTE_TRIGGERS['inhalation'] and 'inhalation' in r and not re.search(ti.SYNONYMS['fresh_air'], low(r['inhalation'])):
        t = 'Fresh air, keep comfortable for breathing (P304+P340)'
        add('4.1', '4-B4', 'warning', r['inhalation'], t, 'CLP Annex IV', items=one('P:P340', 'warning', t), prefix='')
    if H & {'H340', 'H341', 'H350', 'H351', 'H360', 'H361', 'H362', 'H370', 'H371', 'H372', 'H373'} and not re.search(ti.SYNONYMS['medical'], s4):
        add('4.1-4.3', '4-B5', 'warning', '', 'Medical advice after exposure (P308+P313 / P308+P311 / P314)', 'CLP Annex IV')
    p334_quote = ('CLP Annex IV P302+P335+P334: "IF ON SKIN: Brush off loose particles from skin. Immerse in cool water [or wrap in wet bandages]." '
                  'Condition for water-reactives (2.12): standalone P334 row "Use only \'immerse in cool water.\' Text in square brackets should not be used."; '
                  'combined row "use only \'Immerse in cold water\'". The source uses both words, so "cool" and "cold" are both accepted.')
    if H & {'H260', 'H261'} and 'skin' in r:
        if re.search(r'wet bandage', skin):
            t = 'No "wrap in wet bandages" for water-reactives (4.1 wording)'
            add('4.1', '4-B6', 'fail', r['skin'], t, p334_quote, items=one('P:P334', 'fail', t), prefix='')
        elif re.search(r'water|wash|rinse|immerse', skin) and not re.search(r'brush off|remove (?:loose )?particles', skin):
            t = 'Brush off loose particles BEFORE applying water (P335 then P334)'
            add('4.1', '4-B6', 'fail', r['skin'], t, p334_quote,
                items=one('P:P335', 'fail', t) + one('P:P334', 'fail', t), prefix='')
        m_imm = re.search(r'immerse in (\w+) water', skin)
        if m_imm and m_imm.group(1) not in ('cool', 'cold'):
            t = f'"Immerse in {m_imm.group(1)} water": CLP gives "cool" (P334) or "cold" (combined row) water'
            add('4.1', '4-B6', 'warning', r['skin'], t, p334_quote, items=one('P:P334-temp', 'warning', t), prefix='')
    if 'H271' in H and 'skin' in r and not re.search(r'rinse\w* (?:\w+ )*cloth\w* (?:\w+ )*before', skin):
        add('4.1', '4-B6', 'warning', r['skin'], 'Rinse contaminated clothing and skin before removing clothes (P306+P360)', 'CLP Annex IV')
    if 'H281' in H and not re.search(r'thaw|lukewarm', s4):
        add('4.1', '4-B6', 'fail', '', 'Thaw frosted parts with lukewarm water; do not rub (P336+P315)', 'CLP Annex IV')
    # P320/P321 conditions (CLP Annex IV): antidote for Acute Tox. oral 1-3 / inhalation 1-2; immediate specific measures
    # (e.g. a cleansing agent) for Acute Tox. dermal 1-4, inhalation 3, STOT SE 1; only an optional cleansing agent for
    # Skin Corr. / Skin Irrit. / Skin Sens., so P321 from those classes alone asks nothing of 4.3.
    if not re.search(r'antidote|specific treatment|specific measures|cleansing agent|see (?:section|label)', low(s43)):
        if ('P320' in P and 'H330' in H) or ('P321' in P and H & {'H300', 'H301'}):
            add('4.3', '4-B7', 'fail' if EUGB else 'warning', s43, 'Antidote / specific treatment referred to by P320/P321 (acute toxicity)', 'CLP Annex IV P320/P321 conditions')
        elif P & {'P320', 'P321'} and H & {'H310', 'H311', 'H312', 'H331', 'H370'}:
            add('4.3', '4-B7', 'warning', s43, 'Immediate specific measures (e.g. cleansing agent) referred to by P321', 'CLP Annex IV P321 conditions')

    # ---- Section 2 findings arising from the Section 4 review
    s2 = low(' '.join(sds['sections'].get('2', {}).get('text', '').split()))
    if H & {'H260', 'H261'} and 'wet bandage' in s2:
        add('2.2', '2-L1', 'fail', 'Section 2: "...wrap in wet bandages"', 'Bracketed P334 text must not be used for water-reactives', p334_quote)
    rev10 = sorted({c for combo in Pcodes for c in combo.split('+') if c in REV10})
    if rev10:
        add('2.2', '2-L2', 'warning' if EUGB else 'info', 'GHS Rev.10 code(s): ' + ', '.join(rev10),
            ('EU/GB CLP Annex IV has no P316-P319 (verified): use ' if EUGB else 'Code version flag only; treated as equivalent to ')
            + ', '.join(f'{c} -> {REV10[c]}' for c in rev10) + '. Mapping UNVERIFIED until checked against GHS Rev.11 Annex 3.',
            'CLP Annex IV (EU consolidated 1.7.2026; GB)')

    # ---- C: cross-section
    items = []
    if 'P331' in P and pos_vomit(s4):
        items.append({'key': 'P:P331', 'status': 'fail', 'text': 'P331 on label vs "induce vomiting" in Section 4'})
    for code in sorted(P):
        if code in P_ACTIONS and code != 'P310' and not re.search(P_ACTIONS[code][1], s4):
            items.append({'key': 'P:' + code, 'status': 'warning', 'text': code + ' not reflected'})
    if P & {'P310', 'P315', 'P316'} and not re.search(ti.SYNONYMS['urgent'], s4):
        items.append({'key': 'urgent', 'status': 'warning', 'text': 'P310/P315/P316 (immediate medical help; P316 matched as an unverified equivalent) not reflected'})
    if items:
        st = 'fail' if any(x['status'] == 'fail' for x in items) else 'warning'
        add('4.1 ↔ 2', '4-C1', st, '', 'Label first-aid statements vs Section 4: ' + '; '.join(x['text'] for x in items),
            'Annex II 2.2, 4.1; CLP Annex IV', items=items, prefix='Label first-aid statements vs Section 4: ')
    hc = H & HEALTH
    if hc and noinfo(s42):
        add('4.2 ↔ 2/11', '4-C2', 'fail', s42, f'Symptoms for the classified hazards ({", ".join(sorted(hc))})', 'Annex II 4.2, 11')
    elif hc:
        miss = [c for c, rx in SYMPTOMS.items() if c in hc and not re.search(rx, low(s42))]
        if miss:
            add('4.2 ↔ 2/11', '4-C2', 'warning', s42[:150], 'Symptoms missing for: ' + ', '.join(miss), 'Annex II 4.2, 11')
    if H & {'H300', 'H301', 'H330', 'H331'} and not re.search(r'mouth-to-mouth|pocket mask|first[- ]?aider', s4):
        add('4.1 ↔ 8', '4-C3', 'warning', '', 'Protect the first-aider (no mouth-to-mouth; PPE as Section 8)', 'Good practice (not binding)')
    s11 = low(' '.join(sds['sections'].get('11', {}).get('text', '').split())).replace('acute and delayed', '').replace('acute & delayed', '')
    # a "Potential delayed effects : Not available" field is not a delayed effect
    s11 = re.sub(r'(?:potential )?delayed (?:effects?|onset|symptoms?|reactions?)\s*:\s*(?:not available|no (?:specific |known )?data[^.]*|none known|no known[^.]*)', ' ', s11)
    if re.search(r'delayed (?:effect|onset|symptom|reaction)|(?:effects|symptoms) may be delayed|oedema|edema|may cause sensiti', s11) and not re.search(r'delay|later|hours', low(s42 + ' ' + s43)):
        t = 'Delayed effects in Section 11 reflected in 4.2/4.3'
        add('4.2/4.3 ↔ 11', '4-C4', 'warning', s42[:100], t, 'Annex II 4.2, 4.3, 11', items=one('gen:delayed', 'warning', t), prefix='')

    # ---- D: data spot-checks
    ditems, srcs = [], set()
    route_key = {'ingestion': 'P:P331', 'eyes': 'P:P351', 'skin': 'P:P361', 'inhalation': 'P:P340'}
    key = {'ingestion': [(r'do not induce vomiting', 'Do NOT induce vomiting', ti.SYNONYMS['no_vomit'])],
           'eyes': [(r'rinse|irrigate|flush', 'rinse with plenty of water', ti.SYNONYMS['rinse_eyes'])],
           'skin': [(r'remove contaminated cloth', 'remove contaminated clothes', ti.SYNONYMS['remove_clothing'])],
           'inhalation': [(r'fresh air|remove from exposure', 'fresh air', ti.SYNONYMS['fresh_air'])]}
    delayed, special = [], []
    for c, d in lk.items():
        if c == '7732-18-5':
            continue
        for res in d['results']:
            if res['source'] == 'ICSC' and res['status'] == 'ok':
                for card in res['cards']:
                    lab = f'ICSC {card["card"]}'
                    form_txt = ' '.join(str(x) for x in (card.get('name'), card.get('physical_dangers'), card.get('first_aid'), card.get('fire_and_explosion')) if x)
                    if not gate.card_applies(c, lab, form_txt):
                        continue
                    for route, info in (card.get('first_aid') or {}).items():
                        fa = low(info.get('first_aid'))
                        for rx, label, sds_rx in key.get(route, []):
                            if re.search(rx, fa) and route in r and not re.search(sds_rx, low(r[route])):
                                if label == 'Do NOT induce vomiting' and pos_vomit(low(r[route])):
                                    st = gate.allow(c, {'ingestion'}, 'fail', lab)
                                    if st:
                                        ditems.append({'key': 'P:P331', 'status': st, 'text': f'{route}: {lab} says "Do NOT induce vomiting"; SDS says to induce it'})
                                else:
                                    st = gate.allow(c, {route}, 'warning', lab)
                                    if st:
                                        ditems.append({'key': route_key[route], 'status': st, 'text': f'{route}: {label}'})
                                srcs.add(lab)
                        if 'refer immediately' in fa and route in r and not re.search(ti.SYNONYMS['urgent'], low(r[route])):
                            st = gate.allow(c, {route}, 'warning', lab)
                            if st:
                                ditems.append({'key': 'urgent:' + route, 'status': st, 'text': f'{route}: refer immediately for medical attention'})
                                srcs.add(lab)
                    notes = low(card.get('notes'))
                    if re.search(r'do not become manifest|may be delayed|medical observation', notes) and gate.allow(c, {'delayed_health'}, 'warning', lab):
                        delayed.append(lab)
                    if re.search(r'antidote|specific treatment|calcium gluconate|removal by a physician', notes) and \
                            gate.allow(c, {'inhalation', 'skin', 'eyes', 'ingestion'}, 'warning', lab):
                        special.append(f'{lab} ({c})')
    uniq = {}
    for x in ditems:
        uniq.setdefault((x['key'], x['text']), x)
    ditems = list(uniq.values())
    if ditems:
        st = refgate.strongest(*[x['status'] for x in ditems])
        add('4.1', '4-D1', st, '', '; '.join(x['text'] for x in ditems), ', '.join(sorted(srcs)), items=ditems, prefix='')
    if special and not re.search(r'antidote|specific treatment|physician|ophthalmolog|removal', low(s43)):
        add('4.3', '4-D2', 'warning', s43[:100], 'Specific treatment recorded in reference data: ' + ', '.join(special), 'ICSC notes')
    if delayed and not re.search(r'delay|observation|hours', low(s42 + ' ' + s43)):
        t = 'Delayed effects (lung oedema; medical observation) recorded in ' + ', '.join(sorted(set(delayed)))
        add('4.2/4.3', '4-D3', 'warning', (s42 + ' | ' + s43)[:120], t, 'ICSC notes', items=one('gen:delayed', 'warning', t), prefix='')
    findings = dedupe(findings)
    return {'jurisdiction': juris, 'H': sorted(H), 'P_section2': sorted(P), 'routes': r, 'findings': findings, 'gating': gate.notes}


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
    import coverage
    have = any(not k.endswith('7732-18-5.json') for k in os.listdir(a.lookup_dir) if k.startswith('lookup_') and k[7:-5] in sds['codes_all']['CAS'])
    coverage.print_not_run('4', a.declared or res['jurisdiction']['detected'], a.type, have)
    if a.out:
        json.dump(res, open(a.out, 'w'), indent=1, ensure_ascii=False)
