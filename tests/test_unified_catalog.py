import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
CATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "app" / "(tabs)" / "index.tsx").read_text(encoding="utf-8")
AI_SCREEN = (ROOT / "frontend" / "app" / "ai.tsx").read_text(encoding="utf-8")
SCHEMA = (ROOT / "supabase" / "migrations" / "001_unified_pesticide_catalog.sql").read_text(encoding="utf-8")


class UnifiedCatalogStaticTest(unittest.TestCase):
    def test_all_current_product_groups_are_present(self):
        for group, collection in (
            ("herbicide", "herbicide_records"),
            ("fungicide", "fungicide_records"),
            ("insecticide", "insecticide_records"),
            ("seed_treatment", "seed_treatment_records"),
        ):
            self.assertIn(f'"{group}"', CATALOG)
            self.assertIn(f'"{collection}"', CATALOG)

    def test_ai_is_database_first(self):
        self.assertIn("return await build_catalog_ai_context(db, message)", SERVER)
        self.assertIn('"verified_from_catalog": len(found) == 2', CATALOG)
        self.assertIn("Интернет-поиск не требуется", CATALOG)
        self.assertIn("build_direct_catalog_answer(context)", SERVER)
        self.assertIn("def build_direct_catalog_answer", CATALOG)

    def test_product_names_are_found_with_inflection_and_context(self):
        self.assertIn("_product_name_regex(product_name)", CATALOG)
        self.assertIn("_clean_product_phrase", CATALOG)
        self.assertIn("loose=True", CATALOG)

    def test_universal_api_is_connected(self):
        self.assertIn('router.get("/products/search")', CATALOG)
        self.assertIn("app.include_router(create_products_router(db))", SERVER)
        self.assertIn("/api/products/search", INDEX)

    def test_product_title_is_not_limited_to_herbicides(self):
        self.assertIn("Справочник пестицидов РФ", INDEX)
        self.assertIn("единого справочника пестицидов РФ", AI_SCREEN)
        self.assertNotIn("Справочник гербицидов РФ", INDEX)

    def test_supabase_schema_and_migration_exist(self):
        self.assertIn("create table if not exists public.catalog_products", SCHEMA)
        self.assertIn("create table if not exists public.catalog_applications", SCHEMA)
        self.assertIn("search_catalog_products", SCHEMA)
        self.assertTrue((ROOT / "backend" / "migrate_catalog_to_supabase.py").exists())


if __name__ == "__main__":
    unittest.main()
