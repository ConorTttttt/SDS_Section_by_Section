"""Sections 5 (firefighting), 6 (accidental release) and 7 (handling and storage) checker.

Shares the classification reading, P-statement triggers (CLP Annex IV assignment conditions, EU = GB, verified)
and the engine-wide duplicate rule. Links to Section 10 that are already in the Section 10 checklist
(5-C1, 5-C2, 6-C1, 7-C1) are produced by check_s10.py and are not repeated here.

Usage: python3 -I check_s567.py SDS_JSON LOOKUP_DIR --declared GB|EU|US --type substance|mixture [--section 5|6|7] [--out f.json]
Review aid only: a competent person must verify every finding. Keyword heuristics tuned on the regression set.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_s10 as s10  # noqa: E402
import check_s4 as s4  # noqa: E402
from dedupe import dedupe  # noqa: E402
import refgate  # noqa: E402
import textinterp as ti  # noqa: E402
from sds_text import sub_body, transport_class  # noqa: E402

# Checklist rows this engine implements (checked against checklist/coverage.csv by tools/check_coverage.py).
# 5/6/7-A1..A3 are produced by structure().
CODED = ({f'{n}-A{i}' for n in (5, 6, 7) for i in (1, 2, 3)}
         | {'5-A4', '5-A5', '5-A6', '5-B1', '5-B2', '5-B3', '5-B4', '5-B5', '5-C3', '5-C4', '5-C5', '5-C6', '5-D1'}
         | {'6-A4', '6-A5', '6-A6', '6-A7', '6-B1', '6-B2', '6-B3', '6-B4', '6-B5', '6-C2', '6-D1'}
         | {'7-A4', '7-A5', '7-A6', '7-A7'} | {f'7-B{i}' for i in range(1, 15)} | {'7-C2', '7-C3', '7-C4', '7-D1'})

EXPLOSIVE = {'H200', 'H201', 'H202', 'H203', 'H204', 'H205'}
DESENS = {'H206', 'H207', 'H208'}
FLAM_GAS = {'H220', 'H221'}
FLAM_LIQ = {'H224', 'H225', 'H226'}
FLAMMABLE = FLAM_GAS | {'H222', 'H223'} | FLAM_LIQ | {'H228'}
SELF_REACT_OP = {'H240', 'H241', 'H242'}
OX_CAT1 = {'H271'}
OXIDISER = {'H270', 'H271', 'H272'}
WATER_REACT = {'H260', 'H261'}
PYRO = {'H250', 'H232'}
SELF_HEAT = {'H251', 'H252'}
AQUATIC_HIGH = {'H400', 'H410', 'H411'}
AQUATIC_LOW = {'H412', 'H413'}
INHAL = {'H330', 'H331', 'H332', 'H334', 'H335', 'H336'}
H_EXTRA = [(r'very toxic to aquatic life', 'H400'), (r'very toxic to aquatic life with long lasting', 'H410'),
           (r'toxic to aquatic life with long lasting', 'H411'), (r'harmful to aquatic life with long lasting', 'H412'),
           (r'may cause long lasting harmful effects to aquatic', 'H413'), (r'unstable explosive', 'H200'),
           (r'explosive; mass explosion hazard', 'H201'), (r'extremely flammable gas', 'H220'), (r'(?<!extremely )flammable gas\b', 'H221'),
           (r'may cause or intensify fire; oxidi', 'H270'), (r'contains refrigerated gas', 'H281'), (r'pressurised container', 'H229')]
TEMP = r'(?i)(?:not exceeding|below|at or below|maximum(?: of)?|max\.?|≤|<|under)\s*(-?\d+(?:[.,]\d+)?)\s*°\s*C'
MEDIA = {'water spray': r'water spray|water mist|water fog', 'water jet': r'water jet|full jet|straight stream|direct water',
         'water': r'\bwater\b', 'foam': r'foam', 'dry chemical': r'dry chemical|dry powder|\bpowder\b', 'sand': r'\bsand\b',
         'carbon dioxide': r'carbon dioxide|\bco ?2\b', 'halogenated agents': r'halon|halogenated'}


def low(x):
    return (x or '').lower()


def norm(t):
    return ' '.join((t or '').split())


def classification(sds):
    """Section 2 only. Section 12 prose ("Harmful to aquatic life...") is not a classification: a contradiction
    between Section 12 and Section 2 belongs to those sections' checks (blind test, MPM aerosol)."""
    H = s4.classification(sds)
    t = low(norm(sds['sections'].get('2', {}).get('text', '')))
    for rx, code in H_EXTRA:
        if re.search(rx, t):
            H.add(code)
    return H


def media_in(text):
    t = low(text)
    found = {k for k, rx in MEDIA.items() if re.search(rx, t)}
    if 'water spray' in found or 'water jet' in found:
        found.discard('water') if not re.search(r'\bwater\b(?! spray| mist| fog| jet)', t) else None
    return found


