from pathlib import Path


STRICT_PATH = Path("backend/strict_catalog_ai.py")
TEST_PATH = Path("tests/test_supabase_strict_catalog.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


strict = STRICT_PATH.read_text(encoding="utf-8")

strict = replace_once(
    strict,
    '''    value = re.sub(r"\\s+(?:что\\s+думаешь|что\\s+скажешь).*$", "", value, flags=re.IGNORECASE)\n    return value.strip(" \\t\\r\\n«»\\\"'.,!?—–-")\n''',
    '''    value = re.sub(r"\\s+(?:что\\s+думаешь|что\\s+скажешь).*$", "", value, flags=re.IGNORECASE)\n    value = re.sub(\n        r"\\s+(?:тогда\\s+)?(?:для\\s+чего|зачем|как\\s+работает|что\\s+делает|какую\\s+роль\\s+играет)\\s*$",\n        "",\n        value,\n        flags=re.IGNORECASE,\n    )\n    return value.strip(" \\t\\r\\n«»\\\"'.,!?—–-")\n''',
    "clean follow-up entity phrase",
)

marker = '''    return close_matches[0] if len(close_matches) == 1 else None\n\n\nasync def get_supabase_product'''
insert = '''    return close_matches[0] if len(close_matches) == 1 else None\n\n\ndef _normalize_substance_text(value: Any) -> str:\n    text = str(value or "").casefold().replace("ё", "е")\n    text = re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.IGNORECASE)\n    return re.sub(r"\\s+", " ", text).strip()\n\n\ndef _composition_contains_substance(composition: Any, substance_name: str) -> bool:\n    candidate = _normalize_substance_text(substance_name).replace(" ", "")\n    composition_text = _normalize_substance_text(composition).replace(" ", "")\n    return bool(len(candidate) >= 4 and candidate in composition_text)\n\n\ndef select_catalog_substance_matches(\n    results: List[Dict[str, Any]],\n    substance_name: str,\n) -> List[Dict[str, Any]]:\n    matches: List[Dict[str, Any]] = []\n    seen = set()\n    for item in results:\n        if not _composition_contains_substance(item.get("active_substances_raw"), substance_name):\n            continue\n        key = (\n            str(item.get("product_group") or ""),\n            str(item.get("product_key") or item.get("product_name") or ""),\n        )\n        if key in seen:\n            continue\n        seen.add(key)\n        matches.append(dict(item))\n    return matches\n\n\nasync def find_catalog_substance(db: Any, substance_name: str) -> List[Dict[str, Any]]:\n    mode = catalog_backend_mode()\n    if mode in {"supabase", "auto"} and supabase_configured():\n        results = await search_supabase_products(query=substance_name, limit=50)\n    elif mode == "supabase":\n        return []\n    else:\n        results = await search_catalog_products(db, query=substance_name, limit=50)\n    return select_catalog_substance_matches(results, substance_name)[:20]\n\n\nasync def get_supabase_product'''
strict = replace_once(strict, marker, insert, "active substance helpers")

old_candidate_block = '''    candidate = extract_single_product_candidate(message)\n    if candidate:\n        product, suggestions = await find_catalog_product(db, candidate)\n        if product:\n            return {\n                "source": "Единый справочник пестицидов РФ",\n                "intent": "single_product",\n                "requested_product": candidate,\n                "products": [product],\n                "verified_from_catalog": True,\n                "catalog_lookup_attempted": True,\n                "allow_web_fallback": False,\n                "notice": "Препарат найден в каталоге. Используй только переданные данные.",\n            }\n        return {\n            "source": "Единый справочник пестицидов РФ",\n            "intent": "product_not_found",\n            "requested_product": candidate,\n            "missing_products": [candidate],\n            "products": [],\n            "suggestions": suggestions,\n            "verified_from_catalog": False,\n            "catalog_lookup_attempted": True,\n            "allow_web_fallback": False,\n        }\n'''
new_candidate_block = '''    candidate = extract_single_product_candidate(message)\n    if candidate:\n        product, suggestions = await find_catalog_product(db, candidate)\n        if product:\n            return {\n                "source": "Единый справочник пестицидов РФ",\n                "intent": "single_product",\n                "entity_type": "product",\n                "requested_product": candidate,\n                "products": [product],\n                "verified_from_catalog": True,\n                "catalog_lookup_attempted": True,\n                "allow_web_fallback": False,\n                "notice": "Препарат найден в каталоге. Используй только переданные данные.",\n            }\n\n        substance_products = await find_catalog_substance(db, candidate)\n        if substance_products:\n            return {\n                "source": "Единый справочник пестицидов РФ",\n                "intent": "active_substance",\n                "entity_type": "active_substance",\n                "requested_substance": candidate,\n                "products": substance_products,\n                "verified_from_catalog": True,\n                "catalog_lookup_attempted": True,\n                "allow_web_fallback": False,\n                "notice": (\n                    "Термин найден в составах препаратов как действующее вещество, "\n                    "а не как торговое название."\n                ),\n                "answer_instruction": (\n                    "Объясни роль действующего вещества простыми словами: механизм действия, "\n                    "зачем оно нужно в смеси, сильные и слабые стороны, практическое применение "\n                    "и риск резистентности. Учитывай предыдущие сообщения диалога."\n                ),\n            }\n\n        return {\n            "source": "Единый справочник пестицидов РФ",\n            "intent": "product_not_found",\n            "requested_product": candidate,\n            "missing_products": [candidate],\n            "products": [],\n            "suggestions": suggestions,\n            "verified_from_catalog": False,\n            "catalog_lookup_attempted": True,\n            "allow_web_fallback": False,\n        }\n'''
strict = replace_once(strict, old_candidate_block, new_candidate_block, "entity classification block")
STRICT_PATH.write_text(strict, encoding="utf-8")


tests = TEST_PATH.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    select_unambiguous_catalog_match,\n)\n''',
    '''    select_catalog_substance_matches,\n    select_unambiguous_catalog_match,\n)\n''',
    "test helper import",
)

tests = replace_once(
    tests,
    '''    def test_unique_one_letter_typo_can_resolve_to_product(self):\n''',
    '''    def test_active_substance_follow_up_is_cleaned(self):\n        self.assertEqual(\n            extract_single_product_candidate("а фамоксадон тогда для чего?"),\n            "фамоксадон",\n        )\n        self.assertEqual(\n            extract_single_product_candidate("а цимоксанил зачем?"),\n            "цимоксанил",\n        )\n\n    def test_active_substance_is_detected_in_composition(self):\n        products = [\n            {\n                "product_name": "Улис",\n                "product_key": "ulis",\n                "product_group": "fungicide",\n                "active_substances_raw": "Фамоксадон 225 г/кг + цимоксанил 300 г/кг",\n            },\n            {\n                "product_name": "Другой препарат",\n                "product_key": "other",\n                "product_group": "fungicide",\n                "active_substances_raw": "Тебуконазол 250 г/л",\n            },\n        ]\n        matches = select_catalog_substance_matches(products, "фамоксадон")\n        self.assertEqual([item["product_name"] for item in matches], ["Улис"])\n\n    def test_unique_one_letter_typo_can_resolve_to_product(self):\n''',
    "active substance tests",
)

TEST_PATH.write_text(tests, encoding="utf-8")
