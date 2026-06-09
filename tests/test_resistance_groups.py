import asyncio
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "server.py"
SERVER_TEXT = SERVER_SOURCE.read_text()
MANUFACTURER_HELPER_SOURCE = "DISPLAY_MANUFACTURER_FALLBACK =" + SERVER_TEXT.split(
    "DISPLAY_MANUFACTURER_FALLBACK =", 1
)[1].split(
    "# ==================== ACTIVE SUBSTANCE PARSER ====================", 1
)[0]
HELPER_SOURCE = SERVER_TEXT.split(
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
    "json": json,
    "Path": Path,
    "ROOT_DIR": SERVER_SOURCE.parent,
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
exec(MANUFACTURER_HELPER_SOURCE + HELPER_SOURCE, namespace)

parse_active_substances = namespace["parse_active_substances"]
validate_active_substance_composition = namespace["validate_active_substance_composition"]
composition_warning_codes = namespace["composition_warning_codes"]
get_resistance_group = namespace["get_resistance_group"]
annotate_substances_with_resistance = namespace["annotate_substances_with_resistance"]
build_resistance_group_analysis = namespace["build_resistance_group_analysis"]
parse_rate_max_with_unit = namespace["parse_rate_max_with_unit"]
calculate_active_amount = namespace["calculate_active_amount"]
build_advanced_compare_response = namespace["build_advanced_compare_response"]
load_resistance_groups = namespace["load_resistance_groups"]
RESISTANCE_GROUP_DATA = namespace["RESISTANCE_GROUP_DATA"]
OLD_HARDCODED_RESISTANCE_GROUP_COUNT = namespace["OLD_HARDCODED_RESISTANCE_GROUP_COUNT"]
MANUAL_RU_ALIASES = namespace["MANUAL_RU_ALIASES"]
get_resistance_lookup_diagnostics = namespace["get_resistance_lookup_diagnostics"]


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


PROTECT_COMBI_SOURCE_COMPOSITION = (
    "(48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + "
    "37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + "
    "55 г/л Флудиоксонил + 37,5 г/л Тебуконазол + "
    "48 г/л Пираклостробин - протиоконазол + 55 г/л Флудиоксонил + "
    "37,5 г/л Тебуконазол + 48 г/л Пираклостробин - протиоконазол + "
    "55 г/л Флудиоксонил + 37,5 г/л Тебуконазол)"
)


class ActiveSubstanceParsingRegressionTest(unittest.TestCase):
    def assert_substance_names(self, raw, expected_names):
        substances = parse_active_substances(raw)

        self.assertEqual([substance["name"] for substance in substances], expected_names)
        return substances

    def test_protect_combi_source_composition_deduplicates_repeated_components(self):
        substances = self.assert_substance_names(
            PROTECT_COMBI_SOURCE_COMPOSITION,
            ["Пираклостробин", "протиоконазол", "Флудиоксонил", "Тебуконазол"],
        )

        self.assertEqual(len(substances), 4)
        self.assertEqual([substance["concentration"] for substance in substances], [48, None, 55, 37.5])
        self.assertEqual([substance["unit"] for substance in substances], ["г/л", None, "г/л", "г/л"])
        self.assertTrue(substances[1]["concentration_unresolved"])

    def test_protect_combi_does_not_parse_unrelated_record_fragments(self):
        unrelated_fragments = [
            "СЭ",
            "ООО «Агро Эксперт Груп» ОГРН 1027708006996",
            "Пшеница озимая",
            "Пыльная головня, фузариозная снежная плесень",
            "Предпосевная обработка семян с увлажнением перед посевом",
            "Расход рабочей жидкости - 10 л/т",
            "178-02-4527-1",
            "24.04.2024",
        ]

        substances = parse_active_substances(PROTECT_COMBI_SOURCE_COMPOSITION)
        parsed_names = " | ".join(substance["name"] for substance in substances)

        for fragment in unrelated_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, parsed_names)

    def test_duplicate_registration_rows_do_not_duplicate_active_substances(self):
        substances = self.assert_substance_names(
            [PROTECT_COMBI_SOURCE_COMPOSITION, PROTECT_COMBI_SOURCE_COMPOSITION],
            ["Пираклостробин", "протиоконазол", "Флудиоксонил", "Тебуконазол"],
        )

        self.assertEqual(len(substances), 4)

    def test_joined_real_substances_are_split_without_fake_concentration(self):
        substances = self.assert_substance_names(
            "(48 г/л Пираклостробин - протиоконазол)",
            ["Пираклостробин", "протиоконазол"],
        )

        self.assertEqual(substances[0]["concentration"], 48)
        self.assertEqual(substances[0]["unit"], "г/л")
        self.assertIsNone(substances[1]["concentration"])
        self.assertIsNone(substances[1]["unit"])
        self.assertTrue(substances[1]["concentration_unresolved"])

    def test_hyphenated_single_substance_is_not_split(self):
        substances = self.assert_substance_names(
            "(225 г/л Тиофанат - метил + 25 г/л Пираклостробин)",
            ["Тиофанат-метил", "Пираклостробин"],
        )

        self.assertEqual([substance["concentration"] for substance in substances], [225, 25])

    def test_scientific_multiplication_sign_is_not_component_separator(self):
        raw = "2,5×10⁹ КОЕ/Мл Bacillus subtilis, штаммВ-2918 + 2,5×10⁹ КОЕ/Мл Bacillus amyloliquefaciens"

        self.assertEqual(parse_active_substances(raw), [])
        warnings = validate_active_substance_composition(raw, [], "fungicide")

        self.assertNotIn("repeated_fragment", composition_warning_codes(warnings))

    def test_harmless_dash_variant_does_not_create_malformed_warning(self):
        raw = "(23 г/л Пиноксаден + 23 г/л феноксапроп-П-этил + 6 г/л антидот – клоквинтосет-мексил)"
        parsed = parse_active_substances(raw)
        warnings = validate_active_substance_composition(raw, parsed, "herbicide")

        self.assertEqual(len(parsed), 3)
        self.assertNotIn("malformed_delimiters", composition_warning_codes(warnings))

    def test_broken_parentheses_still_create_malformed_warning(self):
        raw = "(90 г/л Клопиралид (2-этилгексиловый эфир)"
        parsed = parse_active_substances(raw)
        warnings = validate_active_substance_composition(raw, parsed, "herbicide")

        self.assertIn("malformed_delimiters", composition_warning_codes(warnings))

    def test_normal_multi_component_seed_treatment_still_parses(self):
        substances = self.assert_substance_names(
            "(25 г/л флудиоксонил + 10 г/л имидаклоприд + 15 г/л тебуконазол)",
            ["флудиоксонил", "имидаклоприд", "тебуконазол"],
        )

        self.assertEqual([substance["concentration"] for substance in substances], [25, 10, 15])

    def test_percent_concentration_still_parses(self):
        substances = self.assert_substance_names("(10 % имидаклоприд)", ["имидаклоприд"])

        self.assertEqual(substances[0]["concentration"], 10)
        self.assertEqual(substances[0]["unit"], "%")

    def test_exact_duplicate_substances_with_identical_concentration_are_deduplicated(self):
        substances = self.assert_substance_names(
            "(250 г/л тебуконазол + 250 г/л тебуконазол)",
            ["тебуконазол"],
        )

        self.assertEqual(len(substances), 1)

    def test_unknown_spaced_hyphen_text_is_not_split_automatically(self):
        substances = self.assert_substance_names(
            "(100 г/л неизвестное - странное)",
            ["неизвестное - странное"],
        )

        self.assertEqual(substances[0]["concentration"], 100)
        self.assertNotIn("concentration_unresolved", substances[0])

    def test_composition_validation_flags_non_substance_text(self):
        parsed = parse_active_substances("(10 г/л Норма расхода 1 л/га)")
        warnings = validate_active_substance_composition("(10 г/л Норма расхода 1 л/га)", parsed, "herbicide")

        self.assertIn("suspicious_non_substance_text", composition_warning_codes(warnings))

    def test_composition_validation_flags_excessive_component_count(self):
        raw = "(1 г/л a + 2 г/л b + 3 г/л c + 4 г/л d + 5 г/л e + 6 г/л f)"
        parsed = parse_active_substances(raw)
        warnings = validate_active_substance_composition(raw, parsed, "fungicide")

        self.assertIn("excessive_component_count", composition_warning_codes(warnings))

    def test_composition_validation_flags_conflicting_concentrations(self):
        raw = "(100 г/л тебуконазол + 200 г/л тебуконазол)"
        parsed = parse_active_substances(raw)
        warnings = validate_active_substance_composition(raw, parsed, "fungicide")

        self.assertIn("conflicting_concentrations", composition_warning_codes(warnings))

    def test_composition_validation_flags_protect_combi_warnings(self):
        parsed = parse_active_substances(PROTECT_COMBI_SOURCE_COMPOSITION)
        warnings = validate_active_substance_composition(PROTECT_COMBI_SOURCE_COMPOSITION, parsed, "seed-treatment")
        codes = composition_warning_codes(warnings)

        self.assertEqual(len(parsed), 4)
        self.assertIn("repeated_fragment", codes)
        self.assertIn("joined_known_substances", codes)
        self.assertIn("unresolved_concentration", codes)

    def test_normal_herbicide_composition_still_parses(self):
        substances = self.assert_substance_names("(750 г/кг трибенурон-метил)", ["трибенурон-метил"])

        self.assertEqual(substances[0]["unit"], "г/кг")

    def test_normal_fungicide_composition_still_parses(self):
        substances = self.assert_substance_names("(250 г/л тебуконазол)", ["тебуконазол"])

        self.assertEqual(substances[0]["concentration"], 250)

    def test_normal_insecticide_composition_still_parses(self):
        substances = self.assert_substance_names("(200 г/л имидаклоприд)", ["имидаклоприд"])

        self.assertEqual(substances[0]["unit"], "г/л")

    def test_herbicide_fungicide_and_insecticide_parsing_is_unchanged(self):
        cases = [
            ("(750 г/кг трибенурон-метил)", ["трибенурон-метил"]),
            ("(250 г/л тебуконазол)", ["тебуконазол"]),
            ("(200 г/л имидаклоприд)", ["имидаклоприд"]),
        ]

        for raw, expected_names in cases:
            with self.subTest(raw=raw):
                self.assert_substance_names(raw, expected_names)


