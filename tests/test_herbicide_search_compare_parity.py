import asyncio
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from backend.composition_audit import read_xlsx_rows
from tests.test_resistance_groups import (
    FakeCollection,
    build_advanced_compare_response,
    first_parseable_composition,
    parse_active_substances,
)


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "herbicides_raw_FINAL_checked.xlsx"


def normalize_import_value(value):
    text = str(value or "").strip()
    return None if not text or text.lower() in {"nan", "none"} else text


def product_key(record):
    return f"{record.get('product_name') or ''}|{record.get('registration_number') or ''}"


def search_composition(records):
    unique_values = []
    for record in records:
        value = record.get("active_substances_raw")
        if value not in unique_values:
            unique_values.append(value)
    return first_parseable_composition(
        [{"active_substances_raw": value} for value in unique_values],
        "herbicide",
    )


def composition_signature(substances):
    return [
        (
            substance.get("name"),
            substance.get("concentration"),
            substance.get("unit"),
            bool(substance.get("is_antidote")),
        )
        for substance in substances or []
    ]


class HerbicideSearchCompareFullParityTest(unittest.TestCase):
    def test_all_workbook_products_have_identical_search_and_compare_compositions(self):
        records_by_key = defaultdict(list)
        for source_record in read_xlsx_rows(WORKBOOK):
            record = {
                field: normalize_import_value(value)
                for field, value in source_record.items()
            }
            if not record.get("product_name"):
                continue
            key = product_key(record)
            record["product_key"] = key
            record["pesticide_type"] = "herbicide"
            records_by_key[key].append(record)

        keys = list(records_by_key)
        self.assertEqual(len(keys), 956)
        self.assertEqual(sum(len(records) for records in records_by_key.values()), 3232)

        search_by_key = {}
        for key, records in records_by_key.items():
            raw_composition = search_composition(records)
            substances = parse_active_substances(raw_composition)
            active_substances = [
                substance for substance in substances if not substance.get("is_antidote")
            ]
            search_by_key[key] = {
                "product_name": records[0].get("product_name"),
                "active_substances_raw": raw_composition,
                "active_substances": active_substances,
                "substance_count": len(active_substances),
                "total_concentration": sum(
                    substance.get("concentration") or 0
                    for substance in active_substances
                ),
            }

        collection = FakeCollection(records_by_key)
        mismatches = []

        async def compare_all_products():
            for index in range(0, len(keys), 2):
                left_key = keys[index]
                right_key = keys[index + 1] if index + 1 < len(keys) else keys[0]
                request = SimpleNamespace(
                    left_key=left_key,
                    right_key=right_key,
                    left_price=None,
                    right_price=None,
                    left_rate=None,
                    right_rate=None,
                    crop=None,
                )
                response = await build_advanced_compare_response(
                    request,
                    collection,
                    "herbicide",
                )
                for key, side in ((left_key, "left"), (right_key, "right")):
                    search = search_by_key[key]
                    compare = response[side]
                    fields = {
                        "product_name": (
                            search.get("product_name"),
                            compare.get("product_name"),
                        ),
                        "active_substances_raw": (
                            search.get("active_substances_raw"),
                            compare.get("active_substances_raw"),
                        ),
                        "active_substances": (
                            composition_signature(search.get("active_substances")),
                            composition_signature(compare.get("active_substances")),
                        ),
                        "substance_count": (
                            search.get("substance_count"),
                            compare.get("substance_count"),
                        ),
                        "total_concentration": (
                            search.get("total_concentration"),
                            compare.get("total_concentration"),
                        ),
                    }
                    different = {
                        field: {"search": values[0], "compare": values[1]}
                        for field, values in fields.items()
                        if values[0] != values[1]
                    }
                    if different:
                        mismatches.append({"product_key": key, "fields": different})

        asyncio.run(compare_all_products())

        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
