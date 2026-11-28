"""Build the bundled CLP legal tables from the EU consolidated text (EUR-Lex / Publications Office Cellar).

  python3 -I tools/legal_tables.py CLP_TEXT.txt --celex 02008R1272-20270101 --retrieved 2026-11-27

CLP_TEXT.txt is the consolidated CLP flattened to text (one table row per line, prefixed "[ROW] ", cells separated
by " | "), as produced from the Cellar XHTML during this project. Writes:

  data/legal/clp_annex_iv_eu_<date>.json   Annex IV Part 1: every P-statement with wording, and each
                                            (hazard class, categories, conditions for use) row
  data/legal/clp_category_h_eu_<date>.json  Annex I label tables: hazard class + category -> H/EUH codes

Reuse: EU legal texts may be reused with credit to the source; changes are marked (Commission reuse policy, as
confirmed by the user on 28 Nov 2026). Change made here: extracted from the consolidated text and restructured
as JSON; wording is unchanged.
"""
import argparse
import datetime
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Annex IV hazard-class cells -> stable keys (matched in order; section numbers decide where words are ambiguous)
CLASS_KEYS = [
    (r'^explosives', 'explosives'), (r'^desensitised explosives', 'desensitised_explosives'),
    (r'^flammable gases', 'flammable_gases'), (r'^aerosols', 'aerosols'), (r'^oxidising gases', 'oxidising_gases'),
    (r'^gases under pressure', 'gases_under_pressure'), (r'^flammable liquids', 'flammable_liquids'),
    (r'^oxidi[sz]ing gases', 'oxidising_gases'), (r'^oxidi[sz]ing liquids', 'oxidising_liquids'), (r'^oxidi[sz]ing solids', 'oxidising_solids'),
    (r'^flammable solids', 'flammable_solids'), (r'^self-reactive', 'self_reactive'), (r'^pyrophoric liquids', 'pyrophoric_liquids'),
    (r'^pyrophoric solids', 'pyrophoric_solids'), (r'^self-heating', 'self_heating'),
    (r'in contact with water, emit flammable gases', 'water_reactive'), (r'^oxidising liquids', 'oxidising_liquids'),
    (r'^oxidising solids', 'oxidising_solids'), (r'^organic peroxides', 'organic_peroxides'),
    (r'^corrosive to metals', 'corrosive_to_metals'),
    (r'^acute toxicity\s*[–—-]\s*oral', 'acute_oral'), (r'^acute toxicity\s*,?\s*[–—-]?\s*dermal', 'acute_dermal'),
    (r'^acute toxicity\s*[–—-]\s*inhalation', 'acute_inhalation'),
    (r'^skin corrosion', 'skin_corrosion'), (r'^skin irritation', 'skin_irritation'),
    (r'^serious eye damage', 'eye_damage'), (r'^eye irritation', 'eye_irritation'),
    (r'^respiratory sensitisation', 'respiratory_sensitisation'), (r'^skin sensitisation', 'skin_sensitisation'),
    (r'^germ cell mutagenicity', 'mutagenicity'), (r'^carcinogenicity', 'carcinogenicity'),
    (r'^reproductive toxicity\s*[,—–-]*\s*effects on or via lactation', 'lactation'), (r'^reproductive toxicity', 'reproductive_toxicity'),
    (r'^specific target organ toxicity\s*[,–—-]\s*single exposure;\s*respiratory tract irritation', 'stot_se_3_resp'),
    (r'^specific target organ toxicity\s*[,–—-]\s*single exposure;\s*narco', 'stot_se_3_narc'),
    (r'^specific target organ toxicity\s*[,–—-]\s*single exposure', 'stot_se'),
    (r'^specific target organ toxicity\s*[,–—-]\s*repeated exposure', 'stot_re'),
    (r'^aspiration hazard', 'aspiration'),
    (r'^hazardous to the aquatic environment\s*[–—-]\s*acute', 'aquatic_acute'),
    (r'^hazardous to the aquatic environment\s*[–—-]\s*(?:chronic|long-term)', 'aquatic_chronic'),
    (r'^hazardous to the aquatic environment\s*[–—-]\s*short-term', 'aquatic_acute'),
    (r'^hazardous to the ozone layer', 'ozone'),
]


