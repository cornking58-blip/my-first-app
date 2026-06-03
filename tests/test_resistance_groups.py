import asyncio
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "server.py"
HELPER_SOURCE = SERVER_SOURCE.read_text().split(
    "# ==================== ACTIVE SUBSTANCE PARSER ====================", 1
)[1].split(
    "# ==================== HELPER FUNCTIONS ====================", 1
)[0]


def normalize_search_text(value: str) -> str:
    normalized = (value or "").strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-яе]+", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class LoggerStub:
    def error(self, *_args, **_kwargs):
        pass


class AdvancedCompareRequest:
    pass


namespace = {
    "re": re,
    "Any": Any,
    "Dict": Dict,
    "List": List,
    "Optional": Optional,
    "Sequence": Sequence,
    "normalize_search_text": normalize_search_text,
    "HTTPException": HTTPException,
    "AdvancedCompareRequest": AdvancedCompareRequest,
    "logger": LoggerStub(),
}
exec(HELPER_SOURCE, namespace)

parse_active_substances = namespace["parse_active_substances"]
get_resistance_group = namespace["get_resistance_group"]
annotate_substances_with_resistance = namespace["annotate_substances_with_resistance"]
build_resistance_group_analysis = namespace["build_resistance_group_analysis"]
parse_rate_max_with_unit = namespace["parse_rate_max_with_unit"]
calculate_active_amount = namespace["calculate_active_amount"]
build_advanced_compare_response = namespace["build_advanced_compare_response"]


class FakeCursor:
    def __init__(self, records):
        self.records = records

    async def to_list(self, length=1000):
        return self.records[:length]


class FakeCollection:
    def __init__(self, records_by_key):
        self.records_by_key = records_by_key

    def find(self, query):
        return FakeCursor(self.records_by_key.get(query["product_key"], []))


class RateUnitParsingTest(unittest.TestCase):
    def test_rate_parser_normalizes_supported_units(self):
        cases = [
            ("25-50 г/га", 0.05, "кг/га"),
            ("до 50 г/га", 0.05, "кг/га"),
            ("30–50 г/га", 0.05, "кг/га"),
            ("125 мл/га", 0.125, "л/га"),
            ("0,125 л/га", 0.125, "л/га"),
            ("1,5 кг/га", 1.5, "кг/га"),
        ]

        for raw_rate, expected_rate, expected_unit in cases:
            with self.subTest(raw_rate=raw_rate):
                parsed_rate, parsed_unit = parse_rate_max_with_unit(raw_rate)

                self.assertAlmostEqual(parsed_rate, expected_rate)
                self.assertEqual(parsed_unit, expected_unit)

    def test_active_amount_uses_compatible_concentration_and_rate_units(self):
        self.assertEqual(calculate_active_amount(750, "г/кг", 0.05, "кг/га"), 37.5)
        self.assertEqual(calculate_active_amount(100, "г/л", 0.5, "л/га"), 50)


