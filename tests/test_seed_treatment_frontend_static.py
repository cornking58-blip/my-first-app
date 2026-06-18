import re
import unittest
from pathlib import Path

COMPARE_SOURCE = Path(__file__).resolve().parents[1] / "frontend" / "app" / "seed-treatment-compare.tsx"
COMPARE_TEXT = COMPARE_SOURCE.read_text()


class SeedTreatmentCompareFrontendStaticTest(unittest.TestCase):
    def test_compare_screen_does_not_use_partial_substance_name_matching(self):
        names_match_body = re.search(r"const namesMatch = .*?=> \{(?P<body>.*?)\n  \};", COMPARE_TEXT, re.S)
        self.assertIsNotNone(names_match_body)
        body = names_match_body.group("body")

        self.assertNotIn("includes", body)
        self.assertIn("leftKey === rightKey", body)

    def test_null_concentration_renders_dash_not_zero(self):
        self.assertIn("if (value === null || value === undefined || !Number.isFinite(value)) return '—';", COMPARE_TEXT)
        self.assertIn("formatConcentration(substance.concentration, substance.unit)", COMPARE_TEXT)

    def test_cost_metric_hidden_when_estimated_cost_per_gram_is_null(self):
        self.assertIn("cost.estimated_cost_per_gram !== null", COMPARE_TEXT)
        self.assertIn("cost.estimated_cost_per_gram !== undefined", COMPARE_TEXT)

    def test_visible_cost_text_stays_inside_text_components(self):
        for phrase in ["Затраты на 1 г ДВ", "Концентрация:", "ДВ на гектар"]:
            self.assertRegex(COMPARE_TEXT, rf"<Text[^>]*>[^<]*{re.escape(phrase)}")


if __name__ == "__main__":
    unittest.main()
