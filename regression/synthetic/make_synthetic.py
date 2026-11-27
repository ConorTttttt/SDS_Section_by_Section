"""Generate the synthetic test SDSs used by the regression set.

These are SYNTHETIC TEST FIXTURES, not real products or real safety data sheets. Each one is complete enough
to run the checkers and is built to trigger one specific rule:

  synth_rev10_codes            GHS Rev.10 codes (P316/P317) on an EU SDS      -> 2-L2 warning, P316 matched as P310
  synth_asp_tox_vomiting       "induce vomiting" with Asp. Tox. 1 (H304, P331) -> 4-B1 fail (also covers 4-C1)
  synth_oral4_vomiting         "induce vomiting" with Acute Tox. 4 oral only   -> 4-B1 warning
  synth_flam_gas_wrong         flammable gas, no leaking-gas caveat / ignition control -> 5-B3, 6-B3, 7-B1 fail
  synth_flam_gas_correct       the same flammable gas done right                     -> no fails (false-fail check)
  synth_explosive_wrong        explosive 1.1, no evacuation advice, no P401 storage  -> 5-B2, 7-B8 fail
  synth_oxidiser_cat1_wrong    oxidising solid cat. 1, no combustibles separation    -> 5-B2, 7-B2 fail
  synth_org_peroxide_ct_wrong  organic peroxide, P411 0 °C on label, none in 7.2     -> 7-B3 fail
  synth_unstable_gas_s10_wrong chemically unstable gas, 10.2 'stable'              -> 10-B4 fail
  synth_explosive_s10_wrong    explosive, 10.4 without shock/friction/static       -> 10-B5 fail
  synth_org_peroxide_s10_wrong organic peroxide, 10.2-10.4 incomplete              -> 10-B7 fail
  synth_peroxide_former_wrong  EUH019/EUH044/EUH031 not reflected in Section 10    -> 10-B13, 10-B14, 10-B15 fail
  synth_monomer_s10_wrong      inhibited monomer, no stabiliser/polymerisation     -> 10-A10, 10-A11 fail

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


GOOD4 = {
    (4, 1): ['General advice: If you feel unwell, get medical advice. First-aiders: wear protective gloves and eye protection.',
             'Inhalation: Remove to fresh air and keep comfortable for breathing.',
             'Skin contact: Take off contaminated clothing and shoes. Wash skin with plenty of water.',
             'Eye contact: Rinse cautiously with water for several minutes. Remove contact lenses, if present and easy to do.',
             'Ingestion: Rinse mouth. Get medical advice if you feel unwell.'],
    (4, 2): 'No specific symptoms known beyond irritation (synthetic fixture).',
    (4, 3): 'Treat symptomatically.',
}
GOOD7_HYGIENE = ('Do not eat, drink or smoke in work areas; wash hands after use; remove contaminated clothing and protective equipment '
                 'before entering eating areas. Avoid release to the environment; keep away from drains. Avoid contact with incompatible materials (see Section 10.5).')
FLAM_GAS = {
    (2, 1): 'Flam. Gas 1A, H220. Press. Gas (Comp.), H280.',
    (2, 2): 'Signal word: Danger. Hazard statements: H220 Extremely flammable gas. H280 Contains gas under pressure; may explode if heated. '
            'Precautionary statements: P210 Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking. '
            'P377 Leaking gas fire: Do not extinguish, unless leak can be stopped safely. P381 In case of leakage, eliminate all ignition sources. '
            'P410+P403 Protect from sunlight. Store in a well-ventilated place.',
    (3, 1): 'Synthetic flammable gas (no CAS): 100 %. Flam. Gas 1A, H220; Press. Gas, H280.',
    (9, 1): 'Physical state: gas. Colour: colourless. Lower explosion limit 2 vol% (synthetic).',
    (10, 1): 'Extremely flammable gas; forms explosive mixtures with air (synthetic fixture).',
    (10, 3): 'Forms explosive mixtures with air. Cylinders may burst or explode if heated.',
    (10, 4): 'Heat, hot surfaces, sparks, open flames, static discharge and other ignition sources; direct sunlight; temperatures above 50 °C.',
    (10, 5): 'Oxidising agents.',
    (10, 6): 'None known under normal storage; on combustion, carbon oxides (see Section 5).',
    (14, 1): 'Transport hazard class 2.1 (synthetic fixture).',
}
CASES.update({
    'synth_flam_gas_wrong': {**GOOD4, **FLAM_GAS, 'tag': 'FGW',
        (5, 1): 'Suitable extinguishing media: water spray, dry chemical. Unsuitable extinguishing media: water jet.',
        (5, 2): 'Extremely flammable gas. Containers may burst if heated. Combustion produces carbon monoxide and carbon dioxide.',
        (5, 3): 'Wear self-contained breathing apparatus. Cool containers with water spray.',
        (6, 1): 'Evacuate the area. Wear protective equipment.',
        (6, 2): 'Prevent entry to sewers and confined spaces.',
        (6, 3): 'Stop the release; ventilate the area until the gas has dispersed.',
        (6, 4): 'See Sections 8 and 13.',
        (7, 1): 'Avoid contact with eyes. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in a dry place.',
    },
    'synth_flam_gas_correct': {**GOOD4, **FLAM_GAS, 'tag': 'FGC',
        (5, 1): 'Suitable extinguishing media: dry chemical, carbon dioxide; water spray to cool containers. Unsuitable extinguishing media: water jet.',
        (5, 2): 'Extremely flammable gas. Containers may burst when heated. Combustion produces carbon monoxide and carbon dioxide.',
        (5, 3): 'Leaking gas fire: Do not extinguish, unless leak can be stopped safely. Eliminate all ignition sources. '
                'Cool containers with water spray from a protected position. Wear self-contained breathing apparatus.',
        (6, 1): '6.1.1 For non-emergency personnel: evacuate the danger area; eliminate all ignition sources; ventilate. '
                '6.1.2 For emergency responders: chemically protective clothing of a suitable material (e.g. butyl rubber gloves) and breathing apparatus. '
                'Small leaks: ventilate and let the gas disperse. Large leaks: evacuate and call the emergency services.',
        (6, 2): 'Prevent gas from entering drains, sewers or confined spaces.',
        (6, 3): 'Contain: stop the leak if safe to do so. Clean up: ventilate and allow the gas to disperse; collect leaking cylinders for return to the supplier. '
                'Use non-sparking tools and explosion-proof equipment.',
        (6, 4): 'See Sections 8 and 13.',
        (7, 1): 'Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking. Ground and bond container and receiving equipment; '
                'take action to prevent static discharges; use explosion-proof electrical equipment and non-sparking tools. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in a well-ventilated place; keep cool. Protect from sunlight. Store cylinders upright and secured, away from oxidising agents (see Section 10.5).',
        (7, 3): 'Industrial use as a fuel gas (synthetic fixture).',
    },
    'synth_explosive_wrong': {**GOOD4, 'tag': 'EXW',
        (2, 1): 'Expl. 1.1, H201.',
        (2, 2): 'Signal word: Danger. Hazard statements: H201 Explosive; mass explosion hazard. Precautionary statements: P210 Keep away from heat, hot surfaces, '
                'sparks, open flames and other ignition sources. No smoking. P234 Keep only in original packaging. P250 Do not subject to grinding/shock/friction. '
                'P370+P372+P380+P373 In case of fire: Explosion risk. Evacuate area. DO NOT fight fire when fire reaches explosives. P401 Store in accordance with local regulations.',
        (3, 1): 'Synthetic explosive (no CAS): 100 %. Expl. 1.1, H201.',
        (5, 1): 'Suitable extinguishing media: water spray. Unsuitable extinguishing media: none known.',
        (5, 2): 'Mass explosion hazard. Combustion produces carbon monoxide and nitrogen oxides.',
        (5, 3): 'Wear self-contained breathing apparatus. Cool containers with water.',
        (6, 1): 'Remove all ignition sources; avoid shock and friction. Evacuate the area. Emergency responders: wear protective clothing of a suitable material (cotton, antistatic).',
        (6, 2): 'Keep away from drains.', (6, 3): 'Contain the spill; collect carefully with non-sparking tools into the original packaging.', (6, 4): 'See Sections 8 and 13.',
        (7, 1): 'Use non-sparking tools. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in a cool, dry place.',
        (9, 1): 'Physical state: solid (powder). Colour: white.',
        (10, 1): 'Explosive; mass explosion hazard (synthetic fixture).',
        (10, 3): 'May explode on heating, shock or friction.',
        (10, 4): 'Heat, sparks, flames, shock, friction, grinding and static discharge.',
        (10, 5): 'Acids, metals, oxidising agents.',
        (10, 6): 'On decomposition: nitrogen oxides and carbon oxides.',
        (14, 1): 'UN classification 1.1D (synthetic fixture).',
    },
    'synth_oxidiser_cat1_wrong': {**GOOD4, 'tag': 'OXW',
        (2, 1): 'Ox. Sol. 1, H271.',
        (2, 2): 'Signal word: Danger. Hazard statements: H271 May cause fire or explosion; strong oxidiser. Precautionary statements: P210 Keep away from heat. '
                'P220 Keep away from clothing and other combustible materials. P283 Wear fire resistant or flame retardant clothing. '
                'P306+P360 IF ON CLOTHING: Rinse immediately contaminated clothing and skin with plenty of water before removing clothes. '
                'P371+P380+P375 In case of major fire and large quantities: Evacuate area. Fight fire remotely due to the risk of explosion. '
                'P370+P378 In case of fire: Use water to extinguish. P420 Store separately.',
        (3, 1): 'Synthetic oxidising solid (no CAS): 100 %. Ox. Sol. 1, H271.',
        (4, 1): ['General advice: If you feel unwell, get medical advice. First-aiders: wear protective gloves and eye protection.',
                 'Inhalation: Remove to fresh air.',
                 'Skin contact: Rinse immediately contaminated clothing and skin with plenty of water before removing clothes.',
                 'Eye contact: Rinse cautiously with water for several minutes. Remove contact lenses, if present and easy to do.',
                 'Ingestion: Rinse mouth. Get medical advice if you feel unwell.'],
        (5, 1): 'Suitable extinguishing media: flooding quantities of water. Unsuitable extinguishing media: dry chemical and carbon dioxide (ineffective).',
        (5, 2): 'Strong oxidiser: intensifies fire; may cause fire or explosion in contact with combustible materials. Releases oxygen when heated.',
        (5, 3): 'Wear self-contained breathing apparatus and full protective clothing.',
        (6, 1): 'Keep combustible materials away from the spill. Emergency responders: wear protective clothing of a suitable material (no combustible fabrics).',
        (6, 2): 'Keep away from drains.', (6, 3): 'Sweep up into a clean, dry, non-combustible container. Do not use sawdust or other combustible absorbents.',
        (6, 4): 'See Sections 8 and 13.',
        (7, 1): 'Avoid dust formation. Wear protective equipment. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in a cool, dry place.',
        (9, 1): 'Physical state: solid (crystals). Colour: white.',
        (10, 1): 'Strong oxidiser: may cause fire or explosion with combustible materials (synthetic fixture).',
        (10, 3): 'Violent reaction with combustible and reducing materials; may intensify fire.',
        (10, 4): 'Heat; contamination with combustible materials.',
        (10, 5): 'Combustible materials, reducing agents, organic materials.',
        (10, 6): 'On heating: oxygen (supports combustion).',
        (14, 1): 'Transport hazard class 5.1 (synthetic fixture).',
    },
    'synth_org_peroxide_ct_wrong': {**GOOD4, 'tag': 'OPW',
        (2, 1): 'Org. Perox. D, H242.',
        (2, 2): 'Signal word: Danger. Hazard statements: H242 Heating may cause a fire. Precautionary statements: P210 Keep away from heat, hot surfaces, sparks, '
                'open flames and other ignition sources. No smoking. P234 Keep only in original packaging. '
                'P370+P378 In case of fire: Use water spray to extinguish. P410 Protect from sunlight. P411 Store at temperatures not exceeding 0 °C. P420 Store separately.',
        (3, 1): 'Synthetic organic peroxide (no CAS): 100 %. Org. Perox. D, H242.',
        (5, 1): 'Suitable extinguishing media: water spray, foam. Unsuitable extinguishing media: water jet.',
        (5, 2): 'Heating may cause a fire; self-accelerating decomposition above the SADT. Combustion produces carbon monoxide and carbon dioxide.',
        (5, 3): 'Wear self-contained breathing apparatus. Cool containers with water spray from a safe distance.',
        (6, 1): 'Remove all ignition sources. Emergency responders: wear protective clothing of a suitable material (e.g. neoprene).',
        (6, 2): 'Keep away from drains.', (6, 3): 'Contain with inert, non-combustible absorbent (vermiculite); collect into a clean container. Do not use sawdust.',
        (6, 4): 'See Sections 8 and 13.',
        (7, 1): 'Keep away from heat, sparks and open flames. ' + GOOD7_HYGIENE,
        (7, 2): 'Keep only in original packaging. Store separately. Protect from sunlight.',
        (9, 1): 'Physical state: liquid. Colour: colourless. Decomposition temperature (SADT): 10 °C (synthetic value, 50 kg package).',
        (10, 1): 'Organic peroxide: self-accelerating decomposition above the SADT (synthetic fixture).',
        (10, 2): 'Stable only when stored at or below the control temperature of 0 °C.',
        (10, 3): 'Self-accelerating decomposition with release of heat and flammable vapours if the temperature rises above the SADT.',
        (10, 4): 'Temperatures above 0 °C (control temperature); heat, sources of ignition, contamination.',
        (10, 5): 'Amines, accelerators, reducing agents, acids, bases, metal compounds.',
        (10, 6): 'On decomposition: carbon dioxide and flammable organic vapours.',
        (14, 1): 'Transport hazard class 5.2; control temperature 0 °C; emergency temperature 10 °C (synthetic fixture).',
    },
})

S10GOOD = {(5, 1): 'Suitable extinguishing media: water spray, dry chemical, carbon dioxide. Unsuitable extinguishing media: water jet.',
           (5, 2): 'Containers may burst when heated. Combustion produces carbon monoxide and carbon dioxide.', (5, 3): 'Wear self-contained breathing apparatus.',
           (6, 1): 'Remove all ignition sources; avoid raising dust. Emergency responders: chemically protective clothing of a suitable material (e.g. butyl rubber). '
                   'Small spills: soak up. Large spills: dike and contain.',
           (6, 2): 'Keep away from drains.', (6, 3): 'Contain and soak up with inert absorbent; collect into closed containers. Use non-sparking tools and explosion-proof equipment.',
           (6, 4): 'See Sections 8 and 13.'}
CASES.update({
    'synth_unstable_gas_s10_wrong': {**GOOD4, **S10GOOD, 'tag': 'UGW',
        (2, 1): 'Flam. Gas 1A, H220; Chem. Unst. Gas A, H230; Press. Gas, H280.',
        (2, 2): 'Signal word: Danger. H220 Extremely flammable gas. H230 May react explosively even in the absence of air. H280 Contains gas under pressure; may explode if heated. '
                'P202 Do not handle until all safety precautions have been read and understood. P210 Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking. '
                'P377 Leaking gas fire: Do not extinguish, unless leak can be stopped safely. P381 In case of leakage, eliminate all ignition sources. P410+P403 Protect from sunlight. Store in a well-ventilated place.',
        (3, 1): 'Synthetic unstable gas (no CAS): 100 %.',
        (5, 3): 'Leaking gas fire: Do not extinguish, unless leak can be stopped safely. Wear self-contained breathing apparatus.',
        (7, 1): 'Keep away from heat, sparks, open flames and other ignition sources. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in a well-ventilated place; keep cool; protect from sunlight; away from oxidising agents (see Section 10.5).',
        (9, 1): 'Physical state: gas.',
        (10, 1): 'Extremely flammable gas (synthetic fixture).', (10, 2): 'Stable under normal conditions.', (10, 3): 'Forms explosive mixtures with air.',
        (10, 4): 'Heat, sparks, open flames, static discharge and other ignition sources; direct sunlight.', (10, 5): 'Oxidising agents.',
        (10, 6): 'None known; on combustion carbon oxides (see Section 5).',
    },
    'synth_explosive_s10_wrong': {**GOOD4, **S10GOOD, 'tag': 'ESW',
        (2, 1): 'Expl. 1.1, H201.',
        (2, 2): 'Signal word: Danger. H201 Explosive; mass explosion hazard. P210 Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking. '
                'P240 Ground and bond container and receiving equipment. P250 Do not subject to grinding/shock/friction. P234 Keep only in original packaging. '
                'P370+P372+P380+P373 In case of fire: Explosion risk. Evacuate area. DO NOT fight fire when fire reaches explosives. P401 Store in accordance with local regulations.',
        (3, 1): 'Synthetic explosive (no CAS): 100 %.',
        (5, 3): 'Explosion risk: evacuate the area. Do not fight fire when fire reaches explosives. Wear self-contained breathing apparatus.',
        (7, 1): 'Do not subject to grinding, shock or friction. Ground and bond equipment. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in accordance with the applicable explosives regulations, in the original packaging, separated from other materials (see Section 10.5).',
        (9, 1): 'Physical state: solid (powder).',
        (10, 1): 'Explosive; mass explosion hazard (synthetic fixture).', (10, 2): 'Stable only under the recommended storage conditions.',
        (10, 3): 'May explode on heating.', (10, 4): 'Heat and open flames.', (10, 5): 'Acids, metals, oxidising agents.', (10, 6): 'On decomposition: nitrogen oxides, carbon oxides.',
        (14, 1): 'UN classification 1.1D (synthetic fixture).',
    },
    'synth_org_peroxide_s10_wrong': {**GOOD4, **S10GOOD, 'tag': 'PSW',
        (2, 1): 'Org. Perox. B, H241.',
        (2, 2): 'Signal word: Danger. H241 Heating may cause a fire or explosion. P210 Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking. '
                'P234 Keep only in original packaging. P410 Protect from sunlight. P411 Store at temperatures not exceeding 5 °C. P420 Store separately.',
        (3, 1): 'Synthetic organic peroxide (no CAS): 100 %.',
        (7, 1): 'Keep away from heat and ignition sources. ' + GOOD7_HYGIENE,
        (7, 2): 'Store at temperatures not exceeding 5 °C in the original packaging, separately, protected from sunlight, away from amines and reducing agents (see Section 10.5).',
        (9, 1): 'Physical state: liquid. SADT: 20 °C (UN test H.4, synthetic value).',
        (10, 1): 'Organic peroxide (synthetic fixture).', (10, 2): 'Stable.', (10, 3): 'No data available: synthetic fixture.',
        (10, 4): 'Sources of ignition, contamination and direct sunlight.', (10, 5): 'Amines, reducing agents.', (10, 6): 'On decomposition: carbon dioxide.',
        (14, 1): 'Transport hazard class 5.2; control temperature 5 °C (synthetic fixture).',
    },
    'synth_peroxide_former_wrong': {**GOOD4, **S10GOOD, 'tag': 'PFW',
        (2, 1): 'Flam. Liq. 2, H225. EUH019, EUH044, EUH031.',
        (2, 2): 'Signal word: Danger. H225 Highly flammable liquid and vapour. EUH019 May form explosive peroxides. EUH044 Risk of explosion if heated under confinement. '
                'EUH031 Contact with acids liberates toxic gas. P210 Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking. '
                'P233 Keep container tightly closed. P240 Ground and bond container and receiving equipment. P243 Take action to prevent static discharges.',
        (3, 1): 'Synthetic ether (no CAS): 100 %.',
        (7, 1): 'Keep away from ignition sources; ground and bond containers; take action to prevent static discharges; use explosion-proof equipment. ' + GOOD7_HYGIENE,
        (7, 2): 'Store in a cool, well-ventilated place away from acids (see Section 10.5). Record the date of opening; test for peroxides before use.',
        (9, 1): 'Physical state: liquid. Flash point -20 °C.',
        (10, 1): 'Highly flammable liquid (synthetic fixture).', (10, 2): 'Stable under normal conditions.', (10, 3): 'Vapours may form explosive mixtures with air.',
        (10, 4): 'Heat, sparks, open flames, static discharge.', (10, 5): 'Oxidising agents.', (10, 6): 'None known; on combustion carbon oxides (see Section 5).',
    },
    'synth_monomer_s10_wrong': {**GOOD4, **S10GOOD, 'tag': 'MOW',
        (2, 1): 'Flam. Liq. 3, H226.',
        (2, 2): 'Signal word: Warning. H226 Flammable liquid and vapour. P210 Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking.',
        (3, 1): 'Synthetic monomer (no CAS): > 99 %, stabilised with 50 ppm inhibitor.',
        (7, 1): 'Keep away from heat and ignition sources. ' + GOOD7_HYGIENE,
        (7, 2): 'Store cool, away from oxidising agents (see Section 10.5). The inhibitor prevents polymerisation; check the inhibitor level every 3 months.',
        (9, 1): 'Physical state: liquid. Flash point 30 °C.',
        (10, 1): 'Flammable liquid (synthetic fixture).', (10, 2): 'Stable under normal conditions.', (10, 3): 'No hazardous reactions known.',
        (10, 4): 'Heat, sparks, open flames.', (10, 5): 'Oxidising agents.', (10, 6): 'None known; on combustion carbon oxides (see Section 5).',
    },
})


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
