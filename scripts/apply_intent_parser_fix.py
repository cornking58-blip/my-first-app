from pathlib import Path

PRODUCT_CATALOG = Path("backend/product_catalog.py")
STRICT_AI = Path("backend/strict_catalog_ai.py")
TESTS = Path("tests/test_supabase_strict_catalog.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


catalog = PRODUCT_CATALOG.read_text(encoding="utf-8")
catalog = replace_once(
    catalog,
    '''    return any(marker in normalized for marker in (\n        "выпиши все",\n        "покажи все",\n        "список препаратов",\n        "все препараты",\n        "полный список",\n        "каталог",\n    ))\n''',
    '''    return any(marker in normalized for marker in (\n        "выпиши все",\n        "выпиши",\n        "покажи все",\n        "покажи",\n        "перечисли",\n        "дай список",\n        "список препаратов",\n        "все препараты",\n        "полный список",\n        "каталог",\n    ))\n''',
    "catalog command markers",
)
PRODUCT_CATALOG.write_text(catalog, encoding="utf-8")


strict = STRICT_AI.read_text(encoding="utf-8")
strict = strict.replace(
    '''        extract_comparison_names,\n        find_mongo_product,\n''',
    '''        extract_comparison_names,\n        is_catalog_request,\n        find_mongo_product,\n''',
)
if strict.count("        is_catalog_request,\n") != 2:
    raise RuntimeError("is_catalog_request imports were not added to both import branches")

strict = replace_once(
    strict,
    '''    value = re.sub(\n        r"\\s+(?:тогда\\s+)?(?:для\\s+чего|зачем|как\\s+работает|что\\s+делает|какую\\s+роль\\s+играет)\\s*$",\n        "",\n        value,\n        flags=re.IGNORECASE,\n    )\n    return value.strip(" \\t\\r\\n«»\\\"'.,!?—–-")\n''',
    '''    value = re.sub(\n        r"\\s+(?:тогда\\s+)?(?:для\\s+чего|зачем|как\\s+работает|что\\s+делает|какую\\s+роль\\s+играет)\\s*$",\n        "",\n        value,\n        flags=re.IGNORECASE,\n    )\n    value = re.sub(\n        r"^(?:(?:расскажи|напиши|покажи)\\s+(?:о|про)\\s+|дай\\s+информацию\\s+(?:о|про)\\s+)",\n        "",\n        value,\n        flags=re.IGNORECASE,\n    )\n    value = re.sub(\n        r"^(?:препарат(?:е|а|ом)?|торгов(?:ое|ого)\\s+названи(?:е|я)|фунгицид(?:е|а|ом)?|гербицид(?:е|а|ом)?|инсектицид(?:е|а|ом)?|протравител(?:е|я|ем)?)\\s+",\n        "",\n        value,\n        flags=re.IGNORECASE,\n    )\n    return value.strip(" \\t\\r\\n«»\\\"'.,!?—–-")\n''',
    "candidate prefixes",
)

strict = replace_once(
    strict,
    '''    candidate = extract_single_product_candidate(message)\n    if candidate:\n''',
    '''    if is_catalog_request(message):\n        catalog_context = await build_catalog_ai_context(db, message)\n        if catalog_context.get("intent") == "manufacturer_catalog":\n            catalog_context["catalog_lookup_attempted"] = True\n            catalog_context["allow_web_fallback"] = False\n            return catalog_context\n\n    candidate = extract_single_product_candidate(message)\n    if candidate:\n''',
    "catalog intent priority",
)
STRICT_AI.write_text(strict, encoding="utf-8")


tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''from backend.strict_catalog_ai import (\n    build_strict_direct_answer,\n    extract_single_product_candidate,\n    select_catalog_substance_matches,\n    select_unambiguous_catalog_match,\n)\n''',
    '''from backend.product_catalog import detect_group, extract_manufacturer, is_catalog_request\nfrom backend.strict_catalog_ai import (\n    build_strict_direct_answer,\n    extract_single_product_candidate,\n    select_catalog_substance_matches,\n    select_unambiguous_catalog_match,\n)\n''',
    "test imports",
)
tests = replace_once(
    tests,
    '''ROOT = Path(__file__).resolve().parents[1]\nSERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")\nCATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")\n''',
    '''ROOT = Path(__file__).resolve().parents[1]\nSERVER = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")\nCATALOG = (ROOT / "backend" / "product_catalog.py").read_text(encoding="utf-8")\nSTRICT_AI_SOURCE = (ROOT / "backend" / "strict_catalog_ai.py").read_text(encoding="utf-8")\n''',
    "strict source fixture",
)
tests = replace_once(
    tests,
    '''    def test_active_substance_follow_up_is_cleaned(self):\n''',
    '''    def test_manufacturer_catalog_command_is_recognized_before_product_lookup(self):\n        message = "выпиши протравители щёлковоагрохим"\n        self.assertTrue(is_catalog_request(message))\n        self.assertEqual(detect_group(message), "seed_treatment")\n        self.assertEqual(extract_manufacturer(message), "щёлковоагрохим")\n        self.assertLess(\n            STRICT_AI_SOURCE.index("if is_catalog_request(message):"),\n            STRICT_AI_SOURCE.index("candidate = extract_single_product_candidate(message)"),\n        )\n\n    def test_product_prefix_is_removed_before_lookup(self):\n        self.assertEqual(extract_single_product_candidate("препарат Цепелин"), "Цепелин")\n        self.assertEqual(\n            extract_single_product_candidate("расскажи про препарат Цепелин"),\n            "Цепелин",\n        )\n\n    def test_active_substance_follow_up_is_cleaned(self):\n''',
    "new parser tests",
)
TESTS.write_text(tests, encoding="utf-8")