class ResistanceGroupHelpersTest(unittest.TestCase):
    def test_get_resistance_group_known_herbicide_with_parser_extra_words(self):
        group = get_resistance_group("Глифосат кислоты", "herbicide")

        self.assertEqual(group["system"], "HRAC")
        self.assertEqual(group["group"], "9")
        self.assertEqual(group["name"], "EPSPS inhibitors")
        self.assertEqual(group["effect_summary"], "Кратко: нарушает синтез важных аминокислот у растения.")

    def test_known_group_annotation_keeps_existing_fields_and_adds_effect_summary(self):
        annotated = annotate_substances_with_resistance(
            parse_active_substances("(250 г/л тебуконазол)"),
            "fungicide",
        )

        self.assertEqual(annotated[0]["resistance_system"], "FRAC")
        self.assertEqual(annotated[0]["resistance_group"], "3")
        self.assertEqual(annotated[0]["resistance_group_name"], "DMI fungicides")
        self.assertEqual(annotated[0]["effect_summary"], "Кратко: нарушает синтез клеточной мембраны гриба.")

    def test_unknown_group_returns_clear_unknown_name(self):
        group = get_resistance_group("неизвестное вещество", "fungicide")

        self.assertIsNone(group["system"])
        self.assertIsNone(group["group"])
        self.assertEqual(group["name"], "группа не определена")
        self.assertNotIn("effect_summary", group)

    def test_identical_active_sets_are_reference_only_without_forbidden_wording(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(360 г/л глифосат)"),
            "herbicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(360 г/л глифосат)"),
            "herbicide",
        )

        analysis = build_resistance_group_analysis(left, right)
        serialized = str(analysis).lower()

        self.assertTrue(analysis["identical_active_substance_sets"])
        self.assertEqual(
            analysis["plain_explanation"],
            "Действующие вещества совпадают. Группы устойчивости указаны справочно.",
        )
        self.assertEqual(analysis["same_group_matches"], [])
        self.assertEqual(analysis["different_group_matches"], [])
        self.assertIn("reference_groups", analysis)
        self.assertIn("HRAC", analysis["reference_groups"]["left"][0]["message"])
        forbidden_phrases = [
            "rot" + "ation is " + "better",
            "better for " + "rot" + "ation",
            "\u0440\u043e\u0442\u0430\u0446\u0438\u044f " + "\u043b\u0443\u0447\u0448\u0435",
            "\u043b\u0443\u0447\u0448\u0430\u044f " + "\u0440\u043e\u0442\u0430\u0446\u0438\u044f",
        ]
        for forbidden in forbidden_phrases:
            self.assertNotIn(forbidden, serialized)

    def test_same_group_match_warning_for_different_substances(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(750 г/кг трибенурон-метил)"),
            "herbicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(40 г/л имазамокс)"),
            "herbicide",
        )

        analysis = build_resistance_group_analysis(left, right)

        self.assertEqual(len(analysis["same_group_matches"]), 1)
        match = analysis["same_group_matches"][0]
        self.assertEqual(match["system"], "HRAC")
        self.assertEqual(match["group"], "2")
        self.assertEqual(match["group_name"], "ALS inhibitors")
        self.assertEqual(match["effect_summary"], "Кратко: нарушает синтез важных аминокислот у растения.")
        self.assertEqual(
            match["warning"],
            "Действующие вещества разные, но группа устойчивости одна. По механизму действия препараты близки.",
        )
        self.assertEqual(
            analysis["plain_explanation"],
            "Действующие вещества разные, но группа устойчивости одна. По механизму действия препараты близки.",
        )

    def test_different_group_match_for_known_different_groups_is_neutral(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(360 г/л глифосат)"),
            "herbicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(600 г/л 2,4-Д)"),
            "herbicide",
        )

        analysis = build_resistance_group_analysis(left, right)
        serialized = str(analysis).lower()

        self.assertEqual(len(analysis["different_group_matches"]), 1)
        match = analysis["different_group_matches"][0]
        self.assertEqual(match["left_group"], "HRAC 9")
        self.assertEqual(match["right_group"], "HRAC 4")
        self.assertEqual(match["message"], "Действующие вещества и группы устойчивости разные.")
        self.assertEqual(analysis["plain_explanation"], "Действующие вещества и группы устойчивости разные.")
        self.assertNotIn("ротац" + "ия", serialized)

    def test_unknown_groups_still_return_group_not_defined_message(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(100 г/л неизвестное вещество)"),
            "fungicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(200 г/л другое неизвестное вещество)"),
            "fungicide",
        )

        analysis = build_resistance_group_analysis(left, right)

        self.assertEqual(len(analysis["unknown_group_substances"]), 2)
        self.assertIn("группа не определена", analysis["plain_explanation"])
        self.assertEqual(analysis["unknown_group_substances"][0]["message"], "группа не определена")
        self.assertNotIn("effect_summary", analysis["unknown_group_substances"][0])

    def test_seed_treatment_uses_mixed_frac_and_irac_lookup(self):
        fungicide_group = get_resistance_group("тебуконазол", "seed-treatment")
        insecticide_group = get_resistance_group("имидаклоприд", "seed-treatment")
        unknown_group = get_resistance_group("неизвестное вещество", "seed-treatment")

        self.assertEqual(fungicide_group["system"], "FRAC")
        self.assertEqual(fungicide_group["group"], "3")
        self.assertEqual(insecticide_group["system"], "IRAC")
        self.assertEqual(insecticide_group["group"], "4A")
        self.assertEqual(unknown_group["name"], "группа не определена")


