import asyncio
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from backend.composition_audit import read_xlsx_rows
from tests.test_resistance_groups import (
    FakeCollection,
    build_advanced_compare_response,
    build_product_composition_search_records,
    first_parseable_composition,
    parse_active_substances,
)


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "insecticides_raw_FINAL_v2.xlsx"


def normalize_import_value(value):
    text = str(value or "").strip()
    return None if not text or text.lower() in {"nan", "none"} else text


def product_key(record):
    return f"{record.get('product_name') or ''}|{record.get('registration_number') or ''}"


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


def search_composition(records):
    unique_values = []
    for record in records:
        value = record.get("active_substances_raw")
        if value not in unique_values:
            unique_values.append(value)
    grouped_record = {
        "product_name": records[0].get("product_name"),
        "active_substances_raw_values": unique_values,
    }
    return first_parseable_composition(
        build_product_composition_search_records(grouped_record, "insecticide"),
        "insecticide",
    )


class InsecticideSearchCompareFullParityTest(unittest.TestCase):
    def test_all_workbook_products_have_identical_search_and_compare_compositions(self):
        records_by_key = defaultdict(list)
        source_records = list(read_xlsx_rows(WORKBOOK))
        self.assertEqual(len(source_records), 3700)

        for source_record in source_records:
            record = {
                field: normalize_import_value(value)
                for field, value in source_record.items()
            }
            if not record.get("product_name"):
                continue
            key = product_key(record)
            record["product_key"] = key
            records_by_key[key].append(record)

        keys = list(records_by_key)
        self.assertEqual(len(keys), 541)
        self.assertEqual(sum(len(records) for records in records_by_key.values()), 3608)

        search_by_key = {}
        source_composition_missing = []
        restored_from_product_name = []
        still_unresolved = []
        nonempty_biological_compositions = []

        for key, records in records_by_key.items():
            raw_composition = search_composition(records)
            substances = parse_active_substances(raw_composition)
            active_substances = [
                substance for substance in substances if not substance.get("is_antidote")
            ]
            source_is_empty = not any(
                record.get("active_substances_raw") for record in records
            )
            if source_is_empty:
                source_composition_missing.append(key)
                if active_substances:
                    restored_from_product_name.append(key)
                else:
                    still_unresolved.append(key)
            elif not active_substances:
                nonempty_biological_compositions.append(key)

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

        self.assertEqual(len(source_composition_missing), 69)
        self.assertEqual(len(restored_from_product_name), 47)
        self.assertEqual(len(still_unresolved), 22)
        self.assertEqual(len(nonempty_biological_compositions), 20)

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
                    "insecticide",
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

    def test_repeated_units_in_product_name_are_normalized_before_parsing(self):
        product_name = (
            "Туарег, СМЭ (280 г/л г/л Имидаклоприд + 34 г/л г/л Имазалил + "
            "20 г/л г/л Тебуконазол)"
        )
        records = [{"product_name": product_name, "active_substances_raw": None}]

        composition = first_parseable_composition(records, "insecticide")
        substances = parse_active_substances(composition)

        self.assertEqual(
            composition,
            "(280 г/л Имидаклоприд + 34 г/л Имазалил + 20 г/л Тебуконазол)",
        )
        self.assertEqual(
            [(item["name"], item["concentration"]) for item in substances],
            [("Имидаклоприд", 280), ("Имазалил", 34), ("Тебуконазол", 20)],
        )

    def test_nonempty_source_composition_is_not_replaced_by_title_fallback(self):
        biological_composition = "(10¹⁰ КОЕ/Мл Bacillus thuringiensis B-501)"
        records = [{
            "product_name": "Тест (200 г/л Имидаклоприд)",
            "active_substances_raw": biological_composition,
        }]

        self.assertEqual(
            first_parseable_composition(records, "insecticide"),
            biological_composition,
        )


if __name__ == "__main__":
    unittest.main()
