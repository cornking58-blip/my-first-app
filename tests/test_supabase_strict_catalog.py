import unittest
from pathlib import Path

from backend.strict_catalog_ai import (
    build_strict_direct_answer,
    extract_single_product_candidate,
    select_unambiguous_catalog_match,
)

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
CATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")
MIGRATION = (ROOT / "backend" / "catalog_auto_migrate.py").read_text(encoding="utf-8")


class SupabaseStrictCatalogTest(unittest.TestCase):
    def test_follow_up_product_name_is_extracted(self):
        self.assertEqual(extract_single_product_candidate("а Ронилан? что думаешь?"), "Ронилан")
        self.assertEqual(extract_single_product_candidate("Что скажешь про Ронилан?"), "Ронилан")
        self.assertEqual(extract_single_product_candidate("Ронилан"), "Ронилан")

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