class AdvancedCompareResponseTest(unittest.TestCase):
    def make_collection(self):
        return FakeCollection({
            "left": [
                {
                    "product_key": "left",
                    "product_name": "Препарат А",
                    "formulation": "КЭ",
                    "active_substances_raw": "(100 г/л дифеноконазол + 200 г/л азоксистробин)",
                    "registration_status": "Действует",
                    "rate_raw": "0,5-1,0",
                    "crop": "подсолнечн ик",
                },
                {
                    "product_key": "left",
                    "product_name": "Препарат А",
                    "formulation": "КЭ",
                    "active_substances_raw": "(100 г/л дифеноконазол + 200 г/л азоксистробин)",
                    "registration_status": "Действует",
                    "rate_raw": "0,7",
                    "crop": "пшеница",
                },
            ],
            "right": [
                {
                    "product_key": "right",
                    "product_name": "Препарат Б",
                    "formulation": "КС",
                    "active_substances_raw": "(250 г/л тебуконазол)",
                    "registration_status": "Действует",
                    "rate_raw": "1,2-1,5",
                    "crop": "кукуруза",
                }
            ],
        })

    def compare(self, **overrides):
        request = SimpleNamespace(
            left_key="left",
            right_key="right",
            left_price=None,
            right_price=None,
            left_rate=None,
            right_rate=None,
            crop=None,
        )
        for key, value in overrides.items():
            setattr(request, key, value)
        return asyncio.run(build_advanced_compare_response(request, self.make_collection(), "fungicide"))

    def test_manual_left_and_right_rates_override_max_parsed_rate(self):
        response = self.compare(left_rate=0.4, right_rate=0.9)

        self.assertEqual(response["left"]["max_rate"], 1.0)
        self.assertEqual(response["right"]["max_rate"], 1.5)
        self.assertEqual(response["left"]["rate_used"], 0.4)
        self.assertEqual(response["right"]["rate_used"], 0.9)
        self.assertEqual(response["left"]["rate_source"], "manual")
        self.assertEqual(response["right"]["rate_source"], "manual")
        self.assertEqual(response["left"]["max_rate_unit"], None)
        self.assertEqual(response["left"]["rate_unit"], None)

    def test_registered_gram_rate_sets_unit_fields_and_manual_keeps_same_unit(self):
        collection = FakeCollection({
            "left": [
                {
                    "product_key": "left",
                    "product_name": "Сухой препарат",
                    "formulation": "ВДГ",
                    "active_substances_raw": "(750 г/кг трибенурон-метил)",
                    "registration_status": "Действует",
                    "rate_raw": "25-50 г/га",
                    "crop": "пшеница",
                }
            ],
            "right": [
                {
                    "product_key": "right",
                    "product_name": "Жидкий препарат",
                    "formulation": "КС",
                    "active_substances_raw": "(100 г/л дифеноконазол)",
                    "registration_status": "Действует",
                    "rate_raw": "0,5 л/га",
                    "crop": "пшеница",
                }
            ],
        })
        request = SimpleNamespace(
            left_key="left",
            right_key="right",
            left_price=1000,
            right_price=800,
            left_rate=0.04,
            right_rate=None,
            crop=None,
        )

        response = asyncio.run(build_advanced_compare_response(request, collection, "herbicide"))

        self.assertEqual(response["left"]["max_rate"], 0.05)
        self.assertEqual(response["left"]["max_rate_unit"], "кг/га")
        self.assertEqual(response["left"]["rate_used"], 0.04)
        self.assertEqual(response["left"]["rate_unit"], "кг/га")
        self.assertEqual(response["left"]["rate_source"], "manual")
        self.assertEqual(response["left"]["total_per_ha"], 30.0)
        self.assertEqual(response["right"]["max_rate"], 0.5)
        self.assertEqual(response["right"]["max_rate_unit"], "л/га")
        self.assertEqual(response["right"]["rate_used"], 0.5)
        self.assertEqual(response["right"]["rate_unit"], "л/га")
        self.assertEqual(response["right"]["total_per_ha"], 50.0)
        self.assertEqual(response["price_analysis"]["left_substances_cost"][0]["grams_per_ha"], 30.0)
        self.assertEqual(response["price_analysis"]["left_substances_cost"][0]["rate_unit"], "кг/га")

    def test_absent_manual_rate_keeps_max_registered_rate_behavior(self):
        response = self.compare()

        self.assertEqual(response["left"]["rate_used"], 1.0)
        self.assertEqual(response["right"]["rate_used"], 1.5)
        self.assertEqual(response["left"]["rate_source"], "max_registered")
        self.assertEqual(response["right"]["rate_source"], "max_registered")

    def test_price_analysis_returns_per_substance_grams_and_cost_per_gram(self):
        response = self.compare(left_price=1200, right_price=900)
        left_costs = response["price_analysis"]["left_substances_cost"]
        right_costs = response["price_analysis"]["right_substances_cost"]

        self.assertEqual(left_costs[0]["substance_name"], "дифеноконазол")
        self.assertEqual(left_costs[0]["grams_per_ha"], 100.0)
        self.assertIsNotNone(left_costs[0]["estimated_cost_per_gram"])
        self.assertEqual(right_costs[0]["grams_per_ha"], 375.0)
        self.assertIsNotNone(right_costs[0]["estimated_cost_per_gram"])
        self.assertIn("substances_cost", response["price_analysis"])

    def test_crop_provided_and_product_has_row_returns_true(self):
        response = self.compare(crop="подсолнечник")

        self.assertTrue(response["crop_registration"]["left"]["has_registration"])
        self.assertEqual(response["crop_registration"]["left"]["message"], "Есть регистрация на выбранную культуру")

    def test_crop_provided_and_product_without_row_returns_false(self):
        response = self.compare(crop="подсолнечник")

        self.assertFalse(response["crop_registration"]["right"]["has_registration"])
        self.assertEqual(response["crop_registration"]["right"]["message"], "Нет регистрации на выбранную культуру")


    def test_crop_registration_matches_case_yo_and_inflected_list_text(self):
        collection = FakeCollection({
            "left": [
                {
                    "product_key": "left",
                    "product_name": "Препарат А",
                    "formulation": "КЭ",
                    "active_substances_raw": "(100 г/л дифеноконазол)",
                    "registration_status": "Действует",
                    "rate_raw": "0,5",
                    "crop": "Подсолнечника, рапса и свёклы",
                }
            ],
            "right": [
                {
                    "product_key": "right",
                    "product_name": "Препарат Б",
                    "formulation": "КС",
                    "active_substances_raw": "(250 г/л тебуконазол)",
                    "registration_status": "Действует",
                    "rate_raw": "1,0",
                    "crop": "кукуруза",
                }
            ],
        })
        request = SimpleNamespace(
            left_key="left",
            right_key="right",
            left_price=None,
            right_price=None,
            left_rate=None,
            right_rate=None,
            crop="  подсолнечник  ",
        )

        response = asyncio.run(build_advanced_compare_response(request, collection, "fungicide"))

        self.assertTrue(response["crop_registration"]["left"]["has_registration"])
        self.assertFalse(response["crop_registration"]["right"]["has_registration"])

    def test_crop_absent_comparison_still_works_without_crop_registration_block(self):
        response = self.compare()

        self.assertIn("left", response)
        self.assertIn("right", response)
        self.assertNotIn("crop_registration", response)


if __name__ == "__main__":
    unittest.main()