def class_key(cell):
    c = ' '.join(re.sub(r'[►◄]\w*', ' ', cell).split()).lower()
    for rx, key in CLASS_KEYS:
        if re.search(rx, c):
            return key
    return None


def categories(cell):
    """'1A,1B, 2' -> ['1A','1B','2']; 'Types A, B, C' -> ['A','B','C']; 'Divisions 1.1, 1.2' -> ['1.1','1.2'];
    named categories ('Unstable explosive', 'Compressed gas', 'Additional category') are kept as text."""
    c = ' '.join(cell.replace('▼M19', ' ').split())
    if not c or c.lower() == 'as appropriate':
        return [c] if c else []
    out = []
    for part in re.split(r',| and ', c):
        p = part.strip()
        p = re.sub(r'^(?:types?|divisions?|categor(?:y|ies)|sub-?categor(?:y|ies))\s+', '', p, flags=re.I)
        p = re.sub(r'\s*\(.*\)$', '', p)
        p = re.sub(r'^unstable explosives$', 'Unstable explosive', p, flags=re.I)
        if re.fullmatch(r'(?:(?:compressed|liquefied|refrigerated liquefied|dissolved) gas\s*)+', p, re.I):
            out += [g.strip().capitalize() for g in re.findall(r'(?:refrigerated liquefied|compressed|liquefied|dissolved) gas', p, re.I)]
        elif p:
            out.append(p)
    return out


CATEGORY_ONLY = re.compile(r'^(?:divisions?\s|types?\s|categor(?:y|ies)\s|compressed gas|liquefied gas|refrigerated liquefied gas|dissolved gas)', re.I)
CODE = re.compile(r'^\[?P\d{3}\]?(?:\s*\+\s*\[?P\d{3}\]?)*$')


def norm_code(c):
    return re.sub(r'\s*\+\s*', '+', c.strip())


def parse_annex_iv(lines):
    start = next(i for i, l in enumerate(lines) if l.strip().startswith('1. Part 1: Criteria for the selection of precautionary statements'))
    end = next(i for i in range(start, len(lines)) if lines[i].strip().startswith('2. Part 2: precautionary statements'))
    stmts, order, cur, table = {}, [], None, None
    last_cond = ''
    for l in lines[start:end]:
        m = re.match(r'Table (6\.\d)', l.strip())
        if m:
            table = m.group(1)
            continue
        if not l.startswith('[ROW]'):
            continue
        cells = [c.strip() for c in l[5:].split('|')]
        cells = [re.sub(r'▼\w+\s*', '', c).strip() for c in cells]
        if not any(cells) or cells[0] in ('Code', '(1)') or re.fullmatch(r'—+', ''.join(cells)):
            continue
        if CODE.match(cells[0]):
            code = norm_code(cells[0])
            text = cells[1] if len(cells) > 1 else ''
            cur = stmts.setdefault(code, {'code': code, 'text': text, 'table': table, 'rows': []})
            if code not in order:
                order.append(code)
            rest = cells[2:]
        elif cur is not None:
            rest = cells
        else:
            continue
        if not rest or not rest[0]:
            continue
        prev = cur['rows'][-1] if cur['rows'] else None
        if CATEGORY_ONLY.match(rest[0]) and class_key(rest[0]) is None and prev:
            # category-only row: the hazard class cell above spans it
            cls_cell, cat_cell = prev['class'], rest[0]
            if len(rest) > 1:
                last_cond = rest[1]
        else:
            cls_cell = rest[0]
            if len(rest) > 1:
                cat_cell = rest[1]
            elif prev:
                cat_cell = prev['categories_text']       # class-only row: the categories cell above spans it
            else:
                cat_cell = ''
            if len(rest) > 2:
                last_cond = rest[2]
        # a missing conditions cell continues the merged cell above (rowspan)
        cur['rows'].append({'class': cls_cell, 'class_key': class_key(cls_cell), 'categories_text': cat_cell,
                            'categories': categories(cat_cell), 'conditions': last_cond})
    return [stmts[c] for c in order]


