"""Section 10 checker: applies the tuned Section 10 checklist rules to one SDS.

Inputs : the sds.json written by sds_text.py, and lookup_<CAS>.json files written by lookup.py.
Output : findings JSON (one entry per check that fired) plus a jurisdiction report.

Usage:
  python3 -I check_s10.py SDS_JSON LOOKUP_DIR --declared GB|EU|US --type substance|mixture [--out findings.json]

This is a review aid, not sign-off. A competent person must verify every finding.
The rules are keyword heuristics tuned on a small regression set. Expect misses and false hits on new layouts.
"""
import argparse
import glob
import json
import os
import re

# ------------------------------------------------------------------ vocabularies
FAMILIES = {  # common material families: a recorded violent reaction with one of these missing from 10.5 is a fail
    'water': r'\bwater\b|moist|humid|aqueous',
    'air': r'\bair\b|\boxygen\b',
    'acids': r'\bacids?\b|hydrogen chloride|hydrochloric',
    'bases': r'\bbases?\b|\bbasic\b|alkali(?!ne earth)(?! metal)|caustic|hydroxides?',
    'oxidisers': r'oxidi[sz](?:ing|er|ers)|oxidants?|peroxides?|perchlor',
    'reducers': r'reduc(?:ing|tant)',
    'combustibles': r'combustible|organic material',
    'metals': r'\bmetals?\b|metallic',
    'halogens': r'\bhalogens?\b|\bchlorine\b|\bbromine\b|\biodine\b|\bfluorine\b',
    'halogenated compounds': r'halogenated|chloroform|bromoform|alkyl halide',
    'ammonia': r'ammonia|ammonium',
    'amines': r'\bamines?\b',
}
REAGENTS = {  # named reagents: missing ones are warnings
    'urea': r'\burea\b', 'silver nitrate / silver salts': r'silver nitrate|silver salt',
    'copper salts': r'copper salt|copper and its compounds', 'sulfur': r'\bsulfur\b|\bsulphur\b',
    'magnesium': r'magnesium', 'lead (II) fluoride': r'lead,? (?:di)?fluoride|lead difluoride',
    'iron (III) chloride / oxide': r'iron \(?iii\)? (?:chloride|oxide)|iron (?:oxide|chloride)',
    'tin (II) chloride': r'tin \(?ii\)? chloride', 'methanol': r'methanol', 'aldehydes': r'aldehydes?',
}
VIOLENT = r'violent|explo|fire|ignit|incandesc|toxic|poison|flammable gas|shock[- ]sensitive|detonat|burns? fiercely|burns? violently'
PRODUCT_VERB = r'\b(?:produces?|produced|producing|releas(?:es|ed|ing|e)|evolv(?:es|ed|ing|e)|forms?|formed|forming|generat(?:es|ed|ing|e)|liberat(?:es|ed|ing|e)|gives?|giving|to give|into|liberation of|decomposes? to)\b'

# physical-hazard statements -> codes (for SDSs that print text without codes, e.g. US)
H_TEXT = [
    (r'corrosive to metals', 'H290'), (r'in contact with water releases flammable gas(?:es)? which may ignite', 'H260'),
    (r'in contact with water releases flammable gas(?:es)?(?:\.|$)(?! which)', 'H261'), (r'catches fire spontaneously if exposed to air', 'H250'),
    (r'extremely flammable liquid', 'H224'), (r'highly flammable liquid', 'H225'), (r'(?<!highly )(?<!extremely )flammable liquid and vapou?r', 'H226'),
    (r'flammable solid', 'H228'), (r'extremely flammable gas', 'H220'), (r'contains gas under pressure', 'H280'),
    (r'may cause or intensify fire', 'H270'), (r'may cause fire or explosion; strong oxidi', 'H271'), (r'may intensify fire; oxidi', 'H272'),
    (r'heating may cause an explosion', 'H240'), (r'heating may cause a fire or explosion', 'H241'), (r'heating may cause a fire', 'H242'),
    (r'self-heating', 'H251'), (r'may react explosively even in the absence of air', 'H230'),
]
REACTIVITY_CLASS = {'H200', 'H201', 'H202', 'H203', 'H204', 'H205', 'H206', 'H207', 'H208', 'H230', 'H231', 'H232',
                    'H240', 'H241', 'H242', 'H250', 'H251', 'H252', 'H260', 'H261', 'H270', 'H271', 'H272', 'H290',
                    'EUH014', 'EUH019', 'EUH029', 'EUH031', 'EUH032', 'EUH044', 'EUH206'}