class Ctx:
    def __init__(self, sds, lookup_dir, declared, sds_type='mixture'):
        self.sds = sds
        self.full = open(os.path.join(os.path.dirname(sds['_path']), 'sds.txt'), encoding='utf-8').read()
        det, _, why = s10.detect_jurisdiction(self.full)
        self.J = declared or det
        self.EUGB = self.J in ('EU', 'GB')
        self.juris = {'declared': declared, 'detected': det, 'evidence': why[det], 'mismatch': bool(declared and declared != det)}
        self.H = classification(sds)
        self.P = set(sds['codes_by_section'].get('2', {}).get('P', []))
        self.Psingle = {c for combo in self.P for c in combo.split('+')}
        self.s2 = low(norm(sds['sections'].get('2', {}).get('text', '')))
        self.lk = s10.lookups(sds['codes_all']['CAS'], lookup_dir)
        self.gate = refgate.Gate(sds, self.H, sds_type)
        self.findings = []

    def sec(self, n):
        return self.sds['sections'].get(str(n))

    def sub(self, key):
        """Subsection text without number and title; text on the heading line is kept (two-column layouts)."""
        n = key.split('.')[0]
        s = self.sec(n) or {}
        return norm(sub_body(s.get('subsections', {}).get(key, ''), key))

    def text(self, n):
        return low(norm((self.sec(n) or {}).get('text', '')))

    def add(self, section, cid, status, says, expected, source, items=None, prefix=None):
        f = {'section': section, 'check': cid, 'status': status, 'sds_says': (says or '')[:300], 'expected': expected, 'source': source}
        if items:
            f.update(items=items, prefix=prefix, suffix='')
        self.findings.append(f)

    def one(self, section, cid, status, says, expected, source, key):
        self.add(section, cid, status, says, expected, source, items=[{'key': key, 'status': status, 'text': expected}], prefix='')

    def icsc(self):
        for c, d in self.lk.items():
            if c == '7732-18-5':
                continue
            for r in d['results']:
                if r['source'] == 'ICSC' and r['status'] == 'ok':
                    for card in r['cards']:
                        form_txt = ' '.join(str(x) for x in (card.get('name'), card.get('physical_dangers'), card.get('first_aid'), card.get('fire_and_explosion')) if x)
                        if self.gate.card_applies(c, f"ICSC {card['card']}", form_txt):
                            yield c, card

    def cameo(self):
        for c, d in self.lk.items():
            for r in d['results']:
                if r['source'] == 'CAMEO Chemicals' and r['status'] == 'ok':
                    for ds in r['datasheets']:
                        if self.gate.card_applies(c, f"CAMEO {ds['id']}", (ds.get('name') or '') + ' ' + (ds.get('reactivity_profile') or '')[:200]):
                            yield c, ds

    def allow(self, cas, kind, severity, label):
        return self.gate.allow(cas, kind, severity, label)


def structure(ctx, n, title_rx, subs_eu, us_labels, refs):
    sec = ctx.sec(n)
    if not sec:
        ctx.add(str(n), f'{n}-A1', 'fail', f'Section {n} not found', f'Section {n} heading present', refs)
        return False
    if ctx.EUGB:
        miss = [k for k in subs_eu if k not in sec.get('subsections', {})]
        blank = [k for k in subs_eu if k in sec.get('subsections', {}) and not ctx.sub(k)]
        if miss or blank:
            ctx.add(str(n), f'{n}-A2', 'fail', ('Missing: ' + ', '.join(miss) if miss else '') + (' Blank: ' + ', '.join(blank) if blank else ''),
                    'Numbered subheadings ' + ', '.join(subs_eu) + ', none blank', 'REACH Annex II Part B, 0.4')
    else:
        t = ctx.text(n)
        miss = [lab for lab, rx in us_labels if not re.search(rx, t)]
        if miss:
            ctx.add(str(n), f'{n}-A3', 'fail', 'Not found: ' + ', '.join(miss), f'App D s.{n} elements', f'OSHA App D Table D.1 s.{n}')
    return True


