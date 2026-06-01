import re
import unittest
from pathlib import Path
from typing import Optional, Sequence


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "server.py"
HELPER_SOURCE = SERVER_SOURCE.read_text().split("RUSSIAN_ENDINGS =", 1)[1].split(
    "# ==================== ACTIVE SUBSTANCE PARSER ====================", 1
)[0]
namespace = {"re": re, "Optional": Optional, "Sequence": Sequence}
exec("RUSSIAN_ENDINGS =" + HELPER_SOURCE, namespace)

make_flexible_text_regex = namespace["make_flexible_text_regex"]
build_registration_filters = namespace["build_registration_filters"]
build_search_match = namespace["build_search_match"]


class FlexibleFilterHelpersTest(unittest.TestCase):
    def assert_matches(self, query_value: str, stored_value: str):
        pattern = make_flexible_text_regex(query_value)
        self.assertRegex(stored_value, re.compile(pattern, re.IGNORECASE))

    def test_russian_endings_and_yo_are_flexible(self):
        self.assert_matches("пшеница", "Пшеницы")
        self.assert_matches("береза", "Берёзы")
        self.assert_matches("сорняки", "сорняков")

    def test_ocr_broken_word_matches_unbroken_query(self):
        self.assert_matches("подсолнечник", "Подсолнечн ик")

    def test_registration_filters_are_row_level_crop_and_target_matches(self):
        filters = build_registration_filters(culture="пшеница", harmful_object="сорняки")
        self.assertEqual(set(filters), {"crop", "target_object"})
        self.assertRegex("Пшеницы озимой", re.compile(filters["crop"]["$regex"], re.IGNORECASE))
        self.assertRegex("Однолетние сорняки", re.compile(filters["target_object"]["$regex"], re.IGNORECASE))

    def test_registration_filters_can_target_multiple_harmful_object_fields(self):
        filters = build_registration_filters(
            harmful_object="ржавчина",
            harmful_object_fields=("target_object", "disease"),
        )
        self.assertEqual(set(filters), {"$or"})
        fields = {next(iter(item.keys())) for item in filters["$or"]}
        self.assertEqual(fields, {"target_object", "disease"})
        for item in filters["$or"]:
            field_filter = next(iter(item.values()))
            self.assertRegex("Бурая ржавчина", re.compile(field_filter["$regex"], re.IGNORECASE))

    def test_registration_filters_match_ocr_broken_fungicide_row(self):
        filters = build_registration_filters(culture="подсолнечник", harmful_object="ржавчина")
        crop_regex = re.compile(filters["crop"]["$regex"], re.IGNORECASE)
        target_regex = re.compile(filters["target_object"]["$regex"], re.IGNORECASE)

        self.assertRegex("Подсолнечн ик", crop_regex)
        self.assertRegex(
            "Альтернариоз, белая гниль корзинок, ржавчина, фомоз, фомопсис",
            target_regex,
        )

    def test_search_match_uses_all_tokens_across_row_fields(self):
        match = build_search_match("пшеница + сорняки")
        self.assertIn("$and", match)
        self.assertEqual(len(match["$and"]), 2)
        for token_clause in match["$and"]:
            fields = {next(iter(item.keys())) for item in token_clause["$or"]}
            self.assertIn("crop", fields)
            self.assertIn("target_object", fields)
            self.assertIn("product_name", fields)


if __name__ == "__main__":
    unittest.main()