UNSTABLE_CLASS = {'H200', 'H201', 'H202', 'H203', 'H204', 'H205', 'H206', 'H207', 'H208', 'H230', 'H231', 'H240', 'H241', 'H242', 'EUH019', 'EUH044'}
FIRE_CLASS = REACTIVITY_CLASS - {'H290', 'EUH014', 'EUH019', 'EUH029', 'EUH031', 'EUH032', 'EUH206'} | {
    'H220', 'H221', 'H222', 'H223', 'H224', 'H225', 'H226', 'H228', 'H229', 'H280'}
FLAMMABLE = {'H220', 'H221', 'H222', 'H223', 'H224', 'H225', 'H226', 'H228'}
WATER_REACTIVE = {'H260', 'H261', 'EUH014', 'EUH029'}
OXIDISER = {'H270', 'H271', 'H272'}

NO_INFO = r'no data available|not available|no information available|not determined|not applicable|no data'
CONTRADICT = r'not reactive|no (?:known )?reactivity|none known|none under normal|no hazardous reactions?|no dangerous reactions?|' + NO_INFO
REASON = r'because|due to|since|as the|not relevant|not tested|reason|based on|no reactive'

ELEMENT_NAMES = {'water': 'HO', 'hypochlorite': 'Cl O', 'sodium': 'Na', 'calcium': 'Ca', 'carbide': 'C', 'oxide': 'O',
                 'dioxide': 'O', 'silicon': 'Si', 'silica': 'Si O', 'acetone': 'C H O', 'chloride': 'Cl', 'sulfate': 'S O',
                 'nitrate': 'N O', 'phosphate': 'P O', 'phosphide': 'P', 'fluoride': 'F', 'bromide': 'Br', 'potassium': 'K'}
PRODUCT_ELEMENTS = [(r'hydrogen chloride|\bhcl\b|chlorine|chloramine|phosgene', 'Cl'), (r'hydrogen fluoride|\bhf\b', 'F'),
                    (r'hydrogen bromide|\bhbr\b|bromine', 'Br'), (r'nitrogen oxides|\bnox\b|hydrogen cyanide|\bhcn\b|ammonia', 'N'),
                    (r'sulfur oxides|sulphur oxides|\bsox\b|hydrogen sulfide|sulphide', 'S'), (r'phosphine|phosphorus oxides', 'P'),
                    (r'carbon monoxide|carbon dioxide|carbon oxides|\bco2?\b|formaldehyde|methanol|acetylene', 'C')]
METALS = {'Na', 'K', 'Ca', 'Mg', 'Al', 'Fe', 'Cu', 'Zn', 'Li', 'Ba', 'Ti', 'Cr', 'Ni', 'Pb', 'Sn', 'Mn'}


def low(s):
    return (s or '').lower()


def families_in(text, vocab=FAMILIES):
    t = low(text)
    return {k for k, rx in vocab.items() if re.search(rx, t)}


# ------------------------------------------------------------------ jurisdiction
def detect_jurisdiction(full):
    t = full[:6000] + full[-3000:]
    score = {'US': 0, 'GB': 0, 'EU': 0}
    why = {'US': [], 'GB': [], 'EU': []}
    for j, rx, w, label in [
        ('US', r'29 CFR 1910\.1200|Hazard Communication Standard|\bOSHA\b', 3, 'cites OSHA HazCom'),
        ('US', r'\b[A-Z]{2} \d{5}\b|\bUSA\b|United States', 1, 'US address'),
        ('GB', r'UK SI 2019/758|UK SI 2020/1577|GB[- ]CLP|GB REACH|UK SI 2019/720|UK SI 2020/1567', 3, 'cites GB REACH/CLP'),
        ('GB', r'UNITED KINGDOM|\b[A-Z]{1,2}\d{1,2}[A-Z]? \d[A-Z]{2}\b', 1, 'UK address'),
        ('EU', r'2020/878', 3, 'cites Reg. 2020/878'),
        ('EU', r'2015/830', 1, 'cites Reg. 2015/830 (old EU format)'),
    ]:
        if re.search(rx, t):
            score[j] += w
            why[j].append(label)
    best = max(score, key=score.get)
    return best, score, why