# ------------------------------------------------------------------ Section 5
def run5(ctx):
    if not structure(ctx, 5, 'fire', ['5.1', '5.2', '5.3'],
                     [('(a) extinguishing media', r'extinguishing media'), ('(b) specific hazards', r'hazards? arising|specific hazard|special hazard'),
                      ('(c) firefighter protection', ti.SYNONYMS['firefighting'] + '|' + ti.SYNONYMS['firefighter_ppe'])], 'Annex II Part B'):
        return
    s5 = ctx.text(5)
    s51 = low(ctx.sub('5.1')) if '5.1' in ctx.sec(5).get('subsections', {}) else s5
    s52 = low(ctx.sub('5.2')) if '5.2' in ctx.sec(5).get('subsections', {}) else s5
    s53 = low(ctx.sub('5.3')) if '5.3' in ctx.sec(5).get('subsections', {}) else s5
    parts = re.split(r'unsuitable(?: extinguishing)?(?: media)?|must not be used|not be used for safety reasons', s51, maxsplit=1)
    suitable, unsuitable = parts[0], (parts[1] if len(parts) > 1 else '')
    if len(parts) == 1:
        ctx.add('5.1', '5-A4', 'warning', s51[:150], 'Unsuitable extinguishing media stated (or "none known")', 'Annex II 5.1; App D s.5(a)')
    if not re.search(r'produc|fumes|gas|smoke|oxides|decompos|vapou?r|burst|explo|hazard', s52):
        ctx.add('5.2', '5-A5', 'warning', s52[:150], 'Hazards named, incl. hazardous combustion products', 'Annex II 5.2; App D s.5(b)')
    if not re.search(ti.SYNONYMS['firefighter_ppe'], s53):
        ctx.add('5.3', '5-A6', 'warning', s53[:150], 'Special protective equipment for firefighters', 'Annex II 5.3; App D s.5(c)')
    H = ctx.H
    # 5-B1 label media vs 5.1
    m = re.search(r'in case of fire:?\s*use (.{3,120}?) (?:to|for) extinction|in case of fire:?\s*use (.{3,120}?) to extinguish', ctx.s2)
    if m or 'P378' in ctx.Psingle:
        label = media_in((m.group(1) or m.group(2)) if m else '')
        bad = sorted(label & media_in(unsuitable))
        missing = sorted(label - media_in(suitable))
        if bad:
            ctx.one('5.1 ↔ 2', '5-B1', 'fail', s51[:150], 'Label media (P370+P378) listed as unsuitable in 5.1: ' + ', '.join(bad), 'CLP IV P370+P378', 'media:label')
        elif missing:
            ctx.one('5.1 ↔ 2', '5-B1', 'warning', s51[:150], 'Label media (P370+P378) not in 5.1 suitable media: ' + ', '.join(missing), 'CLP IV P370+P378', 'media:label')
    # 5-B2 explosion-risk classes
    need = None
    if H & (EXPLOSIVE | {'H240'}):
        need = ('Explosion risk: evacuate area; do not fight fire when it reaches explosives (P370+P372+P380+P373)',
                r'evacuat', r'do not fight|not fight (?:the )?fire|when (?:the )?fire reaches')
    elif H & DESENS:
        need = ('Evacuate area; fight fire remotely due to the risk of explosion (P370+P380+P375)', r'evacuat', r'remote|from a (?:safe )?distance|unmanned|from a protected')
    elif H & OX_CAT1:
        need = ('Major fire and large quantities: evacuate area; fight fire remotely due to the risk of explosion (P371+P380+P375)',
                r'evacuat', r'remote|from a (?:safe )?distance|unmanned|from a protected')
    if need and not (re.search(need[1], s5) and re.search(need[2], s5)):
        ctx.one('5.3', '5-B2', 'fail', s53[:150], need[0], 'CLP IV P370/P371 combinations (EU = GB, verified)', 'fire:explosion')
    if H & FLAM_GAS and not re.search(r'leaking gas fire|do not extinguish[^.]{0,60}unless|unless (?:the )?leak can be stopped', s5):
        ctx.one('5.1/5.3', '5-B3', 'fail', s5[:150], '"Leaking gas fire: do not extinguish, unless leak can be stopped safely" (P377)', 'CLP IV P377', 'fire:leaking-gas')
    if 'H270' in H and not re.search(r'stop (?:the )?leak', s5):
        ctx.one('5.3', '5-B4', 'warning', s53[:150], 'Stop leak if safe to do so (P370+P376)', 'CLP IV P370+P376', 'fire:stop-leak')
    if H & {'H280', 'H229', 'H222', 'H223'} and not re.search(r'burst|rupture|explode|explosion', s5):
        ctx.one('5.2', '5-B4', 'warning', s52[:150], 'Containers may burst/explode when heated; cool them with water spray', 'H280/H229 wording', 'fire:burst')
    if H & FLAM_LIQ and not re.search(r'water jet|full (?:water )?jet|straight stream|direct (?:water )?stream|high volume', unsuitable + ' ' + s5):
        ctx.one('5.1', '5-B5', 'warning', s51[:150], 'Water jet unsuitable for a flammable liquid where water increases the risk', 'CLP IV P370+P378 condition ("if water increases risk")', 'fire:water-jet')
    # 5-C3 suitable media vs 10.5
    inc = low(s10.section10_slots(ctx.sec(10))[0].get('incompatible', '')) if ctx.sec(10) else ''
    clash = [k for k in media_in(suitable) if (k.startswith('water') and re.search(r'\bwater\b', inc) and 'water' not in ctx.text(3)) or
             (k == 'carbon dioxide' and re.search(r'carbon dioxide', inc)) or (k == 'halogenated agents' and re.search(r'halogen', inc))]
    if clash:
        ctx.one('5.1 ↔ 10.5', '5-C3', 'fail', suitable[:150], 'Suitable media listed as incompatible in 10.5: ' + ', '.join(sorted(clash)), 'Annex II 5.1, 10.5', 'media:incompatible')
    if re.search(r'chlorine|hydrogen chloride|carbon monoxide|nitrogen oxides|hydrogen cyanide|phosphine|sulph?fur oxides|toxic', s52) and \
            not re.search(r'breathing apparatus|scba|self-contained|respirat', s53):
        ctx.one('5.3 ↔ 5.2', '5-C4', 'warning', s53[:150], 'Breathing apparatus where 5.2 names toxic combustion products', 'Annex II 5.3, 8', 'ppe:ba')
    if H & AQUATIC_HIGH and not re.search(r'run-?off|fire-?water|extinguishing water|contaminated water|drains', s5 + ' ' + ctx.text(6)):
        ctx.one('5.3/6.2', '5-C5', 'warning' if ctx.EUGB else 'info', s53[:150], 'Contain fire-water run-off (aquatic hazard)',
                'Annex II 5.3, 6.2; NetRegs GPP 18 (GB, good practice)' + ('' if ctx.EUGB else '; HazCom does not cover environmental hazards'), 'env:firewater')
    cls14 = transport_class((ctx.sec(14) or {}).get('text', ''), (ctx.sec(14) or {}).get('subsections'))
    if cls14 and cls14.split('.')[0] == '1' and not re.search(r'evacuat', s5):
        ctx.one('5 ↔ 14', '5-C6', 'warning', '', 'Class 1 (explosives) in Section 14: evacuation advice expected in Section 5', 'ADR; Section 14', 'fire:explosion')
    if cls14 == '2.1' and not H & {'H222', 'H223', 'H229'} and not re.search(r'leak', s5):   # P377 is not assigned to aerosols
        ctx.one('5 ↔ 14', '5-C6', 'warning', '', 'Class 2.1 (flammable gas) in Section 14: leaking-gas-fire advice expected', 'ADR; Section 14', 'fire:leaking-gas')
    # 5-D1 reference data
    for c, card in ctx.icsc():
        ff = low((card.get('fire') or {}).get('fire_fighting'))
        if re.search(r'no water|no direct contact with water|do not use water', ff) and media_in(suitable) & {'water', 'water spray', 'foam'}:
            st = ctx.allow(c, {'high_hazard'}, 'fail', f'ICSC {card["card"]}')
            if st:
                ctx.one('5.1', '5-D1', st, suitable[:150], f'ICSC {card["card"]}: "{ff[:120]}" but 5.1 lists water or foam as suitable', f'ICSC {card["card"]}', 'media:water')
    for c, ds in ctx.cameo():
        # ERG excerpts carry caveats for other materials ("CAUTION: For LNG (UN1972) pool fires, DO NOT USE water"): drop them
        sents = [x for x in s10.sentences(ds.get('firefighting') or '') if not re.search(r'\bfor\b[^.]{0,80}\(\s*UN\s?\d{4}\s*\)|^caution:\s*for\b', x, re.I)]
        ff = low(' '.join(sents))
        if re.search(r'do not use water', ff) and media_in(suitable) & {'water', 'water spray', 'foam'}:
            st = ctx.allow(c, {'high_hazard'}, 'fail', f'CAMEO {ds["id"]}')
            if st:
                ctx.one('5.1', '5-D1', st, suitable[:150], f'CAMEO {ds["id"]} (ERG excerpt): "DO NOT USE WATER" but 5.1 lists water or foam', f'CAMEO {ds["id"]}', 'media:water')


