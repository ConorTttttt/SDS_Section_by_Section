"""Unit tests for tools/refgate.py (concentration and physical-form gating)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import refgate  # noqa: E402


def sds(s3, s9='Physical state: liquid', s1='Product name: X'):
    return {'sections': {'1': {'text': s1}, '3': {'text': s3}, '9': {'text': s9}}, 'codes_by_section': {}}


ROW_BEFORE = """3.2 Mixtures
 Product/ingredient name     Identifiers        %             Classification
 1,3-dioxolane               REACH #:           ≥50 - ≤75     Flam. Liq. 2, H225
                             EC: 211-463-5
                             CAS: 646-06-0
                             Index: 605-017-00-2
 dimethoxymethane            EC: 203-714-2      ≥10 - ≤25     Flam. Liq. 2, H225
                             CAS: 109-87-5
 methanol                    REACH #:           ≤3            Flam. Liq. 2, H225
                             CAS: 67-56-1
 2-Dimethylaminoethanol      REACH #:           ≤0,3          Acute Tox. 4, H302
                             CAS: 108-01-0
"""
ROW_AFTER = """3.2. Mixtures
Name   Product identifier   %   Classification
Distillates (petroleum), hydrotreated heavy paraffinic   CAS-No.: 64742-54-7   ≥ 45 – < 55   Not classified
naphthalene   CAS-No.: 91-20-3   < 0.1   Carc. 2, H351   EC-No.: 202-049-5
"""


class Concentrations(unittest.TestCase):
    def test_concentration_before_cas(self):
        c = refgate.concentrations(sds(ROW_BEFORE))
        self.assertEqual(c['646-06-0']['top'], 75)
        self.assertEqual(c['109-87-5']['top'], 25)
        self.assertEqual(c['67-56-1']['top'], 3)
        self.assertEqual(c['108-01-0']['top'], 0.3)
        self.assertEqual(c['646-06-0']['name'], '1,3-dioxolane')

    def test_concentration_after_cas_and_strict_bounds(self):
        g = refgate.Gate(sds(ROW_AFTER), set(), 'mixture')
        self.assertEqual(g.band('64742-54-7'), 'major')    # < 55
        self.assertEqual(g.band('91-20-3'), 'trace')       # < 0.1

    def test_strict_upper_bound_just_below_threshold(self):
        g = refgate.Gate(sds('Oil  CAS-No.: 64741-88-4  ≥ 0.3 – < 1  Not classified\n'), set(), 'mixture')
        self.assertEqual(g.band('64741-88-4'), 'trace')

    def test_ten_percent_is_minor(self):
        g = refgate.Gate(sds('1-methoxy-2-propanol  REACH #: ≤10  CAS: 107-98-2\n'), set(), 'mixture')
        self.assertEqual(g.band('107-98-2'), 'minor')
        g = refgate.Gate(sds('Solvent  CAS: 64-17-5  10-20 %\n'), set(), 'mixture')
        self.assertEqual(g.band('64-17-5'), 'major')

    def test_unclassified_mixture_capped_at_warning(self):
        g = refgate.Gate(sds(ROW_BEFORE), set(), 'mixture')
        self.assertTrue(g.unclassified)
        self.assertEqual(g.allow('646-06-0', 'reactivity', 'fail'), 'warning')
        self.assertFalse(refgate.Gate(sds(ROW_BEFORE), set(), 'substance').unclassified)

    def test_substance_and_unknown(self):
        self.assertEqual(refgate.Gate(sds('Acetone 67-64-1'), set(), 'substance').band('67-64-1'), 'major')
        self.assertEqual(refgate.Gate(sds('Acetone 67-64-1'), set(), 'mixture').band('67-64-1'),
                         refgate.CFG['unknown_concentration_band'])


class Gating(unittest.TestCase):
    def setUp(self):
        self.g = refgate.Gate(sds(ROW_BEFORE), {'H225', 'H318'}, 'mixture')

    def test_major_unchanged(self):
        self.assertEqual(self.g.allow('646-06-0', 'reactivity', 'fail'), 'fail')

    def test_minor_general_reactivity_is_info(self):
        self.assertEqual(self.g.allow('67-56-1', 'reactivity', 'fail'), 'info')

    def test_minor_fitting_kind_capped_at_warning(self):
        self.assertEqual(self.g.allow('67-56-1', 'flammability', 'fail'), 'warning')     # mixture is H225

    def test_minor_unfitting_kind_dropped(self):
        self.assertIsNone(self.g.allow('67-56-1', 'inhalation', 'warning'))               # mixture has no inhalation class
        self.assertTrue(any('does not fit' in n for n in self.g.notes))

    def test_trace_dropped_unless_high_hazard(self):
        self.assertIsNone(self.g.allow('108-01-0', 'reactivity', 'fail'))
        self.assertIsNone(self.g.allow('108-01-0', {'toxic_gas'}, 'fail'))       # toxic gas: kept for minor, not for trace
        self.assertEqual(self.g.allow('67-56-1', {'toxic_gas'}, 'fail'), 'warning')
        self.assertEqual(self.g.allow('108-01-0', {'high_hazard', 'reactivity'}, 'fail'), 'warning')

    def test_kinds_of(self):
        self.assertIn('high_hazard', refgate.kinds_of('Test sentence: this ether may form explosive peroxides when kept in air.'))
        self.assertIn('toxic_gas', refgate.kinds_of('Reacts with acids. This produces toxic gas (chlorine).'))
        self.assertNotIn('high_hazard', refgate.kinds_of('Reacts with acids. This produces toxic gas (chlorine).'))
        self.assertEqual(refgate.kinds_of('Reacts with strong oxidants.'), {'reactivity'})
        self.assertEqual(refgate.kinds_of('Incompatible with: Strong oxidizers, acetaldehyde, chlorine, acids'), {'reactivity'})
        self.assertEqual(refgate.kinds_of('Test sentence: keep apart from isocyanates, peroxides and epoxides.'), {'reactivity'})
        self.assertIn('high_hazard', refgate.kinds_of('Test sentence: autoxidation in air can give explosive peroxides.'))


class PeroxideFormers(unittest.TestCase):
    def test_list_has_a_source_before_any_entry(self):
        spf = refgate.CFG['strong_peroxide_formers']
        self.assertTrue(not spf['cas'] or spf['source'], 'strong_peroxide_formers needs a cited source before CAS numbers are added')


class Form(unittest.TestCase):
    def test_gas_record_not_applied_to_liquid(self):
        g = refgate.Gate(sds('Hydrochloric acid 7647-01-0 1.6%'), set(), 'mixture')
        self.assertEqual(g.form, 'liquid')
        self.assertFalse(g.card_applies('7647-01-0', 'ICSC 0163', 'Test record: the gas is heavier than air; refrigerated liquid.'))
        self.assertTrue(g.card_applies('7647-01-0', 'CAMEO 3598', 'Test record: an aqueous solution of the acid.'))

    def test_gas_record_applies_to_aerosol(self):
        g = refgate.Gate(sds('butane 106-97-8 10-20 %', s1='Type of product : Aerosol.'), {'H222'}, 'mixture')
        self.assertEqual(g.form, 'aerosol')
        self.assertTrue(g.card_applies('106-97-8', 'ICSC 0232', 'Test record: the gas is heavier than air.'))

    def test_dust_statement_only_for_solids(self):
        g = refgate.Gate(sds('Carbon black 1333-86-4 0.9-5.0%'), set(), 'mixture')
        self.assertFalse(g.statement_applies('1333-86-4', 'ICSC 0471', 'Test sentence: a dust explosion is possible if finely dispersed in air.'))
        g2 = refgate.Gate(sds('Carbon black 1333-86-4 100 %', s9='Physical state: solid powder'), set(), 'mixture')
        self.assertTrue(g2.statement_applies('1333-86-4', 'ICSC 0471', 'Test sentence: a dust explosion is possible if finely dispersed in air.'))


if __name__ == '__main__':
    unittest.main()
