import unittest
from pathlib import Path

from backend.product_catalog import detect_group, extract_manufacturer, is_catalog_request
from backend.strict_catalog_ai import (
    build_strict_direct_answer,
    extract_single_product_candidate,
    select_catalog_substance_matches,
    select_unambiguous_catalog_match,
)

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
CATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")
STRICT_AI_SOURCE = (ROOT / "backend" / "strict_catalog_ai.py").read_text(encoding="utf-8")
MIGRATION = (ROOT / "backend" / "catalog_auto_migrate.py").read_text(encoding="utf-8")


class SupabaseStrictCatalogTest(unittest.TestCase):
    def test_follow_up_product_name_is_extracted(self):
        self.assertEqual(extract_single_product_candidate("а Ронилан? что думаешь?"), "Ронилан")
        self.assertEqual(extract_single_product_candidate("Что скажешь про Ронилан?"), "Ронилан")
        self.assertEqual(extract_single_product_candidate("Ронилан"), "Ронилан")

    def test_manufacturer_catalog_command_is_recognized_before_product_lookup(self):
        message = "выпиши протравители щёлковоагрохим"
        self.assertTrue(is_catalog_request(message))
        self.assertEqual(detect_group(message), "seed_treatment")
        self.assertEqual(extract_manufacturer(message), "щёлковоагрохим")
        self.assertLess(
            STRICT_AI_SOURCE.index("if is_catalog_request(message):"),
            STRICT_AI_SOURCE.index("candidate = extract_single_product_candidate(message)"),
        )

    def test_product_prefix_is_removed_before_lookup(self):
        self.assertEqual(extract_single_product_candidate("препарат Цепелин"), "Цепелин")
        self.assertEqual(
            extract_single_product_candidate("расскажи про препарат Цепелин"),
            "Цепелин",
        )

    def test_active_substance_follow_up_is_cleaned(self):
        self.assertEqual(
            extract_single_product_candidate("а фамоксадон тогда для чего?"),
            "фамоксадон",
        )
        self.assertEqual(
            extract_single_product_candidate("а цимоксанил зачем?"),
            "цимоксанил",
        )

    def test_active_substance_is_detected_in_composition(self):
        products = [
            {
                "product_name": "Улис",
                "product_key": "ulis",
                "product_group": "fungicide",
                "active_substances_raw": "Фамоксадон 225 г/кг + цимоксанил 300 г/кг",
            },
            {
                "product_name": "Другой препарат",
                "product_key": "other",
                "product_group": "fungicide",
                "active_substances_raw": "Тебуконазол 250 г/л",
            },
        ]
        matches = select_catalog_substance_matches(products, "фамоксадон")
        self.assertEqual([item["product_name"] for item in matches], ["Улис"])

    def test_unique_one_letter_typo_can_resolve_to_product(self):
        products = [
            {"product_name": "Ронилан", "product_key": "ronilan"},
            {"product_name": "Протазокс", "product_key": "protazox"},
        ]
        match = select_unambiguous_catalog_match(products, "Ранилан")
        self.assertIsNotNone(match)
        self.assertEqual(match["product_name"], "Ронилан")

    def test_field_question_is_not_mistaken_for_product_name(self):
        self.assertIsNone(extract_single_product_candidate("Что посоветуешь против ржавчины на подсолнечнике?"))

    def test_missing_product_never_invites_guessing(self):
        answer = build_strict_direct_answer({
            "intent": "product_not_found",
            "missing_products": ["Неизвестный препарат"],
            "suggestions": ["Ронилан"],
        })
        self.assertIn("угадывать не буду", answer)
        self.assertIn("Ронилан", answer)

    def test_web_fallback_can_be_forbidden_by_context(self):
        self.assertIn('if context.get("allow_web_fallback") is False:', SERVER)
        self.assertIn("build_strict_catalog_ai_context", SERVER)
        self.assertIn("build_strict_direct_answer", SERVER)

    def test_supabase_can_be_made_mandatory(self):
        self.assertIn('CATALOG_BACKEND', CATALOG)
        self.assertIn('CATALOG_ALLOW_MONGO_FALLBACK', CATALOG)
        self.assertIn('raise HTTPException(status_code=503, detail="Каталог временно недоступен")', CATALOG)

    def test_one_time_migration_is_supported(self):
        self.assertIn("CATALOG_MIGRATE_ON_START", MIGRATION)
        self.assertIn("CATALOG_MIGRATION_COMPLETED", MIGRATION)
        self.assertIn("schedule_catalog_migration(db)", SERVER)


if __name__ == "__main__":
    unittest.main()
