import re
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
SERVER_TEXT = (ROOT / "backend" / "server.py").read_text()
HELPER_TEXT = "def is_valid_product_name" + SERVER_TEXT.split(
    "def is_valid_product_name", 1
)[1].split("# ==================== ENDPOINTS ====================", 1)[0]

namespace = {
    "re": re,
    "Any": Any,
    "Dict": Dict,
    "List": List,
    "Optional": Optional,
    "Sequence": Sequence,
    "Tuple": Tuple,
}
exec(HELPER_TEXT, namespace)

is_valid_product_name = namespace["is_valid_product_name"]
deduplicate_grouped_products = namespace["deduplicate_grouped_products"]


class ProductListCleanupTest(unittest.TestCase):
    def test_numeric_dates_and_registration_fragments_are_not_product_names(self):
        for value in (
            "2",
            "04.08.2028",
            "03.02.2021 02.02.2031",
            "184(026)-01-2445-1/411 30.10.2029",
        ):
            self.assertFalse(is_valid_product_name(value), value)

        self.assertTrue(is_valid_product_name("2,4-Д"))
        self.assertTrue(is_valid_product_name("Туарег, СМЭ"))

    def test_duplicate_visible_names_prefer_active_registration(self):
        inactive = {
            "_id": "tuareg-old",
            "product_name": "Туарег, СМЭ (280 г/л Имидаклоприд)",
            "registration_status": "Не действует",
            "active_substances_raw_values": ["(280 г/л Имидаклоприд)"],
            "applications_count": 6,
        }
        active = {
            "_id": "tuareg-active",
            "product_name": "Туарег, СМЭ (280 г/л г/л Имидаклоприд)",
            "registration_status": "Действует",
            "active_substances_raw_values": ["(280 г/л Имидаклоприд)"],
            "applications_count": 5,
        }
        numeric = {
            "_id": "bad-row",
            "product_name": "2",
            "registration_status": "Действует",
            "active_substances_raw_values": [],
            "applications_count": 1,
        }

        def clean_seed_treatment_name(value):
            return re.sub(r"\s*\([^()]*\)\s*$", "", value).strip(" ,;")

        result = deduplicate_grouped_products(
            [inactive, active, numeric],
            50,
            clean_seed_treatment_name,
        )

        self.assertEqual([row["_id"] for row in result], ["tuareg-active"])

    def test_all_categories_filter_imports_and_search_results(self):
        self.assertEqual(SERVER_TEXT.count("if not is_valid_product_name(product_name):"), 4)
        self.assertEqual(SERVER_TEXT.count("results = deduplicate_grouped_products("), 4)


class CompareReloadPersistenceTest(unittest.TestCase):
    TAB_TO_COMPARE = {
        "index.tsx": ("compare.tsx", "/compare", "selectedForCompare"),
        "insecticides.tsx": (
            "insecticide-compare.tsx",
            "/insecticide-compare",
            "selectedInsecticidesForCompare",
        ),
        "fungicides.tsx": (
            "fungicide-compare.tsx",
            "/fungicide-compare",
            "selectedFungicidesForCompare",
        ),
        "seed-treatments.tsx": (
            "seed-treatment-compare.tsx",
            "/seed-treatment-compare",
            "selectedSeedTreatmentsForCompare",
        ),
    }

    def test_all_compare_links_persist_both_product_keys_in_url(self):
        for tab_name, (_compare_name, pathname, selection_name) in self.TAB_TO_COMPARE.items():
            source = (ROOT / "frontend" / "app" / "(tabs)" / tab_name).read_text()
            self.assertIn(f"pathname: '{pathname}'", source)
            self.assertIn(f"left_key: {selection_name}[0]", source)
            self.assertIn(f"right_key: {selection_name}[1]", source)

    def test_all_compare_pages_restore_keys_from_route_parameters(self):
        for _tab_name, (compare_name, _pathname, _selection_name) in self.TAB_TO_COMPARE.items():
            source = (ROOT / "frontend" / "app" / compare_name).read_text()
            self.assertIn("useLocalSearchParams", source)
            self.assertIn("routeParams.left_key", source)
            self.assertIn("routeParams.right_key", source)
            self.assertIn("left_key: leftSelectedProductKey", source)
            self.assertIn("right_key: rightSelectedProductKey", source)
            self.assertIn("if (!hasComparableProducts)", source)


if __name__ == "__main__":
    unittest.main()
