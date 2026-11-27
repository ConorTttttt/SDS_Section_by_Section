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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedupe import dedupe  # noqa: E402

# Checklist rows this engine implements (checked against checklist/coverage.csv by tools/check_coverage.py)
CODED = ({f'10-A{i}' for i in range(1, 17)} | {f'10-B{i}' for i in range(1, 18)} | {f'10-C{i}' for i in range(1, 9)}
         | {'10-D1', '10-D4', '10-D5', '10-D6', '10-J1', '5-C1', '5-C2', '6-C1', '7-C1'})

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
SPECIFIC = {  # named materials -> the families they belong to (a family already in 10.5 => 'name explicitly' warning)
    'nitric acid': {'acids', 'oxidisers'}, 'perchloric acid': {'acids', 'oxidisers'}, 'sulfuric acid': {'acids'},
    'acetic acid': {'acids'}, 'hydrogen chloride': {'acids'}, 'hydrochloric acid': {'acids'},
    'hydrogen peroxide': {'oxidisers'}, 'sodium peroxide': {'oxidisers'}, 'chlorine': {'halogens', 'oxidisers'},
    'bromine': {'halogens', 'oxidisers'}, 'fluorine': {'halogens', 'oxidisers'}, 'iodine': {'halogens'},
    'chloroform': {'halogenated compounds'}, 'bromoform': {'halogenated compounds'},
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
    (r'heating may cause an explosion', 'H240'), (r'heating may cause a fire or explosion', 'H241'), (r'heating may cause a fire(?! or explosion)', 'H242'),
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
                m_with = re.search(r'(?:contact with|mixing (?:this product )?with|mixed with|reacts? (?:\w+ )?with|away from|separated from|incompatible with)\s+(.*)', s, re.I)
                head = re.split(PRODUCT_VERB, m_with.group(1) if m_with else s, maxsplit=1, flags=re.I)[0]
                if not m_with and re.search(r'^(?:strong )?oxidi[sz]|^[^.]* is an? ', head, re.I):
                    continue
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
        if re.search(r'^(?:an? (?:base|acid|oxidi|reduc)|the (?:substance|solution)[^.]* is an? |[\w ,()\-]+ is an? (?:\w+ )?(?:reduc|oxidi|base|acid)|generally|salts of)', head, re.I) and not re.search(VIOLENT, head, re.I):
            head = ''
        for name in SPECIFIC:
            if re.search(r'\b' + name + r'\b', head, re.I):
                res[('specific', name)] = res.get(('specific', name), False) or violent
                head = re.sub(r'\b' + name + r'\b', ' ', head, flags=re.I)
        for f in families_in(head) | {('reagent', k) for k in families_in(head, REAGENTS)}:
            res[f] = res.get(f, False) or violent
    return res


# ------------------------------------------------------------------ the checks
def run(sds, lookup_dir, declared, sds_type):
    full = open(os.path.join(os.path.dirname(sds['_path']), 'sds.txt'), encoding='utf-8').read()
    findings = []

    def add(section, cid, status, says, expected, source, items=None, prefix=None, suffix=''):
        f = {'section': section, 'check': cid, 'status': status, 'sds_says': says[:300], 'expected': expected, 'source': source}
        if items:
            f.update(items=items, prefix=prefix, suffix=suffix)
        findings.append(f)

    detected, score, why = detect_jurisdiction(full)
    juris = {'declared': declared, 'detected': detected, 'scores': score, 'evidence': why[detected],
             'mismatch': bool(declared and declared != detected)}
    J = declared or detected
    EUGB = J in ('EU', 'GB')
    if juris['mismatch']:
        add('All', '10-J1', 'warning', f"Detected {detected} ({'; '.join(why[detected])})", f'Declared {declared}; checks run as {declared}', 'Run rule')

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
            bad.append(('contra:' + label, f'{label}: "{slots.get(sl, "")[:70]}"'))
    if re.search(r'^\W*yes\b|reactive hazard\W*yes|(?<!not )\bis reactive\b', low(r1)) and re.search(r'^\W*none\b|none under normal|no hazardous reactions?|(?<!polymerization )does not occur\W*$', low(slots.get('reactions', ''))):
        bad.append(('contra:self', '10.1 says reactive but 10.3 says none'))
    if H & UNSTABLE_CLASS and re.fullmatch(r'\W*stable(?: under normal conditions)?\W*', low(slots.get('stability', ''))):
        bad.append(('stab:unstable', '10.2 unqualified "stable"'))
    if H & FIRE_CLASS and re.search(r'^\W*(?:none|no data available|not applicable)\W*$', low(slots.get('conditions', ''))):
        bad.append(('contra:10.4', '10.4 "none"'))
    if bad:
        add('10', '10-B1', 'fail', '; '.join(t for _, t in bad), f'No contradiction with classification ({", ".join(sorted(reactive or H))})',
            'Annex II 0.2.4 / 1910.1200(g)(5)', items=[{'key': k, 'status': 'fail', 'text': t} for k, t in bad],
            prefix=f'No contradiction with classification ({", ".join(sorted(reactive or H))}): ')
    if H & FLAMMABLE:
        c = low(slots.get('conditions', ''))
        if not re.search(r'heat|spark|flame|ignition|hot surface', c):
            add('10.4', '10-B2', 'fail', slots.get('conditions', ''), 'Heat and ignition sources (P210)', 'CLP Annex IV P210')
        elif H & {'H224', 'H225', 'H226'} and not re.search(r'static|electrostatic', low(s10)) and re.search(r'static', low(full)):
            add('10.4', '10-B2', 'warning', slots.get('conditions', ''), 'Static discharge (volatile liquid; P240/P243 conditions)',
                'CLP Annex IV P240/P243', items=[{'key': 'cond:static discharge', 'text': 'static discharge'}], prefix='Static discharge (volatile liquid; P240/P243 conditions): ')
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

    # ---- rows added 27 Nov 2026 (A6, A8, A10, A11, A13-A16, B3-B9, B13-B17)
    s2t = low(' '.join(sds['sections'].get('2', {}).get('text', '').split()))
    sx = {n: low(' '.join(sds['sections'].get(n, {}).get('text', '').split())) for n in ('1', '3', '7', '9', '14')}
    st10, re10, co10, dec10 = low(slots.get('stability')), low(slots.get('reactions')), low(slots.get('conditions')), low(slots.get('decomposition'))

    def items_add(section, cid, status, says, prefix, wants, source):
        if wants:
            add(section, cid, status, says, prefix + '; '.join(t for _, t in wants), source,
                items=[{'key': k, 'status': status, 'text': t} for k, t in wants], prefix=prefix)
    if J == 'US':
        empty = [sl for sl in NUM_SLOT.values() if sl in slots and not slots[sl]]
        if empty:
            add('10', '10-A6', 'fail', 'Empty: ' + ', '.join(empty), 'Mark "no applicable information available"', '1910.1200(g)(3); App D intro')
    if EUGB and sds_type == 'mixture' and re.search(NO_INFO + r'|none known', low(r1)) and not re.search(r'component|ingredient|substance', low(s10)):
        add('10.1', '10-A8', 'warning', r1, 'With no mixture-level data, data on the component substances', 'Annex II 10.1.2')
    if re.search(r'stabili[sz]|inhibit', sx['1'] + ' ' + sx['3'] + ' ' + sx['7']) and not re.search(r'stabili[sz]|inhibit', st10):
        st = 'fail' if EUGB else 'warning'
        add('10.2', '10-A10', st, slots.get('stability', ''), 'Name the stabiliser/inhibitor (named in Sections 1, 3 or 7) and any condition it depends on',
            'Annex II 10.2', items=[{'key': 'stab', 'status': st, 'text': 'name the stabiliser/inhibitor'}], prefix='Name the stabiliser/inhibitor (named in Sections 1, 3 or 7): ')
    if EUGB and re.search(r'polymeri', sx['7'] + ' ' + sx['9'] + ' ' + s2t) and not re.search(r'polymeri', re10):
        add('10.3', '10-A11', 'fail', slots.get('reactions', ''), 'Say whether hazardous polymerisation may occur and under what conditions (polymerisation is named elsewhere in the SDS)',
            'Annex II 10.3', items=[{'key': 'react:polymer', 'status': 'fail', 'text': 'hazardous polymerisation'}], prefix='10.3 must address: ')
    elif EUGB and (H & REACTIVITY_CLASS) and not slots.get('reactions'):
        add('10.3', '10-A11', 'fail', '', 'Describe the hazardous reactions for a reactivity class (' + ', '.join(sorted(H & REACTIVITY_CLASS)) + ')', 'Annex II 10.3')
    fire_only = re.search(r'fire|combustion|burning', dec10) and not re.search(r'heat|decompos|storage|use|spill', dec10.replace('in case of fire', ''))
    if fire_only:
        add('10.6', '10-A13' if EUGB else '10-A14', 'warning' if EUGB else 'info', slots.get('decomposition', ''),
            'Decomposition products from use, storage, spill and heating (fire products belong in 5.2)', 'Annex II 10.6' if EUGB else 'App D s.10(f)')
    m15 = re.search(r'(?:sadt|decomposition (?:onset )?temperature|self-accelerating decomposition temperature)[^.]{0,40}?\d+(?:[.,]\d+)?\s*°\s*c(.{0,80})', sx['9'] + ' ' + s10.lower())
    if EUGB and m15 and not re.search(r'method|test|\bun\b|h\.[1-4]|oecd|astm|dsc|\ben ?\d', m15.group(1)):
        add('9/10', '10-A15', 'info', '', 'Cite the test method for the quoted SADT/decomposition value', 'Annex II s.10 preamble')
    if J == 'EU' and re.search(r'nanoform', sx['1'] + ' ' + sx['3'] + ' ' + sx['9']) and 'nanoform' not in s10.lower():
        add('10', '10-A16', 'warning', '', 'Say which nanoform each Section 10 statement applies to', 'Annex II 0.1.3')
    if H & {'H280', 'H229', 'H222', 'H223'}:
        items_add('10.3/10.4', '10-B3', 'warning', s10[:120], 'Gases under pressure/aerosols: ',
                  [(k, t) for k, t, ok in (('cond:heat', '10.4 heating' + (' (aerosols: above 50 °C, P412)' if H & {'H229', 'H222', 'H223'} else ''), re.search(r'heat|temperature', co10)),
                                           ('react:burst', '10.3 container may burst or explode if heated', re.search(r'burst|explo|rupture', re10 + ' ' + s10.lower())))
                   if not ok], 'H229/H280 wording; P412')
    if H & {'H230', 'H231'}:
        items_add('10.2-10.4', '10-B4', 'fail', s10[:120], 'Chemically unstable gas: ',
                  [(k, t) for k, t, ok in (('stab:unstable', '10.2 states instability', re.search(r'unstable|instab', st10)),
                                           ('react:explosive', '10.3 may react explosively even without air' + (' (at elevated pressure and/or temperature)' if 'H231' in H else ''),
                                            re.search(r'explo', re10) and ('H231' not in H or re.search(r'pressure|temperature', re10))),
                                           ('cond:unstable', '10.4 gives the pressure/temperature conditions', re.search(r'pressure|temperature', co10)))
                   if not ok], 'H230/H231 wording; P202')
    if H & {'H200', 'H201', 'H202', 'H203', 'H204', 'H205'}:
        P2 = set(sds['codes_by_section'].get('2', {}).get('P', []))
        P2 = {c for combo in P2 for c in combo.split('+')}
        wants = [(k, t) for k, t, ok in (('react:explosive', '10.1 describes the explosive hazard', re.search(r'explo', r1.lower())),
                                         ('cond:heat', '10.4 heat and ignition sources (P210)', re.search(r'heat|ignition|flame|spark', co10)),
                                         ('cond:shock', '10.4 shock, friction, grinding (P250 on label)', 'P250' not in P2 or re.search(r'shock|friction|grind|impact', co10)),
                                         ('cond:static discharge', '10.4 static discharge (P240 on label)', 'P240' not in P2 or re.search(r'static', co10)),
                                         ('cond:drying', '10.4 drying out (P230 on label)', 'P230' not in P2 or re.search(r'dry|wet', co10))) if not ok]
        items_add('10.1/10.4', '10-B5', 'fail', s10[:120], 'Explosive: ', wants, 'CLP Annex IV P210, P230, P240, P250 conditions')
    if H & {'H206', 'H207', 'H208'}:
        if J == 'EU':
            items_add('10.2/10.4', '10-B6', 'fail', s10[:120], 'Desensitised explosive (EU 2020/878): ',
                      [(k, t) for k, t, ok in (('stab:shelf', '10.2 shelf life', re.search(r'shelf', st10)),
                                               ('stab:verify', '10.2 how to verify desensitisation', re.search(r'verif|check', st10)),
                                               ('stab:removal', '10.2 removal of the agent turns it into an explosive', re.search(r'remov|loss', st10) and re.search(r'explos', st10)),
                                               ('cond:agent', '10.4 measures against loss of the desensitising agent', re.search(r'desensiti|wet|dry', co10))) if not ok],
                      'EU REACH Annex II 10.2/10.4')
        elif not re.search(r'desensiti|wet|dry', co10):
            add('10.4', '10-B6', 'warning', slots.get('conditions', ''), 'Loss of the desensitising agent as a condition to avoid (P212, P230)', 'CLP Annex IV P212, P230')
    if H & {'H240', 'H241', 'H242'}:
        lab = re.search(r'store at temperatures not exceeding\s*(-?\d+(?:[.,]\d+)?)\s*°\s*c', s2t)
        ctrl = re.search(r'control temperature\s*:?\s*(-?\d+(?:[.,]\d+)?)\s*°\s*c', sx['14'])
        need = lab or ctrl
        tval = (lab or ctrl).group(1).replace(',', '.') if need else None
        t10 = re.findall(r'(-?\d+(?:[.,]\d+)?)\s*°\s*c', co10)
        wants = [(k, t) for k, t, ok in (('stab:unstable', '10.2 states the conditions under which it is stable', re.search(r'only|under|at or below|provided|when stored|temperature|condition', st10)),
                                         ('react:sadt', '10.3 describes self-accelerating decomposition', re.search(r'self-accelerating|decompos', re10)),
                                         ('cond:heat', '10.4 lists heat', re.search(r'heat|temperature', co10)),
                                         ('cond:temp', f'10.4 gives the maximum temperature ({tval} °C per P411/control temperature)',
                                          not need or any(abs(float(x.replace(',', '.')) - float(tval)) < 0.01 for x in t10))) if not ok]
        items_add('10.2-10.4', '10-B7', 'fail', s10[:120], 'Self-reactive/organic peroxide: ', wants, 'H240-H242 wording; CLP Annex IV P411 (Annex I 2.8.2.4/2.15.2.3)')
    if H & {'H250', 'H232'} and not re.search(r'\bair\b|oxygen', co10 + ' ' + low(incompatible)):
        add('10.4/10.5', '10-B8', 'fail', slots.get('conditions', ''), 'Exposure to air in 10.4 or 10.5 (pyrophoric)', 'H250/H232 wording; P222, P231',
            items=[{'key': 'fam:air', 'status': 'fail', 'text': 'air'}], prefix='Exposure to air in 10.4 or 10.5 (pyrophoric): ')
    if H & {'H251', 'H252'}:
        items_add('10.3/10.4', '10-B9', 'warning', s10[:120], 'Self-heating: ',
                  [(k, t) for k, t, ok in (('react:selfheat', '10.3 self-heating can lead to ignition', re.search(r'self-heat|ignit|spontaneous', re10)),
                                           ('cond:heat', '10.4 heat / bulk quantities', re.search(r'heat|temperature|bulk|large quantit', co10))) if not ok], 'H251/H252 wording; P413')
    if 'EUH019' in H and not re.search(r'peroxide', st10 + ' ' + re10):
        add('10.2/10.3', '10-B13', 'fail', (slots.get('stability', '') + ' | ' + slots.get('reactions', ''))[:150], 'Say that explosive peroxides may form and under what conditions (EUH019)', 'EUH019 wording',
            items=[{'key': 'react:peroxide', 'status': 'fail', 'text': 'peroxide formation'}], prefix='10.2/10.3 must address: ')
    if 'EUH044' in H and not re.search(r'confine', co10):
        add('10.4', '10-B14', 'fail', slots.get('conditions', ''), 'Heating under confinement as a condition to avoid (EUH044)', 'EUH044 wording')
    if H & {'EUH031', 'EUH032'}:
        items_add('10.3/10.5', '10-B15', 'fail', s10[:120], 'Contact with acids liberates (very) toxic gas: ',
                  [(k, t) for k, t, ok in (('fam:acids', '10.5 lists acids', 'acids' in families_in(incompatible)),
                                           ('react:gas', '10.3 names the gas released', re.search(r'gas|hydrogen|cyanide|sulphide|sulfide|chlorine|phosphine', re10))) if not ok], 'EUH031/EUH032 wording')
    if 'EUH206' in H:
        items_add('10.3/10.5', '10-B15', 'fail', s10[:120], 'Active chlorine (EUH206): ',
                  [(k, t) for k, t, ok in (('react:chlorine', '10.3 names chlorine release when mixed with other products', re.search(r'chlorine', re10)),
                                           ('fam:other-products', '10.5 names the products it must not be mixed with (e.g. acids)', re.search(r'acid|other products|cleaning', low(incompatible)))) if not ok], 'EUH206 wording')
    if H & {'EUH018', 'EUH209', 'EUH209A'} and not re.search(r'vapou?r|flammab', re10 + ' ' + co10):
        add('10.3/10.4', '10-B16', 'warning', s10[:120], 'Address flammable vapour-air mixtures / becoming flammable in use (EUH018, EUH209/209A)', 'EUH018, EUH209/209A wording')
    if 'EUH207' in H and not re.search(r'fume|cadmium', dec10):
        add('10.6', '10-B16', 'warning', slots.get('decomposition', ''), 'Fumes formed during use (EUH207)', 'EUH207 wording')
    if re.search(r'combustible dust|dust explosion|explosible dust', s2t + ' ' + sx['9']) and not re.search(r'dust', re10 + ' ' + co10):
        add('10.3/10.4', '10-B17', 'warning', s10[:120], 'Dust-explosion potential (10.3) and dust formation/accumulation and ignition sources (10.4)', '1910.1200(c); EU Annex II 9.2.2; ATEX/DSEAR')

    # ---- C: cross-section
    named = reaction_statements(sds)
    c1 = sorted(f for f, secs in named.items() if '7' in secs and f not in have10)
    if c1:
        add('10.5 ↔ 7', '10-C1', 'fail', 'Section 7 names: ' + ', '.join(c1) + ' | 10.5: ' + incompatible[:120],
            'Everything Section 7 keeps the product away from is in 10.5. Missing: ' + ', '.join(c1), 'Annex II 7.2, 10.5 / App D s.7(b), s.10(e)',
            items=[{'key': 'fam:' + f, 'text': f, 'status': 'fail'} for f in c1], prefix='Everything Section 7 keeps the product away from is in 10.5. Missing: ')
    c8 = sorted(f for f, secs in named.items() if not ('7' in secs) and f not in have10 and not (f == 'water' and aqueous))
    if c8:
        add('10.5 ↔ 2/5/6', '10-C8', 'fail', 'Named in Section(s) ' + ', '.join(sorted({s for f in c8 for s in named[f]})) + ': ' + ', '.join(c8),
            'Every material the SDS names as reactive appears in 10.5/10.3. Missing: ' + ', '.join(c8), 'SDS Sections 2, 5, 6',
            items=[{'key': 'fam:' + f, 'text': f, 'status': 'fail'} for f in c8], prefix='Every material the SDS names as reactive appears in 10.5/10.3. Missing: ')
    s7 = low(' '.join(sds['sections'].get('7', {}).get('text', '').split()))
    c2 = []
    for cond, rx7, rx10 in (('light/sunlight', r'sunlight|\blight\b|dark', r'sunlight|\blight\b'),
                            ('moisture', r'protect(?:ed)? (?:from|against) moisture|dry place', r'moist|water'),
                            ('heat', r'\bcool\b|refrigerat|heat', r'heat|temperature'),
                            ('static discharge', r'static', r'static')):
        if re.search(rx7, s7) and not re.search(rx10, low(s10)):
            c2.append(cond)
    if c2:
        add('10.4 ↔ 7', '10-C2', 'warning', 'Section 7 sets: ' + ', '.join(c2), 'Same conditions named in Section 10. Missing: ' + ', '.join(c2), 'Annex II 7, 10.4',
            items=[{'key': 'cond:' + c, 'text': c, 'status': 'warning'} for c in c2], prefix='Same conditions named in Section 10. Missing: ')
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
    if nfpa:
        inst = int(nfpa.group(1))
        nf = []
        if inst >= 2 and re.search(r'\bstable\b', low(slots.get('stability'))) and not re.search(r'unstable', low(slots.get('stability'))):
            nf.append(('nfpa:inst', f'NFPA instability {inst}: 10.2 should not say "stable"'))
        special = re.search(r'Instability\s+(?:Physical hazards\s+)?\d\s+\d\s+\d\s+(\S+)', full)
        sp = special.group(1) if special else ''
        if 'W' in sp and 'water' not in families_in(incompatible):
            nf.append(('fam:water', 'NFPA W: water in 10.5'))
        if 'OX' in sp and 'combustibles' not in have10:
            nf.append(('fam:combustibles', 'NFPA OX: combustibles in 10.5'))
        if nf:
            add('10 ↔ NFPA', '10-C7', 'warning', f'NFPA instability {inst}, special {sp or "none"}', '; '.join(t for _, t in nf), 'NFPA 30 and NFPA 704',
                items=[{'key': k, 'status': 'warning', 'text': t} for k, t in nf], prefix='')
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
    s63 = low(sds['sections'].get('6', {}).get('subsections', {}).get('6.3', s6))
    clash = []
    fam10 = families_in(incompatible)
    m_neu = re.search(r'neutrali[sz]\w*[^.]{0,80}', s63)
    if m_neu:
        agent = m_neu.group(0)
        for fam, rx in (('acids', r'acid|bisulphite|bisulfite'), ('bases', r'alkali|base|soda|lime|bicarbonate|carbonate|hydroxide')):
            if re.search(rx, agent) and fam in fam10:
                clash.append(f'neutralising agent ({fam}) is listed in 10.5')
    if any(re.search(r'saw-?dust|wood chips|paper', x) and not re.search(r"\bdo not\b|\bnever\b|\bno\b|\bnot\b", x) for x in re.split(r'(?<=[.;])\s+', s63)) \
            and ('combustibles' in fam10 or H & OXIDISER):
        clash.append('combustible absorbent (sawdust/paper) with an oxidiser or 10.5 combustibles')
    if re.search(r'(?<!no )(?<!not )(?:flush|wash|rinse|hose)\w* (?:\w+ ){0,3}(?:with )?water|water spray', s63) and 'water' in fam10 and not aqueous:
        clash.append('water used in clean-up but water is listed in 10.5')
    if clash:
        add('6.3 ↔ 10.5', '6-C1', 'fail', s63[:150], 'Clean-up materials or neutralising agents listed as incompatible in 10.5: ' + '; '.join(clash),
            'Annex II 6.3, 10.5; CRW 4 (absorbent check)', items=[{'key': 'spill:incompat', 'status': 'fail', 'text': '; '.join(clash)}], prefix='Clean-up materials or neutralising agents listed as incompatible in 10.5: ')
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
    reported = set()  # overlap with 10-C1/10-C8 is now handled by the engine-wide duplicate rule
    fails, warns, explicit, srcs, fail_cards = {}, set(), set(), [], {}
    PRIMARY = ['halogens', 'acids', 'oxidisers', 'halogenated compounds']
    for cas_, d in lk.items():
        if cas_ == '7732-18-5':  # water as diluent: its own reactivity is not the product's
            continue
        for src, txt, url in reference_statements(d):
            for f, violent in reacting_families(txt).items():
                name = f[1] if isinstance(f, tuple) else f
                if isinstance(f, tuple) and f[0] == 'specific':
                    fams = SPECIFIC[name]
                    if re.search(r'\b' + name + r'\b', low(incompatible)) or fams & reported:
                        continue
                    if fams & have10:
                        explicit.add(name); srcs.append(src)
                    elif violent and src != 'NIOSH':
                        fam = next(x for x in PRIMARY if x in fams)
                        fails.setdefault(fam, set()).add(name); srcs.append(src)
                        if src.startswith('ICSC'):
                            fail_cards.setdefault(cas_, set()).add(src)
                    else:
                        warns.add(name); srcs.append(src)
                    continue
                if name in have10 or name in reported:
                    continue
                if name == 'water' and aqueous:
                    continue
                if isinstance(f, tuple):
                    if not re.search(REAGENTS[name], low(incompatible)):
                        warns.add(name)
                        srcs.append(src)
                elif violent and src != 'NIOSH':
                    fails.setdefault(name, set())
                    srcs.append(src)
                    if src.startswith('ICSC'):
                        fail_cards.setdefault(cas_, set()).add(src)
                else:
                    warns.add(name)
                    srcs.append(src)
    warns -= set(fails)
    notes = []
    s3 = ' '.join(sds['sections'].get('3', {}).get('text', '').split())
    for cas_, d in lk.items():
        cards = [c for r in d['results'] if r['source'] == 'ICSC' and r['status'] == 'ok' for c in r['cards']]
        if len(cards) > 1:
            mc = re.search(re.escape(cas_) + r'\s*([^A-Za-z]{0,25})', s3)
            conc = mc.group(1).strip() if mc else 'not stated'
            used = sorted(fail_cards.get(cas_, set())) or ['all cards (none stricter)']
            notes.append(f"ICSC has {len(cards)} cards for {cas_}: " + '; '.join(f"{c['card']} ({c['name']})" for c in cards)
                         + f". SDS concentration {conc} %; the stricter card was used: {', '.join(used)}.")
    if fails or warns or explicit:
        items = [{'key': 'fam:' + k, 'status': 'fail', 'text': k + (f" ({', '.join(sorted(v))})" if v else '') + ': violent/explosive/gas-releasing reaction recorded'}
                 for k, v in sorted(fails.items())]
        items += [{'key': 'name:' + n, 'status': 'warning', 'text': 'name explicitly (family already listed): ' + n} for n in sorted(explicit)]
        items += [{'key': ('fam:' if n in FAMILIES else 'name:') + n, 'status': 'warning', 'text': 'also listed: ' + n} for n in sorted(warns)]
        suffix = (' ' + ' '.join(notes)) if notes else ''
        add('10.5', '10-D1', 'fail' if fails else 'warning', incompatible[:150], '; '.join(x['text'] for x in items) + suffix,
            ', '.join(sorted(set(srcs))), items=items, prefix='', suffix=suffix)
    # 10-D4 / 10-D5 / 10-D6 from reference data
    s52 = low(' '.join(sds['sections'].get('5', {}).get('text', '').split()))
    d4, d5, d6, src456 = [], False, [], set()
    PRODUCTS = {'chlorine': r'chlorine', 'hydrogen chloride': r'hydrogen chloride|\bhcl\b', 'nitrogen oxides': r'nitrogen oxides|\bnox\b',
                'carbon monoxide': r'carbon monoxide', 'sulfur oxides': r'sulph?fur (?:di)?oxides?|\bsox\b', 'phosphine': r'phosphine',
                'hydrogen cyanide': r'hydrogen cyanide', 'hydrogen fluoride': r'hydrogen fluoride|\bhf\b', 'phosgene': r'phosgene'}
    for cas_, d in lk.items():
        if cas_ == '7732-18-5':
            continue
        for src, txt, url in reference_statements(d):
            t = low(txt)
            for sent in sentences(' '.join(txt.split())):
                if re.search(r'on heating|when heated|decomposes on heating|thermal decomposition|on combustion|burning', sent, re.I):
                    tail = sent + ' '
                    for name, rx in PRODUCTS.items():
                        if re.search(rx, tail, re.I) and not re.search(rx, dec10 + ' ' + s52):
                            d4.append(name); src456.add(src)
            if re.search(r'stabili[sz]ed|inhibitor|inhibited', t):
                d5 = True; src456.add(src)
            if re.search(r'may form explosive peroxides|peroxide former|may polymeri[sz]e|polymeri[sz]able|polymerization', t):
                d6.append('peroxide formation' if 'peroxide' in t else 'hazardous polymerisation'); src456.add(src)
    if d4:
        d4 = sorted(set(d4))
        add('10.6', '10-D4', 'warning', slots.get('decomposition', '')[:120], 'Decomposition products recorded on heating, missing from 10.6/5.2: ' + ', '.join(d4),
            ', '.join(sorted(src456)), items=[{'key': 'dec:' + x, 'status': 'warning', 'text': x} for x in d4], prefix='Decomposition products recorded on heating, missing from 10.6/5.2: ')
    if d5 and not re.search(r'stabili[sz]|inhibit', st10):
        st = 'fail' if EUGB else 'warning'
        add('10.2', '10-D5', st, slots.get('stability', ''), 'Reference data record a stabilised/inhibited form: name the stabiliser', ', '.join(sorted(src456)),
            items=[{'key': 'stab', 'status': st, 'text': 'name the stabiliser/inhibitor'}], prefix='Reference data record a stabilised/inhibited form: ')
    for what in sorted(set(d6)):
        word = 'peroxide' if 'peroxide' in what else 'polymeri'
        if not re.search(word, st10 + ' ' + re10 + ' ' + co10):
            add('10.2-10.4', '10-D6', 'warning', s10[:120], f'Reference data record {what}: address it in 10.2-10.4', ', '.join(sorted(src456)),
                items=[{'key': 'react:peroxide' if word == 'peroxide' else 'react:polymer', 'status': 'warning', 'text': what}], prefix='Reference data record: ')
    for cas_, d in lk.items():
        for r in d['results']:
            if r['source'] == 'GESTIS' and r.get('entries') and cas_ != '7732-18-5':
                add('10', '10-D1 (GESTIS)', 'not checked', '', 'Manual review: ' + r['entries'][0]['url'], 'GESTIS (manual link)')
    # merge 10-A5 and 10-B1 when they fire on the same text
    a5 = next((x for x in findings if x['check'] == '10-A5'), None)
    b1 = next((x for x in findings if x['check'] == '10-B1'), None)
    if a5 and b1:
        subs_a5 = re.findall(r'(10\.\d):', a5['sds_says'])
        subs_b1 = set(re.findall(r'(10\.\d):', b1['sds_says']))
        shared = [x for x in subs_a5 if x in subs_b1]
        if shared:
            findings.remove(a5); findings.remove(b1)
            rest = [x for x in subs_a5 if x not in subs_b1]
            add(b1['section'], '10-A5+10-B1', 'fail', b1['sds_says'],
                'No reason given for "no data" (10-A5) AND contradicts the classification (10-B1): ' + b1['expected'],
                a5['source'] + '; ' + b1['source'], items=b1.get('items'),
                prefix='No reason given for "no data" (10-A5) AND contradicts the classification (10-B1): ' + (b1.get('prefix') or ''))
            if rest:
                add('10', '10-A5', 'fail', '; '.join(r for r in a5['sds_says'].split('; ') if r.split(':')[0] in rest), a5['expected'], a5['source'])
    findings = dedupe(findings)
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
    import coverage
    have = any(not k.endswith('7732-18-5.json') for k in os.listdir(a.lookup_dir) if k.startswith('lookup_') and k[7:-5] in sds['codes_all']['CAS'])
    coverage.print_not_run('10', a.declared or res['jurisdiction']['detected'], a.type, have)
    if a.out:
        json.dump(res, open(a.out, 'w'), indent=1, ensure_ascii=False)
