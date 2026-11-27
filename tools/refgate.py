"""Concentration and physical-form gating for ingredient reference data (ICSC, CAMEO, NIOSH).

Thresholds live in config/reference_gating.json. Every rule that turns an ingredient's reference data into a
finding asks the Gate first:

  gate = Gate(sds, H, sds_type)          H = the mixture's own classification codes
  gate.card_applies(cas, label, text)    False if the record is for a gas and the product is not a gas/aerosol
  gate.allow(cas, kind, severity, label) the severity this finding may have (capped), or None (dropped)
  gate.notes                             what was capped or dropped, and why (shown in the report)

Kinds: 'high_hazard' (explosive, peroxide-forming, water-reactive), 'toxic_gas' (a reaction releases a toxic gas), 'reactivity' (incompatible
families), 'flammability', 'inhalation', 'skin', 'eyes', 'ingestion', 'delayed_health', 'environment', 'oxidiser',
'water_reactive'. Unit tests: tests/test_refgate.py.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config', 'reference_gating.json'), encoding='utf-8'))
SEV = {'info': 0, 'warning': 1, 'fail': 2}
CAS_RX = r'(?<![\d-])\d{2,7}-\d{2}-\d(?![\d-])'

HIGH_HAZARD = (r'explo|detonat|(?:form|forms|forming|formation of)\b[^.]{0,40}peroxides?|peroxide[- ]form|autoxid|'
               r'reacts? violently with water|in contact with water|water[- ]reactive|'
               r'flammable gas(?:es)? (?:on|in) contact with water')
# a toxic gas counts only when a reaction releases it ("liberates chlorine"), not when it is listed as a reagent
TOXIC_GAS = (r'(?:releas|liberat|evolv|produc|form|generat|gives? off|emit)\w*[^.]{0,60}(?:toxic (?:gas|fumes?|vapou?r)|chlorine|'
             r'hydrogen cyanide|hydrogen sulfide|hydrogen sulphide|phosgene|phosphine)')
FLAMMABILITY = r'ignit|flammab|fire|fireproof|spark|flame|combust|vapou?r[- ]air|explosive mixture'
DUST = r'\bdusts?\b|powder|granul|dust explosion|finely (?:divided|dispersed)'
GAS_CARD = (r'\bthe gas\b|gas is heavier|gas mixes|compressed gas|liquefied gas|refrigerated liquid|\(gas\)|anhydrous|'
            r'cryogenic|on contact with liquid: frostbite|frostbite')


# ------------------------------------------------------------------ Section 3 concentrations
_MASKS = [r'\b\d{3}-\d{3}-\d\b',                                  # EC numbers
          r'(?i)index(?:[- ]?no\.?)?\s*:?\s*[\d-]+(?:\s*[\dX-]+)?', r'\b0\d-\d\b',   # CLP index numbers, incl. ones split over lines
          r'\b\d{2}-\d{10}-\d{2}(?:-[\dX]{4})?\b', r'\b01-\d{7,10}-\d{2}(?:-[\dX]{4})?\b', r'01-\s*\d{7,10}-?\s*\d{0,2}(?:-[\dX]{4})?',  # REACH nos
          r'\b\d{3}-\d{3}-\d{2}-\w\b',                           # CLP index numbers
          r'\bE?U?H\d{3}\w{0,2}\b', r'\bP\d{3}\b',                 # H/P codes
          r'\bATE[^=\n]{0,60}=\s*[\d.,\s]+(?:mg|ppm|g)?[^\s]*',     # acute toxicity estimates
          r'\bM[- ]?factor[^=\n]{0,25}=\s*\d+', r'\b\d+(?:[.,]\d+)?\s*(?:mg|µg|g/|ml|ppm|°|kg|l\b)',
          r'\b(?:\d+\.){2,}\d*', r'\[\d\]', r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', r'\b\d+/\d+\b',
          r'(?:Cat(?:egory)?\.?|Tox\.|Irrit\.|Sens\.|Liq\.|Gas|Chronic|Acute|Corr\.|Dam\.|Repr\.|Carc\.|Muta\.|STOT (?:SE|RE)|Aerosol)\s*\d[A-C]?\b']
_CONC = re.compile(
    r'(?P<lo>[≥>]=?\s*)?(?P<a>\d{1,3}(?:[.,]\d+)?)\s*%?\s*(?:-|–|—|to|…)\s*(?P<hiop>[≤<]=?\s*)?(?P<b>\d{1,3}(?:[.,]\d+)?)\s*%?'
    r'|(?P<op>[≥≤<>]=?|ca\.|approx\.?|~)\s*(?P<c>\d{1,3}(?:[.,]\d+)?)\s*%?'
    r'|(?P<d>\d{1,3}(?:[.,]\d+)?)\s*%')


def _num(x):
    return float(x.replace(',', '.'))


def _mask(t):
    for rx in _MASKS:
        t = re.sub(rx, lambda m: ' ' * len(m.group(0)), t, flags=re.I)
    return t


def _candidates(masked, lo, hi):
    out = []
    for m in _CONC.finditer(masked, lo, hi):
        if m.group('a'):
            va, vb = _num(m.group('a')), _num(m.group('b'))
            if not (0 <= va <= vb <= 100) or (not m.group('lo') and '%' not in m.group(0) and vb - va > 90):
                continue
            strict = (m.group('hiop') or '').strip() == '<'
        elif m.group('c'):
            vb = _num(m.group('c'))
            strict = m.group('op').strip() == '<'
        else:
            vb = _num(m.group('d'))
            strict = False
        if vb > 100:
            continue
        top = vb * 0.999 if strict else vb   # "< 1" counts as just below 1
        out.append(((m.start() + m.end()) / 2, top, ' '.join(m.group(0).split())))
    return out


def concentrations(sds):
    """{cas: {'top': float or None, 'raw': str, 'name': str}} from Section 3 (top of any range).
    Tables print the concentration either before or after the CAS number; the first ingredient decides which."""
    s3 = sds['sections'].get('3', {}).get('text', '')
    if not s3:
        return {}
    pos = [(m.start(), m.end(), m.group(0)) for m in re.finditer(CAS_RX, s3)]
    if not pos:
        return {}
    masked = _mask(re.sub(CAS_RX, lambda m: ' ' * len(m.group(0)), s3))
    first_a = pos[0][0]
    start = max(0, first_a - 400)
    hdr = re.search(r'(?i)3\.[12]\.?\s|mixtures?\b|substances?\b', s3[start:first_a])
    before_first = _candidates(masked, start + (hdr.end() if hdr else 0), first_a)
    orient = 'before' if before_first else 'after'
    out = {}
    for i, (a, b, cas) in enumerate(pos):
        lo = pos[i - 1][1] if i else max(0, a - 400)
        hi = pos[i + 1][0] if i + 1 < len(pos) else min(len(s3), b + 400)
        bef, aft = _candidates(masked, lo, a), _candidates(masked, b, hi)
        pick = (bef[-1] if bef else None, aft[0] if aft else None)
        best = (pick[0] or pick[1]) if orient == 'before' else (pick[1] or pick[0])
        name = _name_before(s3, lo, a)
        out.setdefault(cas, {'top': best[1] if best else None, 'raw': best[2] if best else '', 'name': name})
    return out


def _name_before(s3, lo, a):
    seg = s3[lo:a]
    seg = re.sub(r'(?i)CAS(?:[- ]?(?:No|number|nr)\.?)?\s*[:#]?\s*$', '', seg.rstrip())
    lines = [l.strip() for l in seg.split('\n') if l.strip()]
    for l in reversed(lines):
        l2 = re.split(r'\s{2,}', l)[0]
        if re.search(r'[A-Za-z]{4}', l2) and not re.match(r'(?i)(?:ec|cas|reach|index|identifiers?|classification|note|type|\[)', l2):
            return l2[:80]
    return ''


# ------------------------------------------------------------------ product and record forms
def product_form(sds, H):
    s9 = ' '.join(sds['sections'].get('9', {}).get('text', '').split()).lower()
    s1 = ' '.join(sds['sections'].get('1', {}).get('text', '').split()).lower()
    if H & {'H222', 'H223', 'H229'} or re.search(r'\baerosol\b', s1):
        return 'aerosol'
    if H & {'H220', 'H221', 'H280', 'H281'} and not re.search(r'physical state\W*(?:liquid|solid)', s9):
        return 'gas'
    m = re.search(r'\b(?:physical state|appearance|form|phase)\b\W{0,5}([a-z ,()/-]{0,60})', s9)
    st = m.group(1) if m else ''
    if re.search(r'\bgas\b', st):
        return 'gas'
    if re.search(r'liquid|solution|paste|gel|emulsion|suspension|viscous', st):
        return 'liquid'
    if re.search(r'solid|powder|crystal|granul|flake|pellet|dust|sheet|film|tablet|bead', st):
        return 'solid'
    return 'unknown'


def record_is_gas(text):
    return bool(re.search(GAS_CARD, text or '', re.I))


def kinds_of(statement):
    """Kinds of a reference statement (a statement can have several)."""
    s = (statement or '').lower()
    k = set()
    if re.search(HIGH_HAZARD, s):
        k.add('high_hazard')
    if re.search(TOXIC_GAS, s):
        k.add('toxic_gas')
    if re.search(FLAMMABILITY, s):
        k.add('flammability')
    return k or {'reactivity'}


# ------------------------------------------------------------------ the gate
class Gate:
    def __init__(self, sds, H, sds_type):
        self.H = set(H)
        self.type = sds_type
        self.conc = concentrations(sds) if sds_type == 'mixture' else {}
        self.form = product_form(sds, self.H)
        self.notes = []
        self._noted = set()

    def band(self, cas):
        if self.type == 'substance':
            return CFG['substance_band']
        top = (self.conc.get(cas) or {}).get('top')
        if top is None:
            return CFG['unknown_concentration_band']
        if top >= CFG['bands']['major_min_percent']:
            return 'major'
        if top >= CFG['bands']['minor_min_percent']:
            return 'minor'
        return 'trace'

    def describe(self, cas):
        c = self.conc.get(cas) or {}
        return f"{c.get('name') or cas} ({cas}{', ' + c['raw'] if c.get('raw') else ''})"

    def _note(self, text):
        if text not in self._noted:
            self._noted.add(text)
            self.notes.append(text)

    def card_applies(self, cas, label, text):
        """Physical-form gate for a whole record (ICSC card / CAMEO datasheet)."""
        if record_is_gas(text) and self.form not in CFG['physical_form']['gas_compatible_product_forms']:
            self._note(f'{label} for {self.describe(cas)} describes a gas; product is {self.form}: not applied')
            return False
        return True

    def statement_applies(self, cas, label, statement):
        """Physical-form gate for one statement: dust/powder statements only for solid products."""
        if re.search(DUST, statement or '', re.I) and self.form not in CFG['physical_form']['dust_compatible_product_forms']:
            self._note(f'{label}: dust/powder statement for {self.describe(cas)} not applied; product is {self.form}')
            return False
        return True

    def allow(self, cas, kind, severity, label=''):
        """Severity this ingredient's reference data may drive, or None. `kind` is a string or a set of kinds."""
        kinds = {kind} if isinstance(kind, str) else set(kind)
        band = self.band(cas)
        if band == 'major':
            cap = CFG['major']['max_severity']
        elif band == 'minor':
            if kinds & {'high_hazard', 'toxic_gas'}:
                cap = CFG['minor']['max_severity']
            else:
                fitting = [k for k in kinds if k in CFG['kind_fits'] and self.H & set(CFG['kind_fits'][k])]
                if 'reactivity' in kinds and not fitting:
                    cap = CFG['minor']['general_reactivity_max']
                elif fitting:
                    cap = CFG['minor']['max_severity']
                else:
                    self._note(f"{label}: {self.describe(cas)} is {band} ({'/'.join(sorted(kinds))} data does not fit the mixture's classification): not applied")
                    return None
        else:  # trace
            if not kinds & set(CFG['trace']['keep_kinds']):
                self._note(f'{label}: {self.describe(cas)} is below {CFG["bands"]["minor_min_percent"]} %: not applied')
                return None
            cap = CFG['trace']['max_severity']
        out = severity if SEV[severity] <= SEV[cap] else cap
        if out != severity:
            self._note(f'{label}: {self.describe(cas)} is {band}: {severity} capped at {out}')
        return out


def source_status(r):
    """Lookup status, correcting old snapshots that labelled PubChem's 'No CID found' as unreachable."""
    if r.get('status') == 'unreachable' and 'NotFound' in (r.get('note') or ''):
        return 'not found'
    return r.get('status')


def has_reference_data(lk):
    """True if ICSC, CAMEO or NIOSH returned a record for this CAS."""
    for r in (lk or {}).get('results', []):
        if r['source'] == 'ICSC' and r.get('status') == 'ok' and r.get('cards'):
            return True
        if r['source'] == 'CAMEO Chemicals' and r.get('status') == 'ok' and r.get('datasheets'):
            return True
        if r['source'] == 'NIOSH Pocket Guide' and r.get('status') == 'ok':
            return True
    return False


def strongest(*sevs):
    sevs = [s for s in sevs if s]
    return max(sevs, key=lambda s: SEV[s]) if sevs else None