# ------------------------------------------------------------------ Section 10 slots
SLOT_LABELS = {
    'reactivity': r'reactiv(?:e hazard|ity)', 'stability': r'(?:chemical )?stability',
    'reactions': r'(?:possibility of )?hazardous (?:reactions|polymeri[sz]ation)', 'conditions': r'conditions to avoid',
    'incompatible': r'incompatible materials', 'decomposition': r'hazardous decomposition products',
}
NUM_SLOT = {'10.1': 'reactivity', '10.2': 'stability', '10.3': 'reactions', '10.4': 'conditions', '10.5': 'incompatible', '10.6': 'decomposition'}


def section10_slots(sec10):
    slots, numbered = {}, False
    for key, slot in NUM_SLOT.items():
        if key in sec10.get('subsections', {}):
            numbered = True
            body = sec10['subsections'][key]
            body = re.sub(r'^\s*10\.\d\.?\s*', '', body)
            body = re.sub(SLOT_LABELS[slot], '', body, count=1, flags=re.I)
            slots[slot] = ' '.join(body.split())
    if not numbered:  # labelled layout (typical US)
        text = sec10['text']
        lines = text.split('\n')[1:]
        cur = None
        for ln in lines:
            hit = None
            for slot, rx in SLOT_LABELS.items():
                m = re.match(r'\s*(' + rx + r')\b[ :]*(.*)$', ln, re.I)
                if m:
                    hit = slot
                    slots[slot] = (slots.get(slot, '') + ' ' + m.group(2)).strip()
                    break
            if hit:
                cur = hit
            elif cur and ln.strip():
                slots[cur] += ' ' + ln.strip()
    return {k: ' '.join(v.split()) for k, v in slots.items()}, numbered


# ------------------------------------------------------------------ helpers on the SDS
def classification(sds):
    s2 = sds['sections'].get('2', {}).get('text', '')
    codes = set(sds['codes_by_section'].get('2', {}).get('H', [])) | set(sds['codes_by_section'].get('2', {}).get('EUH', []))
    t = low(s2)
    for rx, code in H_TEXT:
        if re.search(rx, t):
            codes.add(code)
    return codes


def sentences(text):
    out = []
    for line in (text or '').split('\n'):
        out += [s.strip() for s in re.split(r'(?<=[.;])\s+(?=[A-Z])', line) if s.strip()]
    return out


def reaction_statements(sds):
    """Materials the SDS itself names as reacting, outside Section 10 (Sections 2, 5, 6, 7)."""
    out = {}
    for n in ('2', '5', '6', '7'):
        txt = sds['sections'].get(n, {}).get('text', '')
        for s in sentences(re.sub(r'[ \t]+', ' ', txt)):
            if re.search(r'incompatib|keep away from|store away from|separat|avoid contact with|ensure no contact|'
                         r'do not store|mixing|contact with|reacts?|liberat|releases?', s, re.I):
                head = re.split(PRODUCT_VERB, s, maxsplit=1, flags=re.I)[0] if re.search(r'mixing|contact with', s, re.I) else s
                for f in families_in(head) - {'air'}:
                    if f == 'water' and n == '7' and not re.search(r'contact with water|from water|ingress of water|protected against moisture', s, re.I):
                        continue
                    out.setdefault(f, set()).add(n)
    return out


def elements(sds):
    found = set()
    for n in ('1', '3', '9'):
        txt = sds['sections'].get(n, {}).get('text', '')
        lines = txt.split('\n')
        for i, ln in enumerate(lines):
            if re.search(r'molecular formula|\bformula\b', ln, re.I):
                for cand in lines[max(0, i - 1):i + 2]:
                    for tok in re.findall(r'\b(?:[A-Z][a-z]?\d*\s?){1,8}\b', cand.replace('Molecular Formula', '').replace('Formula', '')):
                        syms = re.findall(r'([A-Z][a-z]?)\d*', tok)
                        if syms and all(sy in PERIODIC for sy in syms) and len(''.join(syms)) <= 12:
                            found |= set(syms)
        if n == '3':
            for name, els in ELEMENT_NAMES.items():
                if re.search(r'\b' + name + r'\b', low(txt)):
                    found |= set(re.findall(r'[A-Z][a-z]?', els))
    return found