def parse_category_h(lines):
    """Annex I label tables: (class key, category) -> H/EUH codes, from the 'Classification' and 'Hazard Statement'
    rows; tables printed as one flattened line are read with explicit category lists (see FLAT)."""
    out = []
    head = lines[:5400]
    titles = {'explosives': 'explosives', 'aerosol': 'aerosols', 'oxidising gases': 'oxidising_gases',
              'gases under pressure': 'gases_under_pressure', 'flammable liquids': 'flammable_liquids',
              'flammable solids': 'flammable_solids', 'self-reactive': 'self_reactive', 'pyrophoric liquids': 'pyrophoric_liquids',
              'pyrophoric solids': 'pyrophoric_solids', 'self-heating': 'self_heating', 'in contact with water': 'water_reactive',
              'oxidising liquids': 'oxidising_liquids', 'organic peroxides': 'organic_peroxides', 'corrosive to metals': 'corrosive_to_metals',
              'germ cell mutagenicity': 'mutagenicity', 'carcinogenicity': 'carcinogenicity', 'reproductive toxicity': 'reproductive_toxicity',
              'single exposure': 'stot_se', 'repeated exposure': 'stot_re', 'aspiration': 'aspiration',
              'endocrine disruption for human health': 'ed_human_health', 'endocrine disruption for the environment': 'ed_environment'}
    for i, l in enumerate(head):
        if not l.startswith('[ROW] Classification |'):
            continue
        title = next((head[k] + ' ' + head[k + 1] for k in range(i, max(0, i - 40), -1) if re.match(r'^Table \d', head[k])), '')
        key = next((v for k, v in titles.items() if k in title.lower()), None)
        hrow = next((head[j] for j in range(i + 1, i + 8) if re.match(r'\[ROW\] Hazard [Ss]tatement', head[j])), None)
        if not key or not hrow:
            continue
        cats = [c.strip() for c in l.split('|')[1:]]
        hs = [re.findall(r'(?:EU)?H\d{3}', c) for c in hrow.split('|')[1:]]
        for c, h in zip(cats, hs):
            if not h:
                continue
            k = key
            if re.search(r'lactation', c, re.I):
                k, toks = 'lactation', ['Additional category']
            elif key == 'stot_se' and re.search(r'\b3\b', c):
                continue                                   # Category 3 is split by effect in FLAT
            else:
                toks = label_categories(c)
            for t in toks:
                out.append({'class_key': k, 'category': t, 'h': h, 'source': title.strip()[:80]})
    return out


def label_categories(c):
    """Annex I column heads -> Annex IV category tokens: 'Category 1 (Category 1A, 1B)' -> ['1', '1A', '1B'],
    'Type C & D' -> ['C', 'D'], 'Division 1.1' -> ['1.1'], 'Unstable Explosive' -> ['Unstable explosive']."""
    c = ' '.join(c.split())
    m = re.match(r'Category (\w+) \(Category ([\w, ]+)\)', c)
    if m:
        return [m.group(1)] + [x.strip() for x in m.group(2).split(',')]
    m = re.match(r'Types? ([A-G](?:\s*&\s*[A-G])*)$', c)
    if m:
        return [x.strip() for x in m.group(1).split('&')]
    m = re.match(r'(?:Category|Division) ([\w.]+)$', c)
    if m:
        return [m.group(1)]
    named = {'pbt': 'PBT', 'vpvb': 'vPvB', 'pmt': 'PMT', 'vpvm': 'vPvM'}
    if c.lower() in named:
        return [named[c.lower()]]
    c = re.sub(r'\s*\(\s*\d+\s*\)$', '', c)
    return [c[0].upper() + c[1:].lower()]


