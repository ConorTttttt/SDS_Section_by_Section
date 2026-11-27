"""Unit tests for tools/textinterp.py. Run: python3 -I -m unittest discover -s tests -t ."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import textinterp as ti  # noqa: E402


class Negation(unittest.TestCase):
    def test_negated_mentions_are_not_affirmed(self):
        for text in ('This product does not contains nanomaterials.', 'Contains no nanomaterials.',
                     'Free of nanomaterials', 'Not a nanoform.', 'The mixture does not contain any nanoforms'):
            self.assertFalse(ti.affirmed(text, r'nano'), text)

    def test_plain_mentions_are_affirmed(self):
        self.assertTrue(ti.affirmed('Nanoform: titanium dioxide, nanoform 1.', r'nanoform'))
        self.assertTrue(ti.affirmed('Absorb with sawdust or paper.', r'sawdust'))

    def test_negation_does_not_cross_clause_boundary(self):
        self.assertTrue(ti.affirmed('Do not use water jet. Absorb with sawdust.', r'sawdust'))
        self.assertTrue(ti.affirmed('No smoking; flush with plenty of water.', r'flush'))

    def test_vomiting(self):
        self.assertFalse(ti.affirmed('Do NOT induce vomiting.', ti.SYNONYMS['induce_vomit']))
        self.assertFalse(ti.affirmed('Never induce vomiting unless directed by a doctor', ti.SYNONYMS['induce_vomit']))
        self.assertTrue(ti.affirmed('If conscious, induce vomiting.', ti.SYNONYMS['induce_vomit']))
        self.assertTrue(ti.says('Do not induce vomiting. Call a physician immediately.', 'no_vomit'))

    def test_is_reactive(self):
        self.assertFalse(ti.affirmed('The product is not reactive under normal conditions.', r'\breactive\b'))
        self.assertTrue(ti.affirmed('Reactive hazard: yes. The substance is reactive with water.', r'\breactive\b'))


class NoData(unittest.TestCase):
    def test_no_data_phrases(self):
        for v in ('No data available.', 'not available', 'No additional information available',
                  'No further relevant information available.', 'No specific data.', 'Not applicable.', 'N/A', 'n.d.',
                  'Unknown.', '-', ': No specific data.', 'No specific test data related to reactivity available for this product',
                  'Not determined', 'Nothing specified.', 'No data available: synthetic fixture.'):
            self.assertTrue(ti.is_no_data(v), v)

    def test_real_statements_are_not_no_data(self):
        for v in ('Stable under normal conditions.', 'Strong oxidizing agents.', 'None under recommended storage and handling conditions (see section 7).',
                  'No dangerous reactions known under normal conditions of use.', 'Avoid heat, sparks and flames.',
                  'Not available. Reacts violently with water releasing flammable gases.'):
            self.assertFalse(ti.is_no_data(v), v)

    def test_reason(self):
        self.assertFalse(ti.has_reason('No data available.'))
        self.assertTrue(ti.has_reason('No data available because the product is not reactive.'))
        self.assertTrue(ti.has_reason('Not applicable: based on available data the classification criteria are not met.'))

    def test_field_value(self):
        t = 'Short term exposure Potential immediate : Not available. effects Potential delayed effects : Not available. Long term exposure'
        self.assertTrue(ti.is_no_data(ti.field_value(t, r'potential delayed effects')))
        self.assertIsNone(ti.field_value('Eye contact : rinse', r'potential delayed effects'))


class CrossRefs(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(ti.cross_refs('Follow the instructions in the Sections 7 and 8.'), set())  # "in the Sections" is not a cue
        self.assertEqual(ti.cross_refs('See the Section 7, 8 and 13.'), {'7', '8', '13'})
        self.assertEqual(ti.cross_refs('Wear protective clothing as described in Section 8 of this safety data sheet.'), {'8'})
        self.assertEqual(ti.cross_refs('away from incompatible materials (see Section 10)'), {'10'})
        self.assertEqual(ti.cross_refs('None under recommended storage and handling conditions (see section 7).'), {'7'})
        self.assertEqual(ti.cross_refs('For further information refer to section 8: "Exposure controls".'), {'8'})
        self.assertEqual(ti.cross_refs('Store away from oxidising agents (see 10.5).'), set())

    def test_refers_to(self):
        self.assertTrue(ti.refers_to('Personal protection: see Section 8.2.', '8'))
        self.assertTrue(ti.refers_to('Incompatibles: see Section 10.', '10.5'))
        self.assertFalse(ti.refers_to('See Section 13 for disposal.', '8'))


class Synonyms(unittest.TestCase):
    def test_rinse(self):
        for t in ('Flush contaminated skin with plenty of water.', 'Rinse skin with water/shower.', 'Wash with plenty of water.',
                  'Irrigate thoroughly with plenty of water.'):
            self.assertTrue(ti.says(t, 'rinse_water'), t)

    def test_medical(self):
        for t in ('OBTAIN MEDICAL ATTENTION.', 'Get medical advice/attention.', 'Call a physician immediately.', 'Call a POISON CENTER.'):
            self.assertTrue(ti.says(t, 'medical'), t)

    def test_firefighter_ppe(self):
        t = 'Fire fighting Instructions Wear protective suit and self-contained breathing apparatus with full facepiece'
        self.assertTrue(ti.says(t, 'firefighting'))
        self.assertTrue(ti.says(t, 'firefighter_ppe'))

    def test_first_aider(self):
        self.assertTrue(ti.says('Take care of your own safety.', 'firstaider_ppe'))
        self.assertTrue(ti.says('Self protection of the first-aider : First aid workers will be equipped with suitable PPE.', 'firstaider_ppe'))

    def test_eye_symptoms(self):
        self.assertTrue(ti.says('Eye contact : Adverse symptoms may include the following: pain watering redness', 'eye_symptoms'))


class Examples(unittest.TestCase):
    HYG = {'no eating, drinking or smoking': ti.SYNONYMS['no_eat_drink_smoke'], 'wash hands': ti.SYNONYMS['wash_hands'],
           'remove contaminated clothing before eating areas': ti.SYNONYMS['remove_clothing']}

    def test_any_example_meets_the_requirement(self):
        met, missing = ti.covers_examples('Do not eat, drink or smoke when using this product. Always wash hands after handling the product.', self.HYG)
        self.assertTrue(met)
        self.assertEqual(missing, ['remove contaminated clothing before eating areas'])

    def test_generic_wording_meets_the_requirement(self):
        met, _ = ti.covers_examples('Handle in accordance with good industrial hygiene and safety practices.', self.HYG, ti.SYNONYMS['hygiene_generic'])
        self.assertTrue(met)

    def test_nothing(self):
        met, missing = ti.covers_examples('Avoid contact with skin and eyes. Ensure local exhaust ventilation.', self.HYG, ti.SYNONYMS['hygiene_generic'])
        self.assertFalse(met)
        self.assertEqual(len(missing), 3)


if __name__ == '__main__':
    unittest.main()
