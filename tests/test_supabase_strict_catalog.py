import unittest
from pathlib import Path

from backend.strict_catalog_ai import (
    build_strict_direct_answer,
    extract_single_product_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
CATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")
MIGRATION = (ROOT / "backend" / "catalog_auto_migrate.py").read_text(encoding="utf-8")


class SupabaseStrictCatalogTest(unittest.TestCase):
    def test_follow_up_product_name_is_extracted(self):
        self.assertEqual(extract_single_product_candidate("а Ранилан? что думаешь?"), "Ранилан")
        self.assertEqual(extract_single_product_candidate("Что скажешь про Ранилан?"), "Ранилан")
        self.assertEqual(extract_single_product_candidate("Ранилан"), "Ранилан")

    def test_field_question_is_not_mistaken_for_product_name(self):
        self.assertIsNone(extract_single_product_candidate("Что посоветуешь против ржавчины на подсолнечнике?"))

    def test_missing_product_never_invites_guessing(self):
        answer = build_strict_direct_answer({
            "intent": "product_not_found",
            "missing_products": ["Ранилан"],
            "suggestions": ["Ранилазол"],
        })
        self.assertIn("угадывать не буду", answer)
        self.assertIn("Ранилазол", answer)

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