class ResistanceGroupDataFileTest(unittest.TestCase):
    def test_correct_resistance_groups_file_exists_and_wrong_path_is_removed(self):
        repo_root = SERVER_SOURCE.parents[1]

        self.assertTrue((repo_root / "backend" / "data" / "resistance_groups.json").exists())
        self.assertFalse((repo_root / "backend" / "backend" / "data" / "resistance_groups.json").exists())

    def test_resistance_groups_json_loads_and_has_more_records_than_old_mapping(self):
        loaded = load_resistance_groups(SERVER_SOURCE.parent / "data" / "resistance_groups.json")

        self.assertGreater(loaded["record_count"], OLD_HARDCODED_RESISTANCE_GROUP_COUNT)
        self.assertEqual(loaded["record_count"], len(loaded["records"]))
        self.assertGreater(len(loaded["indexes"]["fungicide"]), 0)
        self.assertGreater(len(loaded["indexes"]["herbicide"]), 0)
        self.assertGreater(len(loaded["indexes"]["insecticide"]), 0)

    def test_russian_alias_arrays_exist_and_are_indexed(self):
        loaded = load_resistance_groups(SERVER_SOURCE.parent / "data" / "resistance_groups.json")
        nicosulfuron = next(
            record for record in loaded["records"]
            if record.get("active_ingredient_key") == "nicosulfuron"
        )

        self.assertIsInstance(nicosulfuron.get("active_ingredient_ru_aliases"), list)
        self.assertIn("никосульфурон", nicosulfuron["active_ingredient_ru_aliases"])
        self.assertIn("никосульфурон", loaded["indexes"]["herbicide"])
        self.assertEqual(loaded["indexes"]["herbicide"]["никосульфурон"]["system"], "HRAC")


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

    def test_api_endpoint_urls_are_unchanged(self):
        source = SERVER_SOURCE.read_text(encoding="utf-8")
        actual_paths = re.findall(r'@api_router\.(?:get|post|put|delete|patch)\("([^"]+)"', source)

        self.assertEqual(actual_paths, [
            "/health",
            "/admin/import-excel",
            "/herbicides/search",
            "/herbicides/{product_key:path}",
            "/herbicides/compare",
            "/herbicides/compare-advanced",
            "/admin/import-insecticides",
            "/insecticides/search",
            "/insecticides/{product_key:path}",
            "/insecticides/compare-advanced",
            "/admin/import-fungicides",
            "/fungicides/search",
            "/fungicides/{product_key:path}",
            "/fungicides/compare-advanced",
            "/admin/import-seed-treatments",
            "/seed-treatments/search",
            "/seed-treatments/{product_key:path}",
            "/seed-treatments/compare-advanced",
            "/herbicides/crops",
            "/herbicides/harmful-objects",
            "/insecticides/crops",
            "/insecticides/harmful-objects",
            "/fungicides/crops",
            "/fungicides/harmful-objects",
            "/seed-treatments/crops",
            "/seed-treatments/harmful-objects",
            "/stats",
        ])


