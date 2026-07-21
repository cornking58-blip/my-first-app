import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_TEXT = (ROOT / "frontend" / "app" / "_layout.tsx").read_text(encoding="utf-8")
SANITIZER_TEXT = (ROOT / "frontend" / "src" / "seedTreatmentCompareResponseSanitizer.ts").read_text(encoding="utf-8")


class SeedTreatmentCompareResponseSanitizerStaticTest(unittest.TestCase):
    def test_root_layout_installs_sanitizer(self):
        self.assertIn("import '../src/seedTreatmentCompareResponseSanitizer';", LAYOUT_TEXT)

    def test_sanitizer_is_scoped_to_seed_treatment_compare_endpoint(self):
        self.assertIn("/api/seed-treatments/compare-advanced", SANITIZER_TEXT)

    def test_structured_substances_replace_visible_raw_composition(self):
        self.assertIn("buildCompositionFromSubstances(side.substances)", SANITIZER_TEXT)
        self.assertIn("active_substances_raw: `(${composition})`", SANITIZER_TEXT)
        self.assertNotIn("source_active_substances_raw", SANITIZER_TEXT)
        self.assertNotIn("raw_product_name", SANITIZER_TEXT)
        self.assertNotIn("product_key", SANITIZER_TEXT)


if __name__ == "__main__":
    unittest.main()