# ------------------------------------------------------------------ Section 6
def run6(ctx):
    if not structure(ctx, 6, 'release', ['6.1', '6.2', '6.3', '6.4'],
                     [('(a) personal precautions', r'personal precaution|protective equipment|emergency procedure'),
                      ('(b) containment and clean-up', r'contain|clean')], 'Annex II Part B'):
        return
    s6 = ctx.text(6)
    s61 = low(ctx.sub('6.1')) if '6.1' in ctx.sec(6).get('subsections', {}) else s6
    s62 = low(ctx.sub('6.2')) if '6.2' in ctx.sec(6).get('subsections', {}) else s6
    s63 = low(ctx.sub('6.3')) if '6.3' in ctx.sec(6).get('subsections', {}) else s6
    H = ctx.H
    if ctx.EUGB:
        if H & (FLAMMABLE | {'H300', 'H310', 'H330', 'H331', 'H314'} | AQUATIC_HIGH) and not re.search(r'large|small|major|minor', s6):
            ctx.add('6', '6-A4', 'warning', '', 'Large and small spills distinguished where volume changes the hazard', 'Annex II s.6 preamble')
        if not re.search(r'emergency responders?|6\.1\.2', s6) or not re.search(r'butyl|neoprene|nitrile|pvc|viton|tychem|fabric|material|chemical(?:ly)? (?:resistant|protective) (?:suit|clothing)', s6):
            ctx.add('6.1', '6-A5', 'warning', s61[:150], 'Suitable fabric for emergency responders\' protective clothing (6.1.2)', 'Annex II 6.1.2')
    if not re.search(ti.SYNONYMS['contain_spill'], s6):
        ctx.add('6.3', '6-A6', 'warning', s63[:150], 'How to contain the spill', 'Annex II 6.3.1; App D s.6(b)')
    if not re.search(ti.SYNONYMS['clean_spill'], s63):
        ctx.add('6.3', '6-A6', 'warning', s63[:150], 'How to clean up the spill', 'Annex II 6.3.2; App D s.6(b)')
    if ctx.EUGB and not re.search(r'section 8|section 13|sections 8|8 and 13', s6):
        ctx.add('6.4', '6-A7', 'info', '', 'Reference to Sections 8 and 13', 'Annex II 6.4')
    aq_txt = re.search(r'(?:very )?toxic to aquatic|harmful to aquatic', low(ctx.full))
    if H & AQUATIC_HIGH or (aq_txt and not ctx.EUGB):
        if not re.search(r'drain|sewer|watercourse|surface water|ground ?water|waterway|environment|soil', s62 + ' ' + s6):
            st = 'fail' if ctx.EUGB else 'info'
            ctx.one('6.2', '6-B1', st, s62[:150], 'Keep out of drains, surface and ground water (aquatic hazard; P273)',
                    'CLP IV P273' + ('' if ctx.EUGB else '; HazCom does not cover environmental hazards'), 'env:drains')
        if H & AQUATIC_HIGH and not re.search(r'collect', s6):
            ctx.one('6.3', '6-B1', 'warning' if ctx.EUGB else 'info', s63[:150], 'Collect spillage (P391)', 'CLP IV P391', 'env:collect')
    elif H & AQUATIC_LOW and not re.search(r'drain|sewer|watercourse|surface water|ground ?water|environment', s6):
        ctx.one('6.2', '6-B1', 'warning' if ctx.EUGB else 'info', s62[:150], 'Keep out of drains and water (chronic aquatic hazard; P273)', 'CLP IV P273', 'env:drains')
    if 'H290' in H and not re.search(r'absorb', s63):
        ctx.one('6.3', '6-B2', 'warning', s63[:150], 'Absorb spillage to prevent material damage (P390)', 'CLP IV P390', 'spill:absorb')
    if H & FLAMMABLE:
        if not re.search(r'ignition', s6):
            ctx.one('6.1/6.3', '6-B3', 'fail', s61[:150], 'Remove all ignition sources (P381 for flammable gases; Annex II 6.1.1)', 'CLP IV P381; Annex II 6.1.1', 'ign:remove')
        if H & {'H224', 'H225'} and not re.search(r'non-sparking|spark-proof|explosion-proof|anti-static|ex-protected', s6):
            ctx.one('6.3', '6-B3', 'warning', s63[:150], 'Non-sparking tools / explosion-proof equipment where applicable', 'Annex II 6.3.2; CLP IV P241/P242', 'ign:tools')
    if H & (WATER_REACT | PYRO):
        if ti.affirmed(s63, r'(?:flush|wash|rinse|hose)\w* (?:\w+ ){0,3}(?:with )?water|water spray|dilute with water') and not re.search(r'do not use water|no water|never use water', s6):
            ctx.one('6.3', '6-B4', 'fail', s63[:150], 'No water on a water-reactive/pyrophoric spill; keep dry and cover', 'CLP IV P223, P231+P232', 'spill:water')
        elif not re.search(r'dry|cover|inert|do not use water|no water|without water|no contact with water|avoid (?:all )?contact with water', s6):
            ctx.one('6.3', '6-B4', 'warning', s63[:150], 'Keep the spill dry (no water) and use dry containers', 'CLP IV P223, P402+P404', 'spill:water')
    if H & (INHAL | {'H314'}) and not re.search(r'respirat|breathing|evacuat|ventilat|personal protective|section 8', s61):
        ctx.one('6.1', '6-B5', 'warning', s61[:150], 'Respiratory protection, ventilation or evacuation', 'Annex II 6.1.1', 'ppe:resp')
    s9t = low(norm((ctx.sec(9) or {}).get('text', '')))
    mstate = re.search(r'\b(?:physical state|appearance|form)\b\s*:?\s*([^.;|]{0,80})', s9t)
    state = mstate.group(1) if mstate else ''
    if ctx.EUGB and re.search(r'\bsolid|powder|dust|crystal|granul|flake|rock', state) and not re.search(r'\bliquid|\bgas\b', state) and not re.search(r'dust', s6):
        ctx.one('6.1/6.3', '6-B5', 'warning', s61[:150], 'Control of dust (avoid raising dust)', 'Annex II 6.1.1 ("control of dust")', 'spill:dust')
    s82 = low(ctx.sub('8.2')) if ctx.sec(8) and '8.2' in ctx.sec(8).get('subsections', {}) else ctx.text(8)
    if re.search(r'respirat', s82) and not (re.search(r'respirat|personal protective|ppe|protective equipment', s61) or ti.refers_to(s61, '8')
                                             or re.search(r'sections? (?:7 and )?8\b|section 8', s61)):
        ctx.one('6.1 ↔ 8', '6-C2', 'warning', s61[:150], 'PPE in 6.1 consistent with 8.2 (8.2 calls for respiratory protection)', 'Annex II 6.1.1, 8.2', 'ppe:resp')
    for c, card in ctx.icsc():
        sp = low(card.get('spillage'))
        if not sp:
            continue
        lab = f'ICSC {card["card"]}'
        checks = (
            (re.search(r'do not use water|no water', sp) and ti.affirmed(s63, r'(?:flush|wash|rinse|hose)\w* (?:\w+ ){0,3}(?:with )?water|water spray'),
             '6.3', 'fail', {'high_hazard'}, f'{lab} spillage: "Do NOT use water"', 'spill:water', s63),
            ('remove all ignition sources' in sp and not re.search(r'ignition', s6),
             '6.1', 'warning', {'flammability'}, f'{lab}: remove all ignition sources', 'ign:remove', s61),
            (re.search(r'do not let this chemical enter the environment', sp) and not re.search(r'drain|sewer|environment|water', s62 + ' ' + s6),
             '6.2', 'warning' if ctx.EUGB else 'info', {'environment'}, f'{lab}: do not let the chemical enter the environment', 'env:drains', s62),
            (re.search(r'saw-?dust|combustible absorbents', sp) and ti.affirmed(s63, r'saw-?dust'),
             '6.3', 'fail', {'oxidiser', 'high_hazard'}, f'{lab}: no sawdust or other combustible absorbents', 'spill:absorbent', s63),
            ('dry' in sp and H & WATER_REACT and 'dry' not in s6,
             '6.3', 'warning', {'water_reactive'}, f'{lab}: collect into dry containers', 'spill:water', s63))
        for hit, sec, sev, kind, text, key, says in checks:
            if hit:
                st = ctx.allow(c, kind, sev, lab)
                if st:
                    ctx.one(sec, '6-D1', st, says[:150], text, lab, key)


