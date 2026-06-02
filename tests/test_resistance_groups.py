import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "server.py"
HELPER_SOURCE = SERVER_SOURCE.read_text().split(
    "# ==================== ACTIVE SUBSTANCE PARSER ====================", 1
)[1].split(
    "# ==================== ENDPOINTS ====================", 1
)[0]
namespace = {
    "re": re,
    "Any": Any,
    "Dict": Dict,
    "List": List,
    "Optional": Optional,
    "Sequence": Sequence,
    "AdvancedCompareRequest": object,
    "make_flexible_text_regex": lambda value: re.escape(value),
}
exec(HELPER_SOURCE, namespace)

parse_active_substances = namespace["parse_active_substances"]
parse_rate_max = namespace["parse_rate_max"]
select_rate = namespace["select_rate"]
get_resistance_group = namespace["get_resistance_group"]
annotate_substances_with_resistance = namespace["annotate_substances_with_resistance"]
build_resistance_group_analysis = namespace["build_resistance_group_analysis"]
build_price_analysis = namespace["build_price_analysis"]
build_crop_registration = namespace["build_crop_registration"]


class ResistanceGroupHelpersTest(unittest.TestCase):
    def test_get_resistance_group_known_herbicide_with_parser_extra_words(self):
        group = get_resistance_group("Глифосат кислоты", "herbicide")

        self.assertEqual(group["system"], "HRAC")
        self.assertEqual(group["group"], "9")
        self.assertEqual(group["name"], "EPSPS inhibitors")

    def test_unknown_group_returns_clear_unknown_name(self):
        group = get_resistance_group("неизвестное вещество", "fungicide")

        self.assertIsNone(group["system"])
        self.assertIsNone(group["group"])
        self.assertEqual(group["name"], "группа не определена")

    def test_identical_active_sets_are_reference_only_without_rotation_wording(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(125 г/л дифеноконазол + 200 г/л азоксистробин)"),
            "fungicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(125 г/л дифеноконазол + 200 г/л азоксистробин)"),
            "fungicide",
        )

        analysis = build_resistance_group_analysis(left, right)
        all_text = str(analysis).lower()

        self.assertTrue(analysis["identical_active_set"])
        self.assertEqual(analysis["same_group_matches"], [])
        self.assertEqual(analysis["different_group_matches"], [])
        self.assertIn("указаны справочно", analysis["plain_explanation"])
        self.assertNotIn("ротац", all_text)
        self.assertNotIn("лучше", all_text)
        self.assertEqual(
            {(item["substance"], item["system"], item["group"]) for item in analysis["reference_groups"]},
            {("дифеноконазол", "FRAC", "3"), ("азоксистробин", "FRAC", "11")},
        )

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

        self.assertFalse(analysis["identical_active_set"])
        self.assertEqual(len(analysis["same_group_matches"]), 1)
        match = analysis["same_group_matches"][0]
        self.assertEqual(match["system"], "HRAC")
        self.assertEqual(match["group"], "2")
        self.assertEqual(match["group_name"], "ALS inhibitors")
        self.assertIn("группа устойчивости одна: HRAC 2", match["warning"])

    def test_different_group_match_uses_neutral_message(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(360 г/л глифосат)"),
            "herbicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(600 г/л 2,4-Д)"),
            "herbicide",
        )

        analysis = build_resistance_group_analysis(left, right)

        self.assertEqual(len(analysis["different_group_matches"]), 1)
        match = analysis["different_group_matches"][0]
        self.assertEqual(match["left_group"], "HRAC 9")
        self.assertEqual(match["right_group"], "HRAC 4")
        self.assertEqual(match["message"], "Действующие вещества и группы устойчивости разные.")
        self.assertNotIn("ротац", match["message"].lower())
        self.assertNotIn("лучше", match["message"].lower())

    def test_seed_treatment_uses_mixed_frac_and_irac_lookup(self):
        fungicide_group = get_resistance_group("тебуконазол", "seed-treatment")
        insecticide_group = get_resistance_group("имидаклоприд", "seed-treatment")
        unknown_group = get_resistance_group("неизвестное вещество", "seed-treatment")

        self.assertEqual(fungicide_group["system"], "FRAC")
        self.assertEqual(fungicide_group["group"], "3")
        self.assertEqual(insecticide_group["system"], "IRAC")
        self.assertEqual(insecticide_group["group"], "4A")
        self.assertEqual(unknown_group["name"], "группа не определена")

    def test_manual_rate_overrides_max_registered_rate(self):
        max_rate = parse_rate_max("0,6-1,2")
        rate_used, rate_source = select_rate(0.8, max_rate)

        self.assertEqual(max_rate, 1.2)
        self.assertEqual(rate_used, 0.8)
        self.assertEqual(rate_source, "manual")

    def test_absent_manual_rate_keeps_max_registered_rate(self):
        max_rate = parse_rate_max("0,6-1,2")
        rate_used, rate_source = select_rate(None, max_rate)

        self.assertEqual(rate_used, 1.2)
        self.assertEqual(rate_source, "max_registered")

    def test_price_analysis_returns_per_substance_grams_and_cost_per_gram(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(100 г/л дифеноконазол + 200 г/л азоксистробин)"),
            "fungicide",
        )
        request = SimpleNamespace(left_price=300.0, right_price=None)

        analysis = build_price_analysis(request, left, [], 300.0, 0.0, 2.0, None)
        left_rows = [row for row in analysis["substances_cost"] if row["side"] == "left"]

        self.assertEqual(len(left_rows), 2)
        self.assertEqual([row["substance_name"] for row in left_rows], ["дифеноконазол", "азоксистробин"])
        self.assertEqual([row["grams_per_ha"] for row in left_rows], [200.0, 400.0])
        self.assertTrue(all(row["estimated_cost_per_gram"] is not None for row in left_rows))
        self.assertEqual(analysis["left_cost_per_ha"], 600.0)

    def test_crop_registration_true_false_and_absent_crop(self):
        left_records = [{"crop": "Подсолнечник"}]
        right_records = [{"crop": "Пшеница"}]

        result = build_crop_registration("подсолнечник", left_records, right_records)

        self.assertTrue(result["left"]["has_registration"])
        self.assertFalse(result["right"]["has_registration"])
        self.assertIsNone(build_crop_registration("", left_records, right_records))


if __name__ == "__main__":
    unittest.main()