class ResistanceGroupHelpersTest(unittest.TestCase):
    def test_known_hrac_json_ru_aliases_resolve(self):
        expected = {
            "никосульфурон": "2",
            "тифенсульфурон": "2",
            "трифлусульфурон": "2",
            "глифосат": "9",
        }

        for alias, group_code in expected.items():
            with self.subTest(alias=alias):
                group = get_resistance_group(alias, "herbicide")
                self.assertEqual(group["system"], "HRAC")
                self.assertEqual(group["group"], group_code)

    def test_known_frac_russian_names_resolve(self):
        expected = {
            "пираклостробин": "11",
            "азоксистробин": "11",
            "карбендазим": "1",
            "тебуконазол": "3",
        }

        for alias, group_code in expected.items():
            with self.subTest(alias=alias):
                group = get_resistance_group(alias, "fungicide")
                self.assertEqual(group["system"], "FRAC")
                self.assertEqual(group["group"], group_code)

    def test_known_irac_json_ru_aliases_resolve(self):
        expected = {
            "ацетамиприд": "4A",
            "диметоат": "1B",
            "лямбда-цигалотрин": "3A",
        }

        for alias, group_code in expected.items():
            with self.subTest(alias=alias):
                group = get_resistance_group(alias, "insecticide")
                self.assertEqual(group["system"], "IRAC")
                self.assertEqual(group["group"], group_code)

    def test_json_alias_case_variants_resolve_to_same_group(self):
        lowercase_group = get_resistance_group("никосульфурон", "herbicide")

        self.assertEqual(get_resistance_group("Никосульфурон", "herbicide"), lowercase_group)
        self.assertEqual(get_resistance_group("НИКОСУЛЬФУРОН", "herbicide"), lowercase_group)

    def test_seed_treatment_uses_frac_before_irac_with_json_aliases(self):
        frac_group = get_resistance_group("пенфлуфен", "seed-treatment")
        irac_group = get_resistance_group("фипронил", "seed-treatment")

        self.assertEqual(frac_group["system"], "FRAC")
        self.assertEqual(frac_group["group"], "7")
        self.assertEqual(irac_group["system"], "IRAC")
        self.assertEqual(irac_group["group"], "2B")

    def test_known_hrac_russian_manual_alias_resolves_with_parser_extra_words(self):
        group = get_resistance_group("Глифосат кислоты", "herbicide")

        self.assertEqual(group["system"], "HRAC")
        self.assertEqual(group["group"], "9")
        self.assertIn("EPSPS", group["name"])
        self.assertEqual(group["effect_summary"], "Системное листовое, неселективное.")

    def test_known_irac_russian_manual_alias_resolves_correctly(self):
        group = get_resistance_group("имидаклоприд", "insecticide")

        self.assertEqual(group["system"], "IRAC")
        self.assertEqual(group["group"], "4A")
        self.assertIn("acetylcholine receptor", group["name"])

    def test_pyraclostrobin_alias_is_case_insensitive_for_frac_lookup(self):
        lowercase_group = get_resistance_group("пираклостробин", "fungicide")
        titlecase_group = get_resistance_group("Пираклостробин", "fungicide")
        uppercase_group = get_resistance_group("ПИРАКЛОСТРОБИН", "fungicide")
        mixed_group = get_resistance_group("ПиРаКлОсТрОбИн", "fungicide")

        self.assertEqual(lowercase_group["system"], "FRAC")
        self.assertEqual(lowercase_group["group"], "11")
        self.assertEqual(titlecase_group, lowercase_group)
        self.assertEqual(uppercase_group, lowercase_group)
        self.assertEqual(mixed_group, lowercase_group)

    def test_resistance_lookup_normalizes_spaces_nbsp_punctuation_and_hyphens(self):
        expected = get_resistance_group("лямбда-цигалотрин", "insecticide")

        self.assertEqual(get_resistance_group("  ЛЯМБДА\u00a0—  ЦИГАЛОТРИН. ", "insecticide"), expected)
        self.assertEqual(get_resistance_group("лямбда цигалотрин", "insecticide"), expected)

    def test_acetamiprid_russian_manual_alias_resolves_to_irac_4a(self):
        group = get_resistance_group("ацетамиприд", "insecticide")

        self.assertEqual(group["system"], "IRAC")
        self.assertEqual(group["group"], "4A")
        self.assertIn("acetylcholine receptor", group["name"])

    def test_dimethoate_russian_manual_alias_resolves_to_irac_1b(self):
        group = get_resistance_group("диметоат", "insecticide")

        self.assertEqual(group["system"], "IRAC")
        self.assertEqual(group["group"], "1B")
        self.assertIn("Acetylcholinesterase", group["name"])

    def test_existing_lambda_cyhalothrin_alias_still_resolves_to_irac_3a(self):
        group = get_resistance_group("лямбда-цигалотрин", "insecticide")

        self.assertEqual(group["system"], "IRAC")
        self.assertEqual(group["group"], "3A")
        self.assertIn("Sodium channel", group["name"])

    def test_lambda_cyhalothrin_case_variants_resolve_to_same_irac_group(self):
        lowercase_group = get_resistance_group("лямбда-цигалотрин", "insecticide")
        titlecase_group = get_resistance_group("Лямбда-цигалотрин", "insecticide")

        self.assertEqual(lowercase_group["system"], "IRAC")
        self.assertEqual(lowercase_group["group"], "3A")
        self.assertEqual(titlecase_group, lowercase_group)

    def test_glyphosate_case_variants_resolve_to_same_hrac_group(self):
        lowercase_group = get_resistance_group("глифосат", "herbicide")
        titlecase_group = get_resistance_group("Глифосат", "herbicide")

        self.assertEqual(lowercase_group["system"], "HRAC")
        self.assertEqual(lowercase_group["group"], "9")
        self.assertEqual(titlecase_group, lowercase_group)

    def test_high_confidence_herbicide_alias_from_audit_resolves_to_hrac(self):
        group = get_resistance_group("Изоксафлютол", "herbicide")

        self.assertEqual(group["system"], "HRAC")
        self.assertEqual(group["group"], "27")
        self.assertIn("HPPD", group["name"])

    def test_high_confidence_fungicide_alias_from_audit_resolves_to_frac(self):
        group = get_resistance_group("Пидифлуметофен", "fungicide")

        self.assertEqual(group["system"], "FRAC")
        self.assertEqual(group["group"], "7")
        self.assertEqual(group["name"], "SDHI-fungicides")

    def test_high_confidence_insecticide_alias_from_audit_resolves_to_irac(self):
        group = get_resistance_group("Бифентрин", "insecticide")

        self.assertEqual(group["system"], "IRAC")
        self.assertEqual(group["group"], "3A")
        self.assertIn("Sodium channel", group["name"])

    def test_insecticide_aliases_do_not_resolve_in_herbicide_lookup(self):
        group = get_resistance_group("ацетамиприд", "herbicide")

        self.assertIsNone(group["system"])
        self.assertIsNone(group["group"])
        self.assertEqual(group["name"], "группа не определена")

    def test_unknown_insecticide_still_returns_clear_unknown_name(self):
        group = get_resistance_group("неизвестный инсектицид", "insecticide")

        self.assertIsNone(group["system"])
        self.assertIsNone(group["group"])
        self.assertEqual(group["name"], "группа не определена")

    def test_unknown_substance_still_returns_group_not_defined(self):
        group = get_resistance_group("НЕИЗВЕСТНОЕ вещество", "fungicide")

        self.assertIsNone(group["system"])
        self.assertIsNone(group["group"])
        self.assertEqual(group["name"], "группа не определена")

    def test_resistance_lookup_diagnostics_reports_unresolved_names_without_failing(self):
        diagnostics = get_resistance_lookup_diagnostics(
            ["ацетамиприд", "диметоат", "неизвестный инсектицид"],
            "insecticide",
        )

        self.assertEqual(diagnostics["pesticide_type"], "insecticide")
        self.assertEqual(diagnostics["unresolved"], ["неизвестный инсектицид"])
        self.assertEqual(diagnostics["checked"][0]["group"], "4A")
        self.assertEqual(diagnostics["checked"][1]["group"], "1B")
        self.assertFalse(diagnostics["checked"][2]["resolved"])

    def test_manual_russian_aliases_are_preserved_for_known_app_substances(self):
        existing_aliases = {
            "глифосат", "трибенурон-метил", "метсульфурон-метил", "имазамокс",
            "имазетапир", "клетодим", "хизалофоп-п-этил", "2,4-д", "дикамба",
            "клопиралид", "мезотрион", "метрибузин", "имидаклоприд", "тиаметоксам",
            "клотианидин", "лямбда-цигалотрин", "альфа-циперметрин", "дельтаметрин",
            "хлорантранилипрол", "абамектин", "ацетамиприд", "диметоат",
            "карбендазим", "тебуконазол",
            "дифеноконазол", "азоксистробин", "пираклостробин",
            "флудиоксонил", "металаксил-м",
        }
        audit_aliases = {
            "изоксафлютол", "карфентразон-этил", "пендиметалин", "пиноксаден",
            "прометрин", "пропаквизафоп", "с-метолахлор", "темботрион",
            "тербутилазин", "флорасулам", "изопиразам", "пидифлуметофен",
            "фамоксадон", "фенамидон", "фенпропидин", "цифлуфенамид",
            "бифентрин", "зета-циперметрин", "индоксакарб", "малатион",
            "пиметрозин", "пиримифос-метил", "спиносад", "спиротетрамат",
            "фипронил", "хлорпирифос", "циантранилипрол", "циперметрин",
            "эмамектин бензоат", "эсфенвалерат", "пенфлуфен",
        }

        self.assertEqual(set(MANUAL_RU_ALIASES), existing_aliases | audit_aliases)

    def test_known_group_annotation_keeps_existing_fields_and_adds_effect_summary(self):
        annotated = annotate_substances_with_resistance(
            parse_active_substances("(250 г/л тебуконазол)"),
            "fungicide",
        )

        self.assertEqual(annotated[0]["resistance_system"], "FRAC")
        self.assertEqual(annotated[0]["resistance_group"], "3")
        self.assertEqual(annotated[0]["resistance_group_name"], "DMI-fungicides / SBI Class I")
        self.assertEqual(annotated[0]["effect_summary"], "C14-деметилаза CYP51")

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
        self.assertEqual(match["group_name"], "Inhibition of Acetolactate Synthase (ALS)")
        self.assertEqual(match["effect_summary"], "Системное; почвенное и/или листовое действие.")
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
        audit_fungicide_group = get_resistance_group("пенфлуфен", "seed-treatment")
        audit_insecticide_group = get_resistance_group("Фипронил", "seed-treatment")
        unknown_group = get_resistance_group("неизвестное вещество", "seed-treatment")

        self.assertEqual(fungicide_group["system"], "FRAC")
        self.assertEqual(fungicide_group["group"], "3")
        self.assertEqual(insecticide_group["system"], "IRAC")
        self.assertEqual(insecticide_group["group"], "4A")
        self.assertEqual(audit_fungicide_group["system"], "FRAC")
        self.assertEqual(audit_fungicide_group["group"], "7")
        self.assertEqual(audit_insecticide_group["system"], "IRAC")
        self.assertEqual(audit_insecticide_group["group"], "2B")
        self.assertEqual(unknown_group["name"], "группа не определена")

    def test_seed_treatment_lookup_is_case_insensitive(self):
        fungicide_lower = get_resistance_group("тебуконазол", "seed-treatment")
        fungicide_upper = get_resistance_group("ТЕБУКОНАЗОЛ", "seed-treatment")
        insecticide_lower = get_resistance_group("имидаклоприд", "seed-treatment")
        insecticide_upper = get_resistance_group("ИМИДАКЛОПРИД", "seed-treatment")

        self.assertEqual(fungicide_lower["system"], "FRAC")
        self.assertEqual(fungicide_upper, fungicide_lower)
        self.assertEqual(insecticide_lower["system"], "IRAC")
        self.assertEqual(insecticide_upper, insecticide_lower)

    def test_identical_substances_with_different_case_receive_same_group(self):
        left = annotate_substances_with_resistance(
            parse_active_substances("(100 г/л пираклостробин)"),
            "fungicide",
        )
        right = annotate_substances_with_resistance(
            parse_active_substances("(100 г/л ПИРАКЛОСТРОБИН)"),
            "fungicide",
        )

        analysis = build_resistance_group_analysis(left, right)

        self.assertTrue(analysis["identical_active_substance_sets"])
        self.assertEqual(left[0]["resistance_system"], "FRAC")
        self.assertEqual(left[0]["resistance_group"], "11")
        self.assertEqual(right[0]["resistance_group"], left[0]["resistance_group"])