# ------------------------------------------------------------------ Section 7
def run7(ctx):
    if not structure(ctx, 7, 'handling', ['7.1', '7.2', '7.3'],
                     [('(a) safe handling', r'handling|handle'), ('(b) safe storage', r'storage|store')], 'Annex II Part B'):
        return
    s7 = ctx.text(7)
    subs = ctx.sec(7).get('subsections', {})
    s71 = low(ctx.sub('7.1')) if '7.1' in subs else s7
    s72 = low(ctx.sub('7.2')) if '7.2' in subs else s7
    s73 = low(ctx.sub('7.3')) if '7.3' in subs else ''
    H = ctx.H
    if ctx.EUGB:
        gaps = []
        if not re.search(r'incompatib|keep away from|avoid contact with|section 10|separat', s7):
            gaps.append('prevent handling of incompatible substances')
        if not re.search(r'drain|environment|spill|release|sewer', s7):
            gaps.append('reduce release to the environment')
        if gaps:
            ctx.add('7.1', '7-A4', 'warning', s71[:150], '7.1.1 recommendations missing: ' + '; '.join(gaps), 'Annex II 7.1.1',
                    items=[{'key': 'env:release' if 'environment' in g else 'h:incompat', 'status': 'warning', 'text': g} for g in gaps],
                    prefix='7.1.1 recommendations missing: ')
        # Annex II 7.1.2: "Advice on general occupational hygiene shall be provided, such as: ..." - the list is examples
        met, _ = ti.covers_examples(s7, {'no eating, drinking or smoking': r'\beat|drink|smok',
                                         'wash hands': ti.SYNONYMS['wash_hands'],
                                         'remove contaminated clothing before eating areas': r'contaminated cloth|remove (?:and wash )?contaminated|before entering eating'},
                                    ti.SYNONYMS['hygiene_generic'])
        if not met:
            ctx.add('7.1', '7-A5', 'warning', s71[:150], 'No general occupational hygiene advice (e.g. no eating, drinking or smoking; wash hands; '
                    'remove contaminated clothing before eating areas)', 'Annex II 7.1.2')
        if s73 and (ti.is_no_data(s73) or re.search(r'^\W*(?:see (?:section|subsection) 1\.2|none)\W*\.?$', s73)):
            ctx.add('7.3', '7-A7', 'info', s73[:100], 'Specific end use recommendations (or reference to an attached exposure scenario)', 'Annex II 7.3')
    if ctx.EUGB and not re.search(r'closed|cool|ventilat|dry|temperature|original container|original packaging', s72):
        ctx.add('7.2', '7-A6', 'warning', s72[:150], 'Basic storage conditions (closed container, temperature, ventilation, humidity)', 'Annex II 7.2; App D s.7(b)')
    # B rows
    if H & FLAMMABLE:
        if not re.search(r'ignition|flame|spark|heat|smoking', s7):
            ctx.one('7.1/7.2', '7-B1', 'fail', s7[:150], 'Keep away from heat, sparks, open flames and other ignition sources (P210)', 'CLP IV P210', 'ign:sources')
        want = []
        if H & {'H224', 'H225'} or ctx.Psingle & {'P240', 'P243'}:
            if not re.search(r'ground|earth|bond', s7):
                want.append(('ign:bond', 'ground and bond container and receiving equipment (P240)'))
            if not re.search(r'static', s7):
                want.append(('ign:static', 'action to prevent static discharges (P243)'))
            if not re.search(r'explosion-proof|ex-proof|atex|explosion protected|flameproof', s7):
                want.append(('ign:exproof', 'explosion-proof electrical/ventilating/lighting equipment (P241)'))
        if 'P242' in ctx.Psingle and not re.search(r'non-sparking|spark-proof', s7):
            want.append(('ign:tools', 'non-sparking tools (P242)'))
        if (H & (FLAM_GAS | {'H224', 'H225'})) and not (re.search(r'ventilat', s72) and re.search(r'cool|temperature|heat', s72 + ' ' + s7)):
            want.append(('store:cool-vent', 'store in a well-ventilated place; keep cool (P403+P235 / P403)'))
        if want:
            ctx.add('7.1/7.2', '7-B1', 'warning', s7[:150], '; '.join(t for _, t in want), 'CLP IV P240-P243, P403 (assignment conditions)',
                    items=[{'key': k, 'status': 'warning', 'text': t} for k, t in want], prefix='')
    if H & OXIDISER and not re.search(r'combustible|organic material|flammable material|reducing', s7):
        ctx.one('7.1/7.2', '7-B2', 'fail', s72[:150], 'Keep away from clothing and other combustible materials (P220)', 'CLP IV P220', 'store:combustibles')
    if H & OX_CAT1 and not re.search(r'separat', s72):
        ctx.one('7.2', '7-B2', 'warning', s72[:150], 'Store separately (P420, oxidisers cat. 1)', 'CLP IV P420', 'store:separately')
    if 'H270' in H and not re.search(r'oil|grease', s7):
        ctx.one('7.1', '7-B2', 'warning', s71[:150], 'Keep valves and fittings free from oil and grease (P244)', 'CLP IV P244', 'h:oil')
    if H & SELF_REACT_OP:
        label_t = re.search(r'store at temperatures not exceeding\s*(-?\d+(?:[.,]\d+)?)\s*°\s*c', ctx.s2)
        ctrl = re.search(r'control temperature\s*:?\s*(-?\d+(?:[.,]\d+)?)\s*°\s*c', ctx.text(14) + ' ' + ctx.text(7))
        need_t = label_t or ctrl or 'P411' in ctx.Psingle
        st = re.search(TEMP, s72)
        if need_t and not st:
            ctx.one('7.2', '7-B3', 'fail', s72[:150], 'Maximum storage temperature (P411' + (f': {label_t.group(1)} °C on the label' if label_t else '') + ')', 'CLP IV P411', 'store:temp')
        elif need_t and st and label_t and float(st.group(1).replace(',', '.')) > float(label_t.group(1).replace(',', '.')):
            ctx.one('7.2 ↔ 2', '7-B3', 'fail', s72[:150], f'7.2 storage limit {st.group(1)} °C exceeds the label P411 limit {label_t.group(1)} °C', 'CLP IV P411', 'store:temp')
        want = []
        if not re.search(r'original (?:container|packaging)', s7):
            want.append(('store:original', 'keep only in original packaging (P234)'))
        if not re.search(r'separat', s72):
            want.append(('store:separately', 'store separately (P420)'))
        if not re.search(r'sunlight|light', s72):
            want.append(('store:sunlight', 'protect from sunlight (P410)'))
        if want:
            ctx.add('7.2', '7-B3', 'warning', s72[:150], '; '.join(t for _, t in want), 'CLP IV P234, P420, P410',
                    items=[{'key': k, 'status': 'warning', 'text': t} for k, t in want], prefix='')
    if H & WATER_REACT and not re.search(r'dry|moisture|humid|water', s72):
        ctx.one('7.2', '7-B4', 'fail', s72[:150], 'Protect from moisture; store dry and closed (P231+P232, P402+P404)', 'CLP IV', 'store:dry')
    if H & PYRO and not re.search(r'inert|nitrogen|argon|exclude air|contact with air', s7):
        ctx.one('7.1/7.2', '7-B5', 'fail', s7[:150], 'Handle and store under inert gas; no contact with air (P222, P231)', 'CLP IV', 'store:inert')
    if H & SELF_HEAT and not re.search(r'air gap|stack|bulk|quantit', s72):
        ctx.one('7.2', '7-B6', 'warning', s72[:150], 'Air gap between stacks / bulk limits (P407, P413)', 'CLP IV P407, P413', 'store:self-heat')
    if H & {'H280', 'H281'} and not re.search(r'sunlight|ventilat', s72):
        ctx.one('7.2', '7-B7', 'warning', s72[:150], 'Protect from sunlight; store in a well-ventilated place (P410+P403)', 'CLP IV P410+P403', 'store:gas')
    if H & {'H229', 'H222', 'H223'} and not re.search(r'50\s*°\s*c|122\s*°\s*f', s72):
        ctx.one('7.2', '7-B7', 'warning', s72[:150], 'Do not expose to temperatures exceeding 50 °C (P410+P412)', 'CLP IV P410+P412', 'store:aerosol')
    if H & (EXPLOSIVE | DESENS):
        if not re.search(r'in accordance with|regulation|licen[cs]|magazine|explosives regulations', s72):
            ctx.one('7.2', '7-B8', 'fail', s72[:150], 'Store in accordance with the applicable explosives regulations (P401)', 'CLP IV P401', 'store:regs')
        want = []
        if H & EXPLOSIVE and not re.search(r'original (?:container|packaging)', s7):
            want.append(('store:original', 'keep only in original packaging (P234)'))
        if H & EXPLOSIVE and not re.search(r'grind|shock|friction|impact', s7):
            want.append(('h:shock', 'do not subject to grinding/shock/friction (P250)'))
        if want:
            ctx.add('7.1/7.2', '7-B8', 'warning', s7[:150], '; '.join(t for _, t in want), 'CLP IV P234, P250',
                    items=[{'key': k, 'status': 'warning', 'text': t} for k, t in want], prefix='')
    if 'H290' in H and not re.search(r'original (?:container|packaging)|corrosion[- ]resistant|resistant inner liner|metal container|non-metallic', s72):
        ctx.one('7.2', '7-B9', 'warning', s72[:150], 'Original packaging or corrosion-resistant container (P234/P406)', 'CLP IV P234, P406', 'store:container')
    if H & INHAL and not re.search(r'ventilat|exhaust|fume hood|outdoors|extraction', s7):
        ctx.one('7.1', '7-B10', 'warning', s71[:150], 'Use only outdoors or in a well-ventilated area; avoid breathing vapour/mist (P271/P261)', 'CLP IV P261, P271', 'h:vent')
    if 'H317' in H and not re.search(r'work clothing|contaminated cloth', s7):
        ctx.one('7.1', '7-B10', 'warning', s71[:150], 'Contaminated work clothing should not be allowed out of the workplace (P272)', 'CLP IV P272', 'h:clothing')
    if H & (AQUATIC_HIGH | AQUATIC_LOW) and not re.search(r'environment|drain|release|sewer', s7):
        ctx.one('7.1', '7-B11', 'warning' if ctx.EUGB else 'info', s71[:150], 'Avoid release to the environment (P273)', 'CLP IV P273', 'env:release')
    if 'EUH019' in H and not re.search(r'date|shelf life|peroxide test|test for peroxides', s7):
        ctx.one('7.2', '7-B12', 'warning', s72[:150], 'Opening date, test interval or shelf life for a peroxide former', 'Prudent Practices (good practice)', 'store:peroxide')
    if re.search(r'combustible dust|dust explosion|explosible dust', ctx.s2 + ' ' + low(norm((ctx.sec(9) or {}).get('text', '')))) and 'dust' not in s7:
        ctx.one('7.1', '7-B13', 'warning', s71[:150], 'Avoid dust formation and accumulation; control ignition sources (combustible dust)', 'ATEX/DSEAR; 1910.1200(c); NFPA 652', 'h:dust')
    if 'H281' in H and not re.search(r'cold[- ]insulating gloves|cryogenic gloves|insulated gloves', s71 + ' ' + s7):
        ctx.one('7.1', '7-B14', 'warning', s71[:150], 'Wear cold-insulating gloves and either face shield or eye protection when handling (P282)', 'CLP IV P282', 'h:cryo')
    # C rows
    s9 = low(norm((ctx.sec(9) or {}).get('text', '')))
    sadt = re.search(r'(?:sadt|self-accelerating decomposition temperature)[^0-9\-]{0,40}(-?\d+(?:[.,]\d+)?)\s*°\s*c', s9)
    st = re.search(TEMP, s72)
    if sadt and st and float(st.group(1).replace(',', '.')) >= float(sadt.group(1).replace(',', '.')):
        ctx.one('7.2 ↔ 9', '7-C2', 'fail', s72[:150], f'Storage limit {st.group(1)} °C is not below the SADT {sadt.group(1)} °C in Section 9', 'Annex II 7.2 ("consistent with … section 9")', 'store:temp')
    s82 = ctx.text(8)
    if re.search(r'local exhaust|exhaust ventilation|fume hood|extraction', s82) and not (re.search(ti.SYNONYMS['ventilation'], s71) or ti.refers_to(s71, '8')):
        ctx.one('7.1 ↔ 8', '7-C3', 'warning', s71[:150], 'Handling controls consistent with 8.2 engineering controls (ventilation/LEV)', 'Annex II 7, 8.2', 'h:vent')
    seveso = H & (EXPLOSIVE | FLAM_GAS | {'H224', 'H225', 'H240', 'H241', 'H242', 'H250', 'H260', 'H271', 'H272', 'H300', 'H310', 'H330', 'H331', 'H400', 'H410', 'H411'})
    if ctx.EUGB and seveso and not re.search(r'seveso|2012/18|comah', low(ctx.full)):
        ctx.add('7.2 ↔ 15', '7-C4', 'info', '', 'Major-hazard status (Seveso III / GB COMAH 2015) worth noting for storage quantities: classification includes ' + ', '.join(sorted(seveso)), 'Seveso III; COMAH 2015')
    # D rows
    for c, card in ctx.icsc():
        stc = low(card.get('storage_cell') or card.get('storage'))
        if not stc:
            continue
        want = []
        for rx, lab, key, rx72 in ((r'\bdry\b', 'dry', 'store:dry', r'dry|moisture'), (r'\bcool\b', 'cool', 'store:cool', r'cool|temperature|refrigerat'),
                                   (r'keep in the dark', 'keep in the dark', 'store:sunlight', r'dark|light|sunlight'),
                                   (r'fireproof', 'fireproof', 'store:fire', r'fireproof|fire-?resistant|flammables? (?:area|cabinet|store)'),
                                   (r'without drain or sewer access', 'area without drain or sewer access', 'env:drains-store', r'drain|sewer')):
            if re.search(rx, stc) and not re.search(rx72, s72):
                want.append((key, lab))
        for fam in sorted(s10.families_in(re.split(r'see chemical dangers', stc)[0].split('separated from', 1)[1] if 'separated from' in stc else '') - {'air'}):
            if fam not in s10.families_in(s72) and not (ti.refers_to(s72, '10') or re.search(r'10\.5|incompatible materials', s72)):
                want.append(('fam:' + fam, 'separated from ' + fam))
        kind_of = {'store:fire': {'flammability'}, 'env:drains-store': {'environment'}, 'store:dry': {'water_reactive'}}
        items = []
        for k, lab in want:
            base = 'info' if (k.startswith('env') and not ctx.EUGB) else 'warning'
            st = ctx.allow(c, kind_of.get(k, {'reactivity'}), base, f'ICSC {card["card"]}')
            if st:
                items.append({'key': k, 'status': st, 'text': lab})
        if items:
            ctx.add('7.2', '7-D1', refgate.strongest(*[x['status'] for x in items]), s72[:150], f'ICSC {card["card"]} storage: ' + '; '.join(x['text'] for x in items),
                    f'ICSC {card["card"]}', items=items, prefix=f'ICSC {card["card"]} storage: ')