def parse_annex_i_p(lines):
    """Annex I label tables: per column (class, category) the signal word and the precautionary statements listed.
    Used as the source for the classes added by Regulation (EU) 2023/707 (no Annex IV Part 1 rows) and to cross-check
    the Annex IV extraction for the other classes."""
    out = []
    titles = TITLES
    i = 0
    head = lines[:5400]
    while i < len(head):
        if not re.match(r'^Table \d+\.\d+(?:\.\d+)*\.?$', head[i].strip()):
            i += 1
            continue
        title = head[i].strip() + ' ' + head[i + 1].strip()
        key = next((v for k, v in sorted(titles.items(), key=lambda kv: -len(kv[0])) if k in title.lower()), None)
        j, cols, rows = i + 2, None, []
        while j < len(head) and head[j].startswith('[ROW]'):
            cells = [c.strip() for c in head[j][5:].split('|')]
            rows.append(cells)
            j += 1
        i = j
        if not key or not rows:
            continue
        hdr = next((r for r in rows if r[0] in ('Classification', '')), None)
        if not hdr:
            continue
        cols = hdr[1:]
        classes = [key] * len(cols)
        if key == 'sensitisation':
            classes = ['respiratory_sensitisation', 'skin_sensitisation']
            cols = ['1', '1']
        signal = next((r[1:] for r in rows if re.match(r'Signal [Ww]ord', r[0])), [''] * len(cols))
        for r in rows:
            m = re.match(r'Precautionary [Ss]tatements? (Prevention|Response|Storage|Disposal)(?: \((oral|dermal|inhalation)\))?', r[0])
            if not m:
                continue
            for n, cell in enumerate(r[1:len(cols) + 1]):
                ck = classes[n]
                if key == 'acute':
                    ck = 'acute_' + m.group(2)
                toks = label_categories(cols[n]) if key != 'sensitisation' else ['1', '1A', '1B']
                pairs = [(ck, t) for t in toks]
                if ck == 'reproductive_toxicity' and re.search('lactation', cols[n], re.I):
                    pairs = [('lactation', 'Additional category')]
                elif ck == 'stot_se' and toks == ['3']:
                    pairs = [('stot_se_3_resp', '3'), ('stot_se_3_narc', '3')]
                for ck2, t in pairs:
                    codes = [norm_code(c) for c in re.findall(r'P\d{3}(?:\s*\+\s*\[?P\d{3}\]?)*', cell.replace('[+', '+['))]
                    out.append({'class_key': ck2, 'category': t, 'kind': m.group(1).lower(), 'p': codes,
                                'signal': signal[n] if n < len(signal) else '', 'source': title[:80]})
    merged = {}
    for e in out:
        k = (e['class_key'], e['category'])
        m = merged.setdefault(k, {'class_key': k[0], 'category': k[1], 'p': [], 'signal': e['signal'], 'source': e['source']})
        m['p'] += [c for c in e['p'] if c not in m['p']]
    return list(merged.values())


TITLES = {'explosives': 'explosives', 'aerosol': 'aerosols', 'oxidising gases': 'oxidising_gases',
          'gases under pressure': 'gases_under_pressure', 'flammable liquids': 'flammable_liquids',
          'flammable solids': 'flammable_solids', 'self-reactive': 'self_reactive', 'pyrophoric liquids': 'pyrophoric_liquids',
          'pyrophoric solids': 'pyrophoric_solids', 'self-heating': 'self_heating', 'in contact with water': 'water_reactive',
          'oxidising liquids': 'oxidising_liquids', 'oxidising solids': 'oxidising_solids', 'organic peroxides': 'organic_peroxides',
          'corrosive to metals': 'corrosive_to_metals', 'desensitised explosives': 'desensitised_explosives',
          'acute toxicity label': 'acute', 'sensitisation label': 'sensitisation',
          'germ cell mutagenicity': 'mutagenicity', 'carcinogenicity': 'carcinogenicity', 'reproductive toxicity': 'reproductive_toxicity',
          'single exposure': 'stot_se', 'repeated exposure': 'stot_re', 'aspiration': 'aspiration',
          'endocrine disruption for human health': 'ed_human_health', 'endocrine disruption for the environment': 'ed_environment',
          'pbt and vpvb': 'pbt', 'pmt and vpvm': 'pmt'}