PERIODIC = set('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Ti Cr Mn Fe Co Ni Cu Zn Br Ag Sn I Ba Pb Hg Zr Mo W Pt Au'.split())


def lookups(cases, lookup_dir):
    out = {}
    for cas in cases:
        p = os.path.join(lookup_dir, f'lookup_{cas}.json')
        if os.path.exists(p):
            out[cas] = json.load(open(p))
    return out


def reference_statements(lk):
    """(source, text) pairs describing reactions, from ICSC / CAMEO / NIOSH lookups."""
    out = []
    for r in lk.get('results', []):
        if r['source'] == 'ICSC' and r['status'] == 'ok':
            for c in r['cards']:
                out.append((f"ICSC {c['card']}", c.get('chemical_dangers') or '', c.get('url')))
        if r['source'] == 'CAMEO Chemicals' and r['status'] == 'ok':
            for d in r['datasheets']:
                out.append((f"CAMEO {d['id']}", (d.get('reactivity_profile') or '') + ' ' + (d.get('air_water_reactions') or ''), d.get('url')))
        if r['source'] == 'NIOSH Pocket Guide' and r['status'] == 'ok':
            out.append(('NIOSH', 'Incompatible with: ' + (r.get('incompatibilities') or ''), r.get('url')))
    return out


def reacting_families(text):
    """Return {family_or_reagent: violent?} for one reference text, ignoring products and 'such as' examples."""
    res = {}
    sents = sentences(' '.join(text.split()))
    for i, s in enumerate(sents):
        nxt = sents[i + 1] if i + 1 < len(sents) and re.match(r'This\b', sents[i + 1]) else ''
        violent = bool(re.search(VIOLENT, s + ' ' + nxt, re.I))
        if re.match(r'This\b', s) or re.search(r'\b(?:in)?solub|miscib', s, re.I):
            continue
        s2 = re.sub(r'(\b(?:oxidants?|oxidi[sz]ers?|oxidi[sz]ing agents?|acids?|bases?)\s+such as\b)[^.]*', r'\1', s, flags=re.I)
        head = re.split(PRODUCT_VERB, s2, maxsplit=1, flags=re.I)[0]
        if re.search(r'^(?:an? (?:base|acid|oxidi|reduc)|the (?:substance|solution)[^.]* is an? |generally|salts of)', head, re.I) and not re.search(VIOLENT, head, re.I):
            head = ''
        for f in families_in(head) | {('reagent', k) for k in families_in(head, REAGENTS)}:
            res[f] = res.get(f, False) or violent
    return res


