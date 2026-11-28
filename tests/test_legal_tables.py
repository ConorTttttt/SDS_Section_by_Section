"""Consistency of the bundled CLP tables in data/legal/ (built by tools/legal_tables.py)."""
import glob
import json
import os
import unittest

LEGAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'legal')


def load(prefix):
    return json.load(open(sorted(glob.glob(os.path.join(LEGAL, prefix + '*.json')))[-1], encoding='utf-8'))


def parts(codes):
    return {x.strip('[]') for c in codes for x in c.split('+')}


# Differences inside the consolidated text itself (data/legal/SOURCES.md): class -> codes either source may hold
EITHER = {'explosives': {'P501', 'P503'}, 'self_heating': {'P410'}, 'lactation': {'P202'}}
CONSUMER_ONLY_P201 = {'mutagenicity', 'carcinogenicity', 'reproductive_toxicity', 'lactation'}


class LegalTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iv = load('clp_annex_iv_eu_')
        cls.lab = load('clp_annex_i_label_p_eu_')['entries']
        cls.cat = load('clp_category_h_eu_')['entries']
        cls.codes = load('clp_annex_vi_codes_eu_')['entries']

    def test_source_recorded(self):
        for d in (self.iv, load('clp_annex_i_label_p_eu_'), load('clp_category_h_eu_'), load('clp_annex_vi_codes_eu_')):
            self.assertTrue(d['celex'].startswith('02008R1272') and d['source_sha256'] and 'Changes' in d['reuse'])

    def test_every_statement_has_wording_and_rows(self):
        self.assertEqual(len(self.iv['statements']), 129)
        for s in self.iv['statements']:
            self.assertTrue(s['text'], s['code'])
            self.assertTrue(s['rows'], s['code'])
        self.assertEqual(self.iv['unmapped_class_cells'], [])

    def test_every_class_row_maps_to_hazard_statements(self):
        have = {(e['class_key'], e['category']) for e in self.cat}
        rows = {(r['class_key'], c) for s in self.iv['statements'] for r in s['rows'] if r['class_key'] for c in r['categories']}
        # skin irritation Category 3 is listed in the P313 row but does not exist in EU CLP
        self.assertEqual(rows - have, {('skin_irritation', '3')})

    def test_annex_i_and_annex_iv_agree_except_documented(self):
        by = {}
        for s in self.iv['statements']:
            for r in s['rows']:
                for c in r['categories']:
                    by.setdefault((r['class_key'], c), set()).add(s['code'])
        compared = 0
        for e in self.lab:
            k = (e['class_key'], e['category'])
            if k not in by:
                continue
            a, b = parts(e['p']), parts(by[k])
            diff = (a ^ b) - EITHER.get(k[0], set())
            self.assertEqual(diff, set(), k)
            compared += 1
        self.assertGreater(compared, 70)

    def test_p201_cmr_is_consumer_only_in_annex_iv(self):
        p201 = next(s for s in self.iv['statements'] if s['code'] == 'P201')
        for r in p201['rows']:
            if r['class_key'] in CONSUMER_ONLY_P201:
                self.assertIn('Consumer products', r['conditions'])

    def test_annex_vi_codes_cover_annex_iv_classes(self):
        coded = {e['class_key'] for e in self.codes} | {'acute_oral', 'acute_dermal', 'acute_inhalation', 'stot_se_3_resp', 'stot_se_3_narc'}
        used = {r['class_key'] for s in self.iv['statements'] for r in s['rows'] if r['class_key']}
        self.assertEqual(used - coded, set())


if __name__ == '__main__':
    unittest.main()
