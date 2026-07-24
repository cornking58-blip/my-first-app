import unittest
from pathlib import Path

from backend.catalog_quality import (
    canonical_product_name,
    filter_and_deduplicate_products,
    is_fumigant_row,
    should_exclude_product,
)


ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
CATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")


class CatalogPolishTest(unittest.TestCase):
    def test_spacing_and_known_aliases_are_deduplicated(self):
        products = [
            {
                "product_group": "seed_treatment",
                "product_name": "Кинг Комби",
                "registration_status": "Действует",
                "applications_count": 4,
                "active_substances_raw": "состав",
            },
            {
                "product_group": "seed_treatment",
                "product_name": "КингКомби",
                "registration_status": "Не действует",
                "applications_count": 1,
                "active_substances_raw": None,
            },
        ]
        result = filter_and_deduplicate_products(products)
        self.assertEqual(len(result), 1)
        self.assertEqual(canonical_product_name("КимКомби"), canonical_product_name("Кинг Комби"))

    def test_known_bad_fragment_is_removed(self):
        result = filter_and_deduplicate_products([
            {"product_group": "seed_treatment", "product_name": "Кимк"},
        ])
        self.assertEqual(result, [])

    def test_fumigants_are_not_seed_treatments(self):
        row = {
            "product_name": "Фумифаст",
            "pesticide_type": "Фумигант",
            "application_method": "Фумигация зернохранилищ",
        }
        self.assertTrue(is_fumigant_row(row))
        self.assertTrue(should_exclude_product("seed_treatment", [row]))

    def test_server_hides_links_and_uses_field_advisor_tone(self):
        self.assertIn("как опытный агроном разговаривает с хорошим знакомым прямо в поле", SERVER)
        self.assertIn("О сложном говори простыми словами", SERVER)
        self.assertIn("Не показывай пользователю URL", SERVER)
        self.assertIn("return sanitize_ai_output(answer.strip())", SERVER)
        self.assertIn("get_ai_reasoning_effort(current_message)", SERVER)

    def test_catalog_applies_cleanup_before_returning_results(self):
        self.assertIn("filter_and_deduplicate_products(rows)[:limit]", CATALOG)
        self.assertIn("should_exclude_product(group, product_rows)", CATALOG)


if __name__ == "__main__":
    unittest.main()