class AdvancedCompareResponseTest(unittest.TestCase):
    def make_collection(self):
        return FakeCollection({
            "left": [
                {
                    "product_key": "left",
                    "product_name": "Препарат А",
                    "formulation": "КЭ",
                    "active_substances_raw": "(100 г/л дифеноконазол + 200 г/л азоксистробин)",
                    "registrant": "Левый регистрант",
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
                    "producer": "Правый производитель",
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

    def test_advanced_comparison_includes_display_manufacturer_for_both_products(self):
        response = self.compare()

        self.assertEqual(response["left"]["display_manufacturer"], "Левый регистрант")
        self.assertEqual(response["right"]["display_manufacturer"], "Правый производитель")

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

    def test_price_analysis_returns_cost_per_gram_for_unmatched_substance(self):
        response = self.compare(left_price=1200, right_price=900)
        left_costs = response["price_analysis"]["left_substances_cost"]

        unmatched_cost = next(
            item for item in left_costs
            if item["substance_name"] == "азоксистробин"
        )

        self.assertEqual(unmatched_cost["grams_per_ha"], 200.0)
        self.assertGreater(unmatched_cost["estimated_cost_share_per_ha"], 0)
        self.assertGreater(unmatched_cost["estimated_cost_per_gram"], 0)
        self.assertEqual(unmatched_cost["rate_unit"], None)

    def test_price_analysis_does_not_return_fake_substance_cost_without_price(self):
        response = self.compare(left_price=1200, right_price=None)

        self.assertEqual(response["price_analysis"]["right_substances_cost"], [])
        self.assertFalse(
            any(item["side"] == "right" for item in response["price_analysis"]["substances_cost"])
        )

    def test_price_analysis_does_not_return_fake_cost_for_unresolved_concentration(self):
        collection = FakeCollection({
            "left": [
                {
                    "product_key": "left",
                    "product_name": "Протект Комби",
                    "formulation": "КС",
                    "active_substances_raw": PROTECT_COMBI_SOURCE_COMPOSITION,
                    "registration_status": "Действует",
                    "rate_raw": "1,0 л/т",
                    "crop": "пшеница",
                }
            ],
            "right": [
                {
                    "product_key": "right",
                    "product_name": "Обычный фунгицид",
                    "formulation": "КС",
                    "active_substances_raw": "(250 г/л тебуконазол)",
                    "registration_status": "Действует",
                    "rate_raw": "1,0 л/т",
                    "crop": "пшеница",
                }
            ],
        })
        request = SimpleNamespace(
            left_key="left",
            right_key="right",
            left_price=1000,
            right_price=1000,
            left_rate=None,
            right_rate=None,
            crop=None,
        )

        response = asyncio.run(build_advanced_compare_response(request, collection, "seed-treatment"))
        left_costs = response["price_analysis"]["left_substances_cost"]

        self.assertFalse(any(item["substance_name"] == "протиоконазол" for item in left_costs))
        self.assertTrue(response["left"]["has_composition_warning"])
        self.assertIn("unresolved_concentration", composition_warning_codes(response["left"]["composition_warnings"]))

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
