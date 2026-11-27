"""Generate the synthetic test SDSs used by the regression set.

These are SYNTHETIC TEST FIXTURES, not real products or real safety data sheets. Each one is complete enough
to run the checkers and is built to trigger one specific rule:

  synth_rev10_codes            GHS Rev.10 codes (P316/P317) on an EU SDS      -> 2-L2 warning, P316 matched as P310
  synth_asp_tox_vomiting       "induce vomiting" with Asp. Tox. 1 (H304, P331) -> 4-B1 fail (also covers 4-C1)
  synth_oral4_vomiting         "induce vomiting" with Acute Tox. 4 oral only   -> 4-B1 warning

Usage: python3 -I regression/synthetic/make_synthetic.py   (writes .md and .docx next to this script; needs pandoc)
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BANNER = '**SYNTHETIC TEST SDS — NOT A REAL PRODUCT. Regression fixture for the SDS section checker. Do not use for any hazard communication.**'

TITLES = ['Identification of the substance/mixture and of the company/undertaking', 'Hazards identification',
          'Composition/information on ingredients', 'First aid measures', 'Firefighting measures', 'Accidental release measures',
          'Handling and storage', 'Exposure controls/personal protection', 'Physical and chemical properties', 'Stability and reactivity',
          'Toxicological information', 'Ecological information', 'Disposal considerations', 'Transport information',
          'Regulatory information', 'Other information']
SUBS = {1: ['Product identifier', 'Relevant identified uses', 'Details of the supplier of the safety data sheet', 'Emergency telephone number'],
        2: ['Classification of the substance or mixture', 'Label elements', 'Other hazards'],
        3: ['Substances'], 4: ['Description of first aid measures', 'Most important symptoms and effects, both acute and delayed',
                               'Indication of any immediate medical attention and special treatment needed'],
        5: ['Extinguishing media', 'Special hazards arising from the substance or mixture', 'Advice for firefighters'],
        6: ['Personal precautions, protective equipment and emergency procedures', 'Environmental precautions',
            'Methods and material for containment and cleaning up', 'Reference to other sections'],
        7: ['Precautions for safe handling', 'Conditions for safe storage, including any incompatibilities', 'Specific end use(s)'],
        8: ['Control parameters', 'Exposure controls'], 9: ['Information on basic physical and chemical properties', 'Other information'],
        10: ['Reactivity', 'Chemical stability', 'Possibility of hazardous reactions', 'Conditions to avoid', 'Incompatible materials',
             'Hazardous decomposition products'],
        11: ['Information on hazard classes as defined in Regulation (EC) No 1272/2008'], 12: ['Toxicity'], 13: ['Waste treatment methods'],
        14: ['UN number or ID number'], 15: ['Safety, health and environmental regulations/legislation specific for the substance or mixture'],
        16: ['Other information']}

COMMON = {
    (1, 1): 'Product name: SYNTHETIC TEST PRODUCT {tag} (fictitious). No CAS number: synthetic test component.',
    (1, 2): 'Regression testing of the SDS section checker only.',
    (1, 3): 'SYNTHETIC TEST FIXTURE: not a real company and no real address.',
    (1, 4): 'None: synthetic test document.',
    (2, 3): 'None known for this synthetic fixture.',
    (5, 1): 'Suitable extinguishing media: water spray, dry chemical, carbon dioxide. Unsuitable extinguishing media: none known.',
    (5, 2): 'Hazardous combustion products: carbon monoxide, carbon dioxide.',
    (5, 3): 'Wear self-contained breathing apparatus.',
    (6, 1): 'Use personal protective equipment. Ensure adequate ventilation.',
    (6, 2): 'Do not let product enter drains.', (6, 3): 'Soak up with inert absorbent material.', (6, 4): 'See Sections 8 and 13.',
    (7, 1): 'Avoid contact with skin and eyes.', (7, 2): 'Keep container tightly closed. Store separately from strong oxidising agents.',
    (7, 3): 'Laboratory use.', (8, 1): 'No occupational exposure limits (synthetic fixture).', (8, 2): 'Wear protective gloves and eye protection.',
    (9, 1): 'Physical state: liquid. Colour: colourless. Decomposition temperature: no decomposition observed up to 200 °C.',
    (9, 2): 'No further information.',
    (10, 1): 'Not reactive under normal conditions of use; reacts with strong oxidising agents (synthetic fixture, class data).',
    (10, 2): 'Stable under recommended storage conditions of temperature and pressure; no stabiliser needed.',
    (10, 3): 'Reacts with strong oxidising agents, generating heat. No hazardous polymerisation.',
    (10, 4): 'Heat and contact with incompatible materials.', (10, 5): 'Strong oxidising agents.',
    (10, 6): 'None known under normal storage and use; on heating, carbon oxides (see Section 5).',
    (12, 1): 'No data: synthetic fixture.', (13, 1): 'Dispose of as hazardous waste.', (14, 1): 'Not regulated (synthetic fixture).',
    (15, 1): 'This document follows the format of Regulation (EU) 2020/878 for testing only.',
    (16, 1): 'Synthetic regression fixture generated by make_synthetic.py. Not a real safety data sheet.',
}

CASES = {
    'synth_rev10_codes': {
        'tag': 'R10',
        (2, 1): 'Skin Corr. 1B, H314.',
        (2, 2): 'Signal word: Danger. Hazard statements: H314 Causes severe skin burns and eye damage. '
                'Precautionary statements: P280 Wear protective gloves/protective clothing/eye protection/face protection. '
                'P301+P330+P331 IF SWALLOWED: Rinse mouth. Do NOT induce vomiting. '
                'P303+P361+P353 IF ON SKIN (or hair): Take off immediately all contaminated clothing. Rinse skin with water or shower. '
                'P305+P351+P338 IF IN EYES: Rinse cautiously with water for several minutes. Remove contact lenses, if present and easy to do. Continue rinsing. '
                'P316 Get emergency medical help immediately. P317 Get medical help.',
        (3, 1): 'Synthetic corrosive component (no CAS): 100 %. Skin Corr. 1B, H314.',
        (4, 1): ['General advice: Get emergency medical help immediately. First-aiders: wear protective gloves and eye protection.',
                 'Inhalation: Remove to fresh air and keep comfortable for breathing. Get medical help immediately.',
                 'Skin contact: Take off immediately all contaminated clothing and shoes. Rinse skin with water or shower. Get medical help immediately.',
                 'Eye contact: Rinse cautiously with water for several minutes. Remove contact lenses, if present and easy to do. Continue rinsing. Get emergency medical help immediately.',
                 'Ingestion: Rinse mouth. Do NOT induce vomiting. Get emergency medical help immediately.'],
        (4, 2): 'Causes severe burns of skin, eyes and mouth; corrosive damage to the eyes may be permanent.',
        (4, 3): 'Immediate medical attention is required. Treat burns symptomatically.',
        (11, 1): 'Skin corrosion: Category 1B (synthetic fixture). Causes burns.',
    },
    'synth_asp_tox_vomiting': {
        'tag': 'ASP',
        (2, 1): 'Asp. Tox. 1, H304.',
        (2, 2): 'Signal word: Danger. Hazard statements: H304 May be fatal if swallowed and enters airways. '
                'Precautionary statements: P301+P310 IF SWALLOWED: Immediately call a POISON CENTER/doctor. P331 Do NOT induce vomiting. P405 Store locked up.',
        (3, 1): 'Synthetic hydrocarbon component (no CAS): 100 %. Asp. Tox. 1, H304.',
        (4, 1): ['General advice: Show this safety data sheet to the doctor. First-aiders: wear protective gloves.',
                 'Inhalation: Remove to fresh air.',
                 'Skin contact: Remove contaminated clothing. Wash skin with water.',
                 'Eye contact: Rinse with water.',
                 'Ingestion: Induce vomiting. Immediately call a POISON CENTER or doctor.'],
        (4, 2): 'Aspiration into the lungs may cause chemical pneumonitis, which can be fatal.',
        (4, 3): 'Immediate medical attention is required.',
        (11, 1): 'Aspiration hazard: Category 1 (synthetic fixture).',
    },
    'synth_oral4_vomiting': {
        'tag': 'OR4',
        (2, 1): 'Acute Tox. 4 (oral), H302.',
        (2, 2): 'Signal word: Warning. Hazard statements: H302 Harmful if swallowed. '
                'Precautionary statements: P264 Wash hands thoroughly after handling. P270 Do not eat, drink or smoke when using this product. '
                'P301+P312 IF SWALLOWED: Call a POISON CENTER/doctor if you feel unwell. P330 Rinse mouth.',
        (3, 1): 'Synthetic harmful component (no CAS): 100 %. Acute Tox. 4, H302.',
        (4, 1): ['General advice: If you feel unwell, get medical advice. First-aiders: wear protective gloves.',
                 'Inhalation: Remove to fresh air.',
                 'Skin contact: Remove contaminated clothing. Wash skin with water.',
                 'Eye contact: Rinse with water.',
                 'Ingestion: Rinse mouth. Induce vomiting. Call a POISON CENTER or doctor if you feel unwell.'],
        (4, 2): 'Harmful if swallowed: nausea, abdominal pain.',
        (4, 3): 'Treat symptomatically.',
        (11, 1): 'Acute toxicity (oral): Category 4 (synthetic fixture).',
    },
}


def build(name, spec):
    lines = [BANNER, '', f'# SAFETY DATA SHEET — {name}', '', 'Revision date: 27.11.2026 (synthetic)', '']
    for n, title in enumerate(TITLES, 1):
        lines += [f'SECTION {n}: {title}', '']
        for k, sub in enumerate(SUBS[n], 1):
            body = spec.get((n, k), COMMON.get((n, k), 'Not applicable: synthetic fixture.'))
            if isinstance(body, str):
                body = body.replace('{tag}', spec['tag'])
            lines.append(f'{n}.{k}. {sub}')
            lines.append('')
            for para in (body if isinstance(body, list) else [body]):
                lines += [para, '']
        lines += [BANNER, '']
    md = os.path.join(HERE, name + '.md')
    open(md, 'w', encoding='utf-8').write('\n'.join(lines))
    subprocess.run(['pandoc', md, '-o', os.path.join(HERE, name + '.docx')], check=True)
    return md


if __name__ == '__main__':
    for name, spec in CASES.items():
        print('wrote', build(name, spec))
