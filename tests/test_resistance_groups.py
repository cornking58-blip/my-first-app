import re
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "server.py"
HELPER_SOURCE = SERVER_SOURCE.read_text().split(
    "# ==================== ACTIVE SUBSTANCE PARSER ====================", 1
)[1].split(
    "def parse_rate_max", 1
)[0]
namespace = {
    "re": re,
    "Any": Any,
    "Dict": Dict,
    "List": List,
    "Optional": Optional,
}
exec(HELPER_SOURCE, namespace)

parse_active_substances = namespace["parse_active_substances"]
get_resistance_group = namespace["get_resistance_group"]
annotate_substances_with_resistance = namespace["annotate_substances_with_resistance"]
build_resistance_group_analysis = namespace["build_resistance_group_analysis"]


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
        self.assertIn("не полноценная ротация", match["warning"])

    def test_different_group_match_for_known_different_groups(self):
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
        self.assertIn("ротация", match["message"])

    def test_seed_treatment_uses_mixed_frac_and_irac_lookup(self):
        fungicide_group = get_resistance_group("тебуконазол", "seed-treatment")
        insecticide_group = get_resistance_group("имидаклоприд", "seed-treatment")
        unknown_group = get_resistance_group("неизвестное вещество", "seed-treatment")

        self.assertEqual(fungicide_group["system"], "FRAC")
        self.assertEqual(fungicide_group["group"], "3")
        self.assertEqual(insecticide_group["system"], "IRAC")
        self.assertEqual(insecticide_group["group"], "4A")
        self.assertEqual(unknown_group["name"], "группа не определена")


if __name__ == "__main__":
    unittest.main()