# Annex I tables flattened into a single line (skin, eye, acute dermal/inhalation, sensitisation, aquatic, ozone,
# flammable gases, oxidising solids, desensitised explosives, PBT/PMT). Each entry was read from the consolidated
# text (table and row named) and is checked against that text by tools/legal_tables.py --check.
FLAT = [
    ('aerosols', '1', ['H222', 'H229'], 'Table 2.3.2'), ('aerosols', '2', ['H223', 'H229'], 'Table 2.3.2'), ('aerosols', '3', ['H229'], 'Table 2.3.2'),
    ('flammable_gases', '1A', ['H220'], 'Table 2.2.2'), ('flammable_gases', 'Pyrophoric gas', ['H220', 'H232'], 'Table 2.2.2'),
    ('flammable_gases', 'A', ['H220', 'H230'], 'Table 2.2.2 (chemically unstable gas A)'),
    ('flammable_gases', 'B', ['H220', 'H231'], 'Table 2.2.2 (chemically unstable gas B)'),
    ('flammable_gases', '1B', ['H221'], 'Table 2.2.2'), ('flammable_gases', '2', ['H221'], 'Table 2.2.2'),
    ('oxidising_solids', '1', ['H271'], 'Table 2.14.2'), ('oxidising_solids', '2', ['H272'], 'Table 2.14.2'), ('oxidising_solids', '3', ['H272'], 'Table 2.14.2'),
    ('desensitised_explosives', '1', ['H206'], 'Table 2.17.2'), ('desensitised_explosives', '2', ['H207'], 'Table 2.17.2'),
    ('desensitised_explosives', '3', ['H207'], 'Table 2.17.2'), ('desensitised_explosives', '4', ['H208'], 'Table 2.17.2'),
    ('acute_oral', '1', ['H300'], 'Table 3.1.3'), ('acute_oral', '2', ['H300'], 'Table 3.1.3'), ('acute_oral', '3', ['H301'], 'Table 3.1.3'), ('acute_oral', '4', ['H302'], 'Table 3.1.3'),
    ('acute_dermal', '1', ['H310'], 'Table 3.1.3'), ('acute_dermal', '2', ['H310'], 'Table 3.1.3'), ('acute_dermal', '3', ['H311'], 'Table 3.1.3'), ('acute_dermal', '4', ['H312'], 'Table 3.1.3'),
    ('acute_inhalation', '1', ['H330'], 'Table 3.1.3'), ('acute_inhalation', '2', ['H330'], 'Table 3.1.3'), ('acute_inhalation', '3', ['H331'], 'Table 3.1.3'), ('acute_inhalation', '4', ['H332'], 'Table 3.1.3'),
    ('skin_corrosion', '1', ['H314'], 'Table 3.2.5'), ('skin_corrosion', '1A', ['H314'], 'Table 3.2.5'), ('skin_corrosion', '1B', ['H314'], 'Table 3.2.5'), ('skin_corrosion', '1C', ['H314'], 'Table 3.2.5'),
    ('skin_irritation', '2', ['H315'], 'Table 3.2.5'), ('eye_damage', '1', ['H318'], 'Table 3.3.5'), ('eye_irritation', '2', ['H319'], 'Table 3.3.5'),
    ('respiratory_sensitisation', '1', ['H334'], 'Table 3.4.7'), ('respiratory_sensitisation', '1A', ['H334'], 'Table 3.4.7'), ('respiratory_sensitisation', '1B', ['H334'], 'Table 3.4.7'),
    ('skin_sensitisation', '1', ['H317'], 'Table 3.4.7'), ('skin_sensitisation', '1A', ['H317'], 'Table 3.4.7'), ('skin_sensitisation', '1B', ['H317'], 'Table 3.4.7'),
    ('lactation', 'Additional category', ['H362'], 'Table 3.7.3'),
    ('stot_se_3_resp', '3', ['H335'], 'Table 3.8.4'), ('stot_se_3_narc', '3', ['H336'], 'Table 3.8.4'),
    ('aquatic_acute', '1', ['H400'], 'Table 4.1.4'), ('aquatic_chronic', '1', ['H410'], 'Table 4.1.4'), ('aquatic_chronic', '2', ['H411'], 'Table 4.1.4'),
    ('aquatic_chronic', '3', ['H412'], 'Table 4.1.4'), ('aquatic_chronic', '4', ['H413'], 'Table 4.1.4'),
    ('ozone', '1', ['H420'], 'Table 5.2'),
    ('pbt', 'PBT', ['EUH440'], 'Table 4.3.x (PBT/vPvB)'), ('pbt', 'vPvB', ['EUH441'], 'Table 4.3.x (PBT/vPvB)'),
    ('pmt', 'PMT', ['EUH450'], 'Table 4.4.x (PMT/vPvM)'), ('pmt', 'vPvM', ['EUH451'], 'Table 4.4.x (PMT/vPvM)'),
]


