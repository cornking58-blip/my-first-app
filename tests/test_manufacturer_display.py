import re
import unittest
from pathlib import Path
from typing import Optional, Sequence


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "server.py"
SERVER_TEXT = SERVER_SOURCE.read_text(encoding="utf-8")
HELPER_SOURCE = "DISPLAY_MANUFACTURER_FALLBACK =" + SERVER_TEXT.split(
    "DISPLAY_MANUFACTURER_FALLBACK =", 1
)[1].split(
    "# ==================== ACTIVE SUBSTANCE PARSER ====================", 1
)[0]

namespace = {"Optional": Optional, "Sequence": Sequence}
exec(HELPER_SOURCE, namespace)

get_display_manufacturer = namespace["get_display_manufacturer"]
manufacturer_response_fields = namespace["manufacturer_response_fields"]
DISPLAY_MANUFACTURER_FALLBACK = namespace["DISPLAY_MANUFACTURER_FALLBACK"]
MANUFACTURER_FIELD_PRIORITY = namespace["MANUFACTURER_FIELD_PRIORITY"]


class ManufacturerDisplayHelperTest(unittest.TestCase):
    def test_record_with_manufacturer_returns_manufacturer(self):
        self.assertEqual(
            get_display_manufacturer({"manufacturer": "Производитель А", "registrant": "Регистрант Б"}),
            "Производитель А",
        )

    def test_record_with_only_registrant_returns_registrant(self):
        self.assertEqual(get_display_manufacturer({"registrant": "Регистрант Б"}), "Регистрант Б")

    def test_record_with_only_producer_returns_producer(self):
        self.assertEqual(get_display_manufacturer({"producer": "Производитель В"}), "Производитель В")

    def test_record_with_only_applicant_returns_applicant(self):
        self.assertEqual(get_display_manufacturer({"applicant": "Заявитель Г"}), "Заявитель Г")

    def test_empty_manufacturer_fields_return_fallback(self):
        self.assertEqual(
            get_display_manufacturer({field: "" for field in MANUFACTURER_FIELD_PRIORITY}),
            DISPLAY_MANUFACTURER_FALLBACK,
        )

    def test_grouped_search_list_response_can_include_display_manufacturer(self):
        grouped_record = {"manufacturer": [None, "Производитель из списка"], "registrant": ["Регистрант"]}
        self.assertEqual(get_display_manufacturer(grouped_record), "Производитель из списка")
        self.assertIn("display_manufacturer", SERVER_TEXT)
        self.assertIn("/herbicides/search", SERVER_TEXT)
        self.assertIn("/fungicides/search", SERVER_TEXT)
        self.assertIn("/insecticides/search", SERVER_TEXT)
        self.assertIn("/seed-treatments/search", SERVER_TEXT)

    def test_product_detail_response_fields_include_display_manufacturer(self):
        fields = manufacturer_response_fields({"registrant": "Детальный регистрант"})
        self.assertEqual(fields["display_manufacturer"], "Детальный регистрант")
        self.assertRegex(SERVER_TEXT, re.compile(r"ProductCard\([\s\S]*manufacturer_response_fields"))

    def test_comparison_response_includes_display_manufacturer_for_both_products(self):
        left = manufacturer_response_fields({"producer": "Левый производитель"})
        right = manufacturer_response_fields({"applicant": "Правый заявитель"})
        self.assertEqual(left["display_manufacturer"], "Левый производитель")
        self.assertEqual(right["display_manufacturer"], "Правый заявитель")
        self.assertGreaterEqual(SERVER_TEXT.count("**manufacturer_response_fields(left_first, left_records)"), 1)
        self.assertGreaterEqual(SERVER_TEXT.count("**manufacturer_response_fields(right_first, right_records)"), 1)

    def test_endpoint_urls_are_unchanged_for_manufacturer_change(self):
        actual_paths = re.findall(r'@api_router\.(?:get|post|put|delete|patch)\("([^"]+)"', SERVER_TEXT)
        self.assertEqual(actual_paths, [
            "/health",
            "/admin/import-excel",
            "/herbicides/search",
            "/herbicides/{product_key:path}",
            "/herbicides/compare",
            "/herbicides/compare-advanced",
            "/admin/import-insecticides",
            "/insecticides/search",
            "/insecticides/{product_key:path}",
            "/insecticides/compare-advanced",
            "/admin/import-fungicides",
            "/fungicides/search",
            "/fungicides/{product_key:path}",
            "/fungicides/compare-advanced",
            "/admin/import-seed-treatments",
            "/seed-treatments/search",
            "/seed-treatments/{product_key:path}",
            "/seed-treatments/compare-advanced",
            "/herbicides/crops",
            "/herbicides/harmful-objects",
            "/insecticides/crops",
            "/insecticides/harmful-objects",
            "/fungicides/crops",
            "/fungicides/harmful-objects",
            "/seed-treatments/crops",
            "/seed-treatments/harmful-objects",
            "/stats",
        ])


if __name__ == "__main__":
    unittest.main()