# ------------------------------------------------------------------ the checks
def run(sds, lookup_dir, declared, sds_type):
    full = open(os.path.join(os.path.dirname(sds['_path']), 'sds.txt'), encoding='utf-8').read()
    findings = []

    def add(section, cid, status, says, expected, source):
        findings.append({'section': section, 'check': cid, 'status': status, 'sds_says': says[:300], 'expected': expected, 'source': source})

    detected, score, why = detect_jurisdiction(full)
    juris = {'declared': declared, 'detected': detected, 'scores': score, 'evidence': why[detected],
             'mismatch': bool(declared and declared != detected)}
    J = declared or detected
    EUGB = J in ('EU', 'GB')

    sec10 = sds['sections'].get('10')
    if not sec10:
        add('10', '10-A1', 'fail', 'Section 10 not found', 'Section 10 "Stability and reactivity"', 'Annex II Part B / 1910.1200(g)(2)(x)')
        return {'jurisdiction': juris, 'findings': findings}
    slots, numbered = section10_slots(sec10)
    s10 = ' '.join(sec10['text'].split())
    H = classification(sds)
    cas = sds['codes_all']['CAS']
    lk = lookups(cas, lookup_dir)
    aqueous = '7732-18-5' in cas or re.search(r'\bsolution\b', low(sds['sections'].get('1', {}).get('text', '')))
    incompatible = slots.get('incompatible', '')
    have10 = families_in(incompatible) | families_in(slots.get('reactions', ''))

    # ---- A: required content
    if EUGB:
        missing = [k for k in NUM_SLOT if k not in sec10['subsections']]
        if missing:
            add('10', '10-A2', 'fail', 'Subheadings missing: ' + ', '.join(missing), 'Numbered 10.1-10.6', 'Annex II Part B')
        blanks = [k for k, sl in NUM_SLOT.items() if k in sec10['subsections'] and not slots.get(sl)]
        if blanks:
            add('10', '10-A4', 'fail', 'Blank: ' + ', '.join(blanks), 'No blank subsections', 'Annex II 0.4')
        noreason = [k for k, sl in NUM_SLOT.items() if re.search(NO_INFO, low(slots.get(sl))) and not re.search(REASON, low(slots.get(sl)))]
        if noreason:
            add('10', '10-A5', 'fail', '; '.join(f'{k}: "{slots[NUM_SLOT[k]][:60]}"' for k in noreason),
                'A reason for each "no data"/"not applicable" (one consolidated finding)', 'Annex II s.10 preamble')
    else:
        absent = [sl for sl in NUM_SLOT.values() if sl not in slots]
        if absent:
            add('10', '10-A3', 'fail', 'Elements missing: ' + ', '.join(absent), 'All six App D elements', 'App D Table D.1 s.10')
    r1 = slots.get('reactivity', '')
    if len(r1) < 60 and not (families_in(r1) or re.search(r'react|decompos|explo|flammab|corros', low(r1)) and len(r1) > 25):
        add('10', '10-A7', 'warning', r1 or '(empty)', 'Reactivity hazards described for this product', 'Annex II 10.1.1 / App D s.10(a)')
    if not re.search(r'\bstable\b|\bunstable\b|stability', low(slots.get('stability', ''))):
        add('10', '10-A9', 'fail', slots.get('stability', '(empty)'), 'Stable/unstable under normal conditions stated', 'Annex II 10.2 / App D s.10(b)')
    if J == 'US' and not re.search(r'fire|emergenc|spill|mix|contact with|heat', low(slots.get('reactions', ''))):
        hcs2024 = re.search(r'Hazard Communication Standard 2024|HCS 2024|1910\.1200, 2024', full)
        status = 'warning' if (sds_type == 'substance' or hcs2024) else 'info'
        add('10', '10-A12', status, slots.get('reactions', '(empty)'),
            'Hazardous reactions incl. foreseeable emergencies' + (' (SDS declares HazCom 2024)' if hcs2024 else ''),
            'App D s.10(c); 1910.1200(j)')

    # ---- B: classification-driven
    reactive = H & REACTIVITY_CLASS
    bad = []
    for sl, label in (('reactivity', '10.1'), ('reactions', '10.3')):
        if reactive and re.search(CONTRADICT, low(slots.get(sl))):
            bad.append(f'{label}: "{slots.get(sl, "")[:70]}"')
    if re.search(r'\byes\b|\breactive\b', low(r1)) and re.search(r'none|no hazardous', low(slots.get('reactions', ''))):
        bad.append('10.1 says reactive but 10.3 says none')
    if H & UNSTABLE_CLASS and re.fullmatch(r'\W*stable under normal conditions\W*', low(slots.get('stability', ''))):
        bad.append('10.2 unqualified "stable"')
    if H & FIRE_CLASS and re.search(r'^\W*(?:none|no data available|not applicable)\W*$', low(slots.get('conditions', ''))):
        bad.append('10.4 "none"')
    if bad:
        add('10', '10-B1', 'fail', '; '.join(bad), f'No contradiction with classification ({", ".join(sorted(reactive or H))})',
            'Annex II 0.2.4 / 1910.1200(g)(5)')
    if H & FLAMMABLE:
        c = low(slots.get('conditions', ''))
        if not re.search(r'heat|spark|flame|ignition|hot surface', c):
            add('10.4', '10-B2', 'fail', slots.get('conditions', ''), 'Heat and ignition sources (P210)', 'CLP Annex IV P210')
        elif H & {'H224', 'H225', 'H226'} and not re.search(r'static|electrostatic', low(s10)) and re.search(r'static', low(full)):
            add('10.4', '10-B2', 'warning', slots.get('conditions', ''), 'Static discharge (volatile liquid; P240/P243 conditions)',
                'CLP Annex IV P240/P243')
    if H & WATER_REACTIVE:
        if 'water' not in families_in(incompatible):
            add('10.5', '10-B10', 'fail', incompatible, 'Water listed in 10.5', 'Annex II 10.5; H260/H261/EUH014/EUH029')
        if not re.search(r'moist|humid|water vapou?r|water', low(s10.replace(incompatible, ''))):
            add('10.4', '10-B10', 'warning', slots.get('conditions', ''), 'Moisture listed as a condition to avoid', 'P232, P402+P404')
        if not re.search(r'acetylene|hydrogen|phosphine|flammable gas|gas', low(s10)):
            add('10.3', '10-B10', 'warning', slots.get('reactions', ''), 'Gas released on contact with water named somewhere in Section 10', 'H260/H261')
    if H & OXIDISER and 'combustibles' not in have10:
        add('10.5', '10-B11', 'fail', incompatible, 'Combustible materials (P220)', 'CLP Annex IV P220')
    if 'H290' in H and 'metals' not in have10:
        add('10.5', '10-B12', 'warning', incompatible, 'Metals attacked', 'H290; Annex II 10.1.2')

    # ---- C: cross-section
    named = reaction_statements(sds)
    c1 = sorted(f for f, secs in named.items() if '7' in secs and f not in have10)
    if c1:
        add('10.5 ↔ 7', '10-C1', 'fail', 'Section 7 names: ' + ', '.join(c1) + ' | 10.5: ' + incompatible[:120],
            'Everything Section 7 keeps the product away from is in 10.5', 'Annex II 7.2, 10.5 / App D s.7(b), s.10(e)')
    c8 = sorted(f for f, secs in named.items() if not ('7' in secs) and f not in have10 and not (f == 'water' and aqueous))
    if c8:
        add('10.5 ↔ 2/5/6', '10-C8', 'fail', 'Named in Section(s) ' + ', '.join(sorted({s for f in c8 for s in named[f]})) + ': ' + ', '.join(c8),
            'Every material the SDS names as reactive appears in 10.5/10.3', 'SDS Sections 2, 5, 6')
    s7 = low(' '.join(sds['sections'].get('7', {}).get('text', '').split()))
    c2 = []
    for cond, rx7, rx10 in (('light/sunlight', r'sunlight|\blight\b|dark', r'sunlight|\blight\b'),
                            ('moisture', r'protect(?:ed)? (?:from|against) moisture|dry place', r'moist|water'),
                            ('heat', r'\bcool\b|refrigerat|heat', r'heat|temperature'),
                            ('static discharge', r'static', r'static')):
        if re.search(rx7, s7) and not re.search(rx10, low(s10)):
            if cond == 'static discharge' and any(f['check'] == '10-B2' for f in findings):
                continue
            c2.append(cond)
    if c2:
        add('10.4 ↔ 7', '10-C2', 'warning', 'Section 7 sets: ' + ', '.join(c2), 'Same conditions named in Section 10', 'Annex II 7, 10.4')
    s9 = ' '.join(sds['sections'].get('9', {}).get('text', '').split())
    m = re.search(r'decomposition temperature\s*([<>≥≤]?\s*-?\d+(?:\.\d+)?)\s*°?\s*C', s9, re.I)
    if m and re.search(r'\bstable\b', low(slots.get('stability', ''))):
        val = float(re.sub(r'[^\d.\-]', '', m.group(1)))
        if val <= 50:
            add('10 ↔ 9', '10-C3', 'warning', f'9: decomposition temperature {m.group(1).strip()} °C; 10.2: {slots.get("stability", "")[:60]}',
                'Consistent decomposition data (value implausible or conflicts with "stable"): needs verification', 'Annex II 9.1 / App D s.9')
    els = elements(sds)
    dec = low(slots.get('decomposition', ''))
    need = {e for rx, e in PRODUCT_ELEMENTS if re.search(rx, dec)}
    if els and need - els:
        add('10.6 ↔ 3', '10-C4', 'warning', f'10.6: {slots.get("decomposition", "")[:120]} | composition elements: {"".join(sorted(els))}',
            f'Product(s) need {", ".join(sorted(need - els))}, not in Section 3: undeclared impurity or copy-paste; verify', 'By Section element rule')
    thermal = m or re.search(r'thermal decomposition|on heating|excess heat|\bheat\b', low(s10 + ' ' + sds['sections'].get('5', {}).get('text', '')))
    if thermal and els:
        miss = []
        if 'C' in els and 'C' not in need and not (H & FLAMMABLE and False):
            miss.append('C → CO/CO₂')
        for x in ('N', 'S', 'P'):
            if x in els and x not in need:
                miss.append({'N': 'N → NOx', 'S': 'S → SOx', 'P': 'P → phosphorus oxides'}[x])
        if els & {'Cl', 'F', 'Br', 'I'} and not need & {'Cl', 'F', 'Br', 'I'}:
            miss.append('halogen → HX or X₂')
        if miss:
            add('10.6 ↔ 3', '10-C5', 'warning', slots.get('decomposition', '')[:120], 'Expected by element: ' + '; '.join(miss), 'By Section element rule')
        metal = els & METALS
        if metal and not (H & FLAMMABLE) and not re.search(r'metal oxide|oxide', dec):
            add('10.6 ↔ 3', '10-C5', 'info', slots.get('decomposition', '')[:120],
                f'Metal oxides ({", ".join(sorted(metal))}) not expected: product is not combustible', 'By Section element rule (tuned)')
    m14 = re.search(r'(?:hazard class|transport hazard class(?:es)?|UN classification)\s*\(?e?s?\)?\s*(\d(?:\.\d)?)', ' '.join(sds['sections'].get('14', {}).get('text', '').split()), re.I)
    if m14:
        cls = m14.group(1)
        if cls == '4.3' and 'water' not in families_in(incompatible):
            add('10 ↔ 14', '10-C6', 'warning', f'Class {cls}; 10.5: {incompatible[:80]}', 'Water in 10.5', 'ADR / Section 14')
        if cls == '5.1' and 'combustibles' not in have10:
            add('10 ↔ 14', '10-C6', 'warning', f'Class {cls}', 'Combustibles in 10.5', 'ADR / Section 14')
    nfpa = re.search(r'Instability\s+(?:Physical hazards\s+)?\d\s+\d\s+(\d)', full)
    # linked checks owned by other sections
    s5 = ' '.join(sds['sections'].get('5', {}).get('text', '').split())
    suitable = re.split(r'unsuitable|must not be used', s5, flags=re.I)[0]
    if (H & WATER_REACTIVE or 'water' in families_in(incompatible) and not aqueous):
        if not re.search(r'water', re.split(r'suitable extinguishing media|extinguishing media', s5, flags=re.I)[-1], re.I) or re.search(r'water spray|water jet|foam', low(suitable)):
            add('5.1 ↔ 10', '5-C1', 'fail', s5[:150], 'Water listed as unsuitable; no water/water-based foam as suitable', 'Annex II 5.1 / App D s.5(a)')
    m52 = re.search(r'(?:hazardous combustion products|special hazards arising|specific hazards arising)(.{0,400})', s5, re.I)
    if m52:
        p52 = low(m52.group(1))
        n52 = {e for rx, e in PRODUCT_ELEMENTS if re.search(rx, p52)}
        if els & {'Cl', 'F', 'Br', 'I'} and not n52 & {'Cl', 'F', 'Br', 'I'}:
            add('5.2', '5-C2', 'fail', m52.group(1)[:150], 'A halogen-containing combustion product (HX or X₂)', 'Annex II 5.2 / 10.6')
        elif 'C' in els and 'C' not in n52:
            add('5.2', '5-C2', 'warning', m52.group(1)[:150], 'Carbon oxides named (generic "toxic fumes" is not enough)', 'Annex II 5.2 / 10.6')
    s6 = ' '.join(sds['sections'].get('6', {}).get('text', '').split())
    absorb_bad = []
    for cas_, d in lk.items():
        for r in d['results']:
            if r['source'] == 'CAMEO Chemicals' and r['status'] == 'ok':
                for ds in r['datasheets']:
                    a = ds.get('incompatible_absorbents') or ''
                    if a and not a.lower().startswith('no information'):
                        absorb_bad.append(re.sub(r'.*situations to watch out for\.\.\.\s*', '', a))
    if absorb_bad and re.search(r'inert absorbent|absorbent material', low(s6)):
        oxid_or_wr = bool(H & (OXIDISER | WATER_REACTIVE)) or 'water' in families_in(incompatible) and not aqueous
        add('6.3', '6-C1', 'warning' if oxid_or_wr else 'info', 'Generic "inert absorbent"',
            'Name a compatible absorbent; CAMEO flags: ' + '; '.join(sorted(set(absorb_bad)))[:150], 'CAMEO absorbent data')
    s72 = sds['sections'].get('7', {}).get('subsections', {}).get('7.2', s7)
    fam10 = families_in(incompatible)
    if fam10 and not families_in(s72) and not re.search(r'section 10|10\.5', low(s72)):
        add('7.2', '7-C1', 'warning', ' '.join(s72.split())[:150], 'Segregation for: ' + ', '.join(sorted(fam10)) + ' (or a cross-reference to 10.5)', 'Annex II 7.2')

    # ---- D: data spot-checks
    reported = {f for x in findings if x['check'] in ('10-C1', '10-C8') for f in re.findall(r'[a-z ]+', x['sds_says'].split(':', 1)[-1].split('|')[0]) for f in [f.strip()]}
    fails, warns, srcs = set(), set(), []
    for cas_, d in lk.items():
        if cas_ == '7732-18-5':  # water as diluent: its own reactivity is not the product's
            continue
        for src, txt, url in reference_statements(d):
            for f, violent in reacting_families(txt).items():
                name = f[1] if isinstance(f, tuple) else f
                if name in have10 or name in reported:
                    continue
                if name == 'water' and aqueous:
                    continue
                if isinstance(f, tuple):
                    if not re.search(REAGENTS[name], low(incompatible)):
                        warns.add(name)
                        srcs.append(src)
                elif violent and src != 'NIOSH':
                    fails.add(name)
                    srcs.append(src)
                else:
                    warns.add(name)
                    srcs.append(src)
    warns -= fails
    if fails or warns:
        add('10.5', '10-D1', 'fail' if fails else 'warning', incompatible[:150],
            ('Recorded violent/explosive/gas-releasing reaction with: ' + ', '.join(sorted(fails)) + '. ' if fails else '')
            + ('Also listed: ' + ', '.join(sorted(warns)) if warns else ''), ', '.join(sorted(set(srcs))))
    for cas_, d in lk.items():
        for r in d['results']:
            if r['source'] == 'GESTIS' and r.get('entries') and cas_ != '7732-18-5':
                add('10', '10-D1 (GESTIS)', 'not checked', '', 'Manual review: ' + r['entries'][0]['url'], 'GESTIS (manual link)')
    return {'jurisdiction': juris, 'H': sorted(H), 'elements': sorted(els), 'slots': slots, 'findings': findings}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sds_json')
    ap.add_argument('lookup_dir')
    ap.add_argument('--declared', choices=['EU', 'GB', 'US'])
    ap.add_argument('--type', choices=['substance', 'mixture'], required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    sds = json.load(open(a.sds_json))
    sds['_path'] = a.sds_json
    res = run(sds, a.lookup_dir, a.declared, a.type)
    j = res['jurisdiction']
    print(f"jurisdiction: declared={j['declared']} detected={j['detected']} ({'; '.join(j['evidence'])})" + ('  ** MISMATCH **' if j['mismatch'] else ''))
    for f in res['findings']:
        print(f"  {f['check']:<16} {f['status']:<11} {f['sds_says'][:90]!r} -> {f['expected'][:110]}")
    if a.out:
        json.dump(res, open(a.out, 'w'), indent=1, ensure_ascii=False)