# Annex VI Table 1.1 hazard class and category codes -> (class key, categories). Acute Tox. and STOT SE 3 need the
# H-code for the route/effect; Press. Gas needs H280/H281. Each code is checked against the Table 1.1 text.
ANNEX_VI_CODES = [
    ('Unst. Expl.', 'explosives', ['Unstable explosive']), ('Expl. 1.1', 'explosives', ['1.1']), ('Expl. 1.2', 'explosives', ['1.2']),
    ('Expl. 1.3', 'explosives', ['1.3']), ('Expl. 1.4', 'explosives', ['1.4']), ('Expl. 1.5', 'explosives', ['1.5']),
    ('Expl. 1.6', 'explosives', ['1.6']),
    ('Flam. Gas 1A', 'flammable_gases', ['1A']), ('Flam. Gas 1B', 'flammable_gases', ['1B']), ('Flam. Gas 2', 'flammable_gases', ['2']),
    ('Pyr. Gas', 'flammable_gases', ['Pyrophoric gas']), ('Chem. Unst. Gas A', 'flammable_gases', ['A']),
    ('Chem. Unst. Gas B', 'flammable_gases', ['B']),
    ('Aerosol 1', 'aerosols', ['1']), ('Aerosol 2', 'aerosols', ['2']), ('Aerosol 3', 'aerosols', ['3']),
    ('Ox. Gas 1', 'oxidising_gases', ['1']), ('Press. Gas', 'gases_under_pressure', ['by H-code']),
    ('Flam. Liq. 1', 'flammable_liquids', ['1']), ('Flam. Liq. 2', 'flammable_liquids', ['2']), ('Flam. Liq. 3', 'flammable_liquids', ['3']),
    ('Flam. Sol. 1', 'flammable_solids', ['1']), ('Flam. Sol. 2', 'flammable_solids', ['2']),
    ('Self-react. A', 'self_reactive', ['A']), ('Self-react. B', 'self_reactive', ['B']), ('Self-react. CD', 'self_reactive', ['C', 'D']),
    ('Self-react. EF', 'self_reactive', ['E', 'F']), ('Self-react. G', 'self_reactive', ['G']),
    ('Pyr. Liq. 1', 'pyrophoric_liquids', ['1']), ('Pyr. Sol. 1', 'pyrophoric_solids', ['1']),
    ('Self-heat. 1', 'self_heating', ['1']), ('Self-heat. 2', 'self_heating', ['2']),
    ('Water-react. 1', 'water_reactive', ['1']), ('Water-react. 2', 'water_reactive', ['2']), ('Water-react. 3', 'water_reactive', ['3']),
    ('Ox. Liq. 1', 'oxidising_liquids', ['1']), ('Ox. Liq. 2', 'oxidising_liquids', ['2']), ('Ox. Liq. 3', 'oxidising_liquids', ['3']),
    ('Ox. Sol. 1', 'oxidising_solids', ['1']), ('Ox. Sol. 2', 'oxidising_solids', ['2']), ('Ox. Sol. 3', 'oxidising_solids', ['3']),
    ('Org. Perox. A', 'organic_peroxides', ['A']), ('Org. Perox. B', 'organic_peroxides', ['B']),
    ('Org. Perox. CD', 'organic_peroxides', ['C', 'D']), ('Org. Perox. EF', 'organic_peroxides', ['E', 'F']),
    ('Org. Perox. G', 'organic_peroxides', ['G']), ('Met. Corr. 1', 'corrosive_to_metals', ['1']),
    ('Desen. Expl. 1', 'desensitised_explosives', ['1']), ('Desen. Expl. 2', 'desensitised_explosives', ['2']),
    ('Desen. Expl. 3', 'desensitised_explosives', ['3']), ('Desen. Expl. 4', 'desensitised_explosives', ['4']),
    ('Acute Tox. 1', 'acute_by_h', ['1']), ('Acute Tox. 2', 'acute_by_h', ['2']), ('Acute Tox. 3', 'acute_by_h', ['3']),
    ('Acute Tox. 4', 'acute_by_h', ['4']),
    ('Skin Corr. 1A', 'skin_corrosion', ['1A']), ('Skin Corr. 1B', 'skin_corrosion', ['1B']), ('Skin Corr. 1C', 'skin_corrosion', ['1C']),
    ('Skin Corr. 1', 'skin_corrosion', ['1']), ('Skin Irrit. 2', 'skin_irritation', ['2']),
    ('Eye Dam. 1', 'eye_damage', ['1']), ('Eye Irrit. 2', 'eye_irritation', ['2']),
    ('Resp. Sens. 1A', 'respiratory_sensitisation', ['1A']), ('Resp. Sens. 1B', 'respiratory_sensitisation', ['1B']),
    ('Resp. Sens. 1', 'respiratory_sensitisation', ['1']),
    ('Skin Sens. 1A', 'skin_sensitisation', ['1A']), ('Skin Sens. 1B', 'skin_sensitisation', ['1B']), ('Skin Sens. 1', 'skin_sensitisation', ['1']),
    ('Muta. 1A', 'mutagenicity', ['1A']), ('Muta. 1B', 'mutagenicity', ['1B']), ('Muta. 2', 'mutagenicity', ['2']),
    ('Carc. 1A', 'carcinogenicity', ['1A']), ('Carc. 1B', 'carcinogenicity', ['1B']), ('Carc. 2', 'carcinogenicity', ['2']),
    ('Repr. 1A', 'reproductive_toxicity', ['1A']), ('Repr. 1B', 'reproductive_toxicity', ['1B']), ('Repr. 2', 'reproductive_toxicity', ['2']),
    ('Lact.', 'lactation', ['Additional category']),
    ('STOT SE 1', 'stot_se', ['1']), ('STOT SE 2', 'stot_se', ['2']), ('STOT SE 3', 'stot_se_3_by_h', ['3']),
    ('STOT RE 1', 'stot_re', ['1']), ('STOT RE 2', 'stot_re', ['2']), ('Asp. Tox. 1', 'aspiration', ['1']),
    ('ED HH 1', 'ed_human_health', ['1']), ('ED HH 2', 'ed_human_health', ['2']),
    ('Aquatic Acute 1', 'aquatic_acute', ['1']), ('Aquatic Chronic 1', 'aquatic_chronic', ['1']),
    ('Aquatic Chronic 2', 'aquatic_chronic', ['2']), ('Aquatic Chronic 3', 'aquatic_chronic', ['3']),
    ('Aquatic Chronic 4', 'aquatic_chronic', ['4']), ('ED ENV 1', 'ed_environment', ['1']), ('ED ENV 2', 'ed_environment', ['2']),
    ('PBT', 'pbt', ['PBT']), ('vPvB', 'pbt', ['vPvB']), ('PMT', 'pmt', ['PMT']), ('vPvM', 'pmt', ['vPvM']), ('Ozone 1', 'ozone', ['1']),
]