RUNNERS = {'5': run5, '6': run6, '7': run7}


def run(sds, lookup_dir, declared, sds_type, section='5'):
    ctx = Ctx(sds, lookup_dir, declared, sds_type)
    RUNNERS[section](ctx)
    return {'jurisdiction': ctx.juris, 'H': sorted(ctx.H), 'findings': dedupe(ctx.findings), 'gating': ctx.gate.notes}


def runner(section):
    return lambda sds, lk, decl, typ: run(sds, lk, decl, typ, section)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sds_json'); ap.add_argument('lookup_dir')
    ap.add_argument('--declared', choices=['EU', 'GB', 'US']); ap.add_argument('--type', choices=['substance', 'mixture'], required=True)
    ap.add_argument('--section', choices=['5', '6', '7'], action='append')
    ap.add_argument('--out')
    a = ap.parse_args()
    sds = json.load(open(a.sds_json)); sds['_path'] = a.sds_json
    out = {}
    for sec in a.section or ['5', '6', '7']:
        res = run(sds, a.lookup_dir, a.declared, a.type, sec)
        out[sec] = res
        print(f"== Section {sec}  (jurisdiction {res['jurisdiction']['detected']}{', MISMATCH' if res['jurisdiction']['mismatch'] else ''}; H: {', '.join(res['H'])})")
        for f in res['findings']:
            print(f"  {f['check']:<7} {f['status']:<8} {f['sds_says'][:70]!r} -> {f['expected'][:120]}")
        import coverage
        have = any(k.startswith('lookup_') and k[7:-5] in sds['codes_all']['CAS'] and not k.endswith('7732-18-5.json') for k in os.listdir(a.lookup_dir))
        coverage.print_not_run(sec, a.declared or res['jurisdiction']['detected'], a.type, have)
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1, ensure_ascii=False)
