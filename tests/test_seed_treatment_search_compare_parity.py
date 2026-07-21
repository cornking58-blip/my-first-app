import asyncio
import importlib.util
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "seed_treatments_FINAL_v2.xlsx"
AUDIT_MODULE = ROOT / "backend" / "seed_treatment_full_audit.py"
HELPER_TEST_MODULE = ROOT / "tests" / "test_resistance_groups.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helpers = load_module("test_resistance_groups_helpers", HELPER_TEST_MODULE)
FakeCollection = helpers.FakeCollection
build_advanced_compare_response = helpers.build_advanced_compare_response
build_seed_treatment_search_response = helpers.build_seed_treatment_search_response


def load_seed_treatment_rows():
    module = load_module("seed_treatment_full_audit", AUDIT_MODULE)
    return module.read_rows(WORKBOOK, module.SHEET_NAME)


def normalize_import_value(value):
    text = str(value or "").strip()
    return None if not text or text.lower() in {"nan", "none"} else text


def product_key(record):
    return f"{record.get('product_name') or ''}|{record.get('registration_number') or ''}"


def grouped_search_record(key, records):
    first = records[0]

    def values(field):
        return [record.get(field) or None for record in records]

    raw_values = []
    for value in values("active_substances_raw"):
        if value not in raw_values:
            raw_values.append(value)

    return {
        "_id": key,
        "product_name": first.get("product_name"),
        "formulation": first.get("formulation"),
        "active_substances_raw_values": raw_values,
        "manufacturer": first.get("manufacturer"),
        "registrant": values("registrant"),
        "producer": values("producer"),
        "company": values("company"),
        "applicant": values("applicant"),
        "registration_holder": values("registration_holder"),
        "registrant_name": values("registrant_name"),
        "manufacturer_name": values("manufacturer_name"),
        "producer_name": values("producer_name"),
        "organization": values("organization"),
        "registrant_organization": values("registrant_organization"),
        "certificate_holder": values("certificate_holder"),
        "all_manufacturers": values("manufacturer"),
        "registration_status": first.get("registration_status"),
        "pesticide_type": first.get("pesticide_type"),
        "applications_count": len(records),
    }


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


class SeedTreatmentSearchCompareFullParityTest(unittest.TestCase):
    def test_all_workbook_products_have_identical_search_and_compare_compositions(self):
        records_by_key = defaultdict(list)
        for record in load_seed_treatment_rows():
            record = {
                field: normalize_import_value(value)
                for field, value in record.items()
                if field != "_excel_row_number"
            }
            key = product_key(record)
            record["product_key"] = key
            records_by_key[key].append(record)

        keys = list(records_by_key)
        self.assertEqual(len(keys), 360)
        self.assertEqual(sum(len(records) for records in records_by_key.values()), 1435)

        search_by_key = {
            key: build_seed_treatment_search_response(grouped_search_record(key, records))
            for key, records in records_by_key.items()
        }
        collection = FakeCollection(records_by_key)
        mismatches = []

        async def compare_all_pairs():
            for index in range(0, len(keys), 2):
                left_key = keys[index]
                right_key = keys[index + 1]
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
                    "seed-treatment",
                )
                for key, side in ((left_key, "left"), (right_key, "right")):
                    search = search_by_key[key]
                    compare = response[side]
                    expected_total = sum(
                        substance.get("concentration") or 0
                        for substance in search["active_substances"]
                        if not substance.get("is_antidote")
                    )
                    fields = {
                        "product_name": (search.get("product_name"), compare.get("product_name")),
                        "display_product_name": (
                            search.get("display_product_name"),
                            compare.get("display_product_name"),
                        ),
                        "raw_product_name": (
                            search.get("raw_product_name"),
                            compare.get("raw_product_name"),
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
                            expected_total,
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

        asyncio.run(compare_all_pairs())

        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