def annex_vi_codes(lines):
    start = next(i for i, l in enumerate(lines) if l.strip() == 'Hazard class and category codes')
    table = ' '.join(l for l in lines[start:start + 60] if l.startswith('[ROW]'))
    table = re.sub(r'[►◄]\w*', ' ', table)
    table = ' '.join(table.replace('Skin. Sens.', 'Skin Sens.').split())
    missing = []
    for code, _, _ in ANNEX_VI_CODES:
        base = re.sub(r' 1[AB]$', ' 1', code) if code.startswith(('Resp. Sens.', 'Skin Sens.')) else code
        if base not in table:
            missing.append(code)
    return [{'code': c, 'class_key': k, 'categories': cats} for c, k, cats in ANNEX_VI_CODES], missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('clp_text')
    ap.add_argument('--celex', required=True)
    ap.add_argument('--retrieved', required=True)
    a = ap.parse_args()
    raw = open(a.clp_text, encoding='utf-8').read()
    lines = raw.split('\n')
    date = re.search(r'-(\d{4})(\d{2})(\d{2})$', a.celex)
    version = f'{date.group(1)}-{date.group(2)}-{date.group(3)}' if date else a.celex
    meta = {'source': 'Regulation (EC) No 1272/2008 (CLP), consolidated version ' + version, 'celex': a.celex,
            'url': f'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{a.celex}',
            'retrieved': a.retrieved, 'source_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
            'built': datetime.date.today().isoformat(),
            'reuse': 'EU legal text reused with credit to the source (EUR-Lex). Changes: extracted from the consolidated '
                     'text and restructured as JSON; statement wording unchanged.'}
    os.makedirs(os.path.join(ROOT, 'data', 'legal'), exist_ok=True)
    stmts = parse_annex_iv(lines)
    unknown = sorted({r['class'] for s in stmts for r in s['rows'] if not r['class_key'] and r['class'].lower() != 'as appropriate'})
    p_iv = os.path.join(ROOT, 'data', 'legal', f'clp_annex_iv_eu_{version}.json')
    json.dump({**meta, 'part': 'Annex IV Part 1 (Tables 6.1-6.5)', 'statements': stmts, 'unmapped_class_cells': unknown},
              open(p_iv, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    cat = parse_category_h(lines) + [{'class_key': k, 'category': c, 'h': h, 'source': s} for k, c, h, s in FLAT]
    have = {(e['class_key'], e['category']) for e in cat}
    no_h = sorted({(r['class_key'], c) for st in stmts for r in st['rows'] if r['class_key'] for c in r['categories']} - have)
    if no_h:
        print('Annex IV class/category with no hazard statement mapped:', no_h)
    codes, missing_codes = annex_vi_codes(lines)
    p_c = os.path.join(ROOT, 'data', 'legal', f'clp_annex_vi_codes_eu_{version}.json')
    json.dump({**meta, 'part': 'Annex VI Part 1, Table 1.1: hazard class and category codes (Skin. Sens. read as Skin Sens.)',
               'entries': codes}, open(p_c, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'{len(codes)} Annex VI codes -> {p_c}')
    if missing_codes:
        print('Annex VI codes not found in Table 1.1:', missing_codes)
    lab = parse_annex_i_p(lines)
    p_l = os.path.join(ROOT, 'data', 'legal', f'clp_annex_i_label_p_eu_{version}.json')
    json.dump({**meta, 'part': 'Annex I label-element tables: signal word and precautionary statements per class/category column',
               'entries': lab}, open(p_l, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'{len(lab)} Annex I label columns -> {p_l}')
    missing_flat = [(k, c, h) for k, c, h, s in FLAT if not all(x in raw for x in h)]
    p_h = os.path.join(ROOT, 'data', 'legal', f'clp_category_h_eu_{version}.json')
    json.dump({**meta, 'part': 'Annex I label-element tables: hazard class + category -> hazard statement codes', 'entries': cat},
              open(p_h, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'{len(stmts)} P-statements ({sum(len(s["rows"]) for s in stmts)} class rows) -> {p_iv}')
    print(f'{len(cat)} class/category entries -> {p_h}')
    if unknown:
        print('Class cells not mapped to a key:', unknown)
    if missing_flat:
        print('FLAT entries whose codes are not in the text:', missing_flat)


if __name__ == '__main__':
    main()
