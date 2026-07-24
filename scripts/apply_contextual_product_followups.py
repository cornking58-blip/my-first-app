from pathlib import Path

STRICT = Path("backend/strict_catalog_ai.py")
TESTS = Path("tests/test_supabase_strict_catalog.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


strict = STRICT.read_text(encoding="utf-8")

strict = replace_once(
    strict,
    '''async def find_catalog_product(db: Any, product_name: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:\n    mode = catalog_backend_mode()\n\n    if mode in {"supabase", "auto"} and supabase_configured():\n        results = await search_supabase_products(query=product_name, limit=12)\n    elif mode == "supabase":\n        return None, []\n    else:\n        results = await search_catalog_products(db, query=product_name, limit=12)\n\n''',
    '''def is_short_contextual_fragment(value: str) -> bool:\n    candidate = _clean_candidate(value)\n    normalized = canonical_product_name(candidate)\n    return bool(\n        normalized\n        and 1 <= len(candidate.split()) <= 2\n        and 3 <= len(normalized) <= 32\n        and not is_catalog_request(value)\n    )\n\n\nasync def search_catalog_candidate_products(\n    db: Any,\n    query: str,\n    limit: int = 12,\n) -> List[Dict[str, Any]]:\n    mode = catalog_backend_mode()\n    if mode in {"supabase", "auto"} and supabase_configured():\n        return await search_supabase_products(query=query, limit=limit)\n    if mode == "supabase":\n        return []\n    return await search_catalog_products(db, query=query, limit=limit)\n\n\nasync def find_catalog_product(db: Any, product_name: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:\n    results = await search_catalog_candidate_products(db, product_name, limit=12)\n\n''',
    "candidate search helper",
)

strict = replace_once(
    strict,
    '''        substance_products = await find_catalog_substance(db, candidate)\n        if substance_products:\n''',
    '''        if is_short_contextual_fragment(candidate) and suggestions:\n            candidate_products = await search_catalog_candidate_products(db, candidate, limit=12)\n            if candidate_products:\n                return {\n                    "source": "Единый справочник пестицидов РФ",\n                    "intent": "contextual_product_followup",\n                    "entity_type": "product_fragment",\n                    "requested_fragment": candidate,\n                    "products": candidate_products,\n                    "suggestions": suggestions,\n                    "verified_from_catalog": True,\n                    "catalog_lookup_attempted": True,\n                    "allow_web_fallback": False,\n                    "notice": (\n                        "Короткое уточнение найдено в названиях нескольких препаратов. "\n                        "Используй предыдущие сообщения диалога, чтобы выбрать только "\n                        "однозначно подходящее полное название."\n                    ),\n                    "answer_instruction": (\n                        "Свяжи короткий фрагмент с предыдущей репликой пользователя. "\n                        "Например, после «препарат Амистар» слово «Голд» означает "\n                        "«Амистар Голд», но только если такой вариант есть среди переданных "\n                        "кандидатов. Если контекст не даёт одного точного варианта, задай "\n                        "один короткий уточняющий вопрос. Не объявляй фрагмент новым препаратом."\n                    ),\n                }\n\n        substance_products = await find_catalog_substance(db, candidate)\n        if substance_products:\n''',
    "contextual follow-up block",
)

STRICT.write_text(strict, encoding="utf-8")


tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    extract_single_product_candidate,\n    select_catalog_substance_matches,\n''',
    '''    extract_single_product_candidate,\n    is_short_contextual_fragment,\n    select_catalog_substance_matches,\n''',
    "test import",
)
tests = replace_once(
    tests,
    '''    def test_active_substance_follow_up_is_cleaned(self):\n''',
    '''    def test_short_product_suffix_is_treated_as_contextual_fragment(self):\n        self.assertTrue(is_short_contextual_fragment("Голд"))\n        self.assertTrue(is_short_contextual_fragment("Амистар Голд"))\n        self.assertFalse(is_short_contextual_fragment("выпиши препараты Голд"))\n        self.assertIn("contextual_product_followup", STRICT_AI_SOURCE)\n        self.assertIn("Не объявляй фрагмент новым препаратом", STRICT_AI_SOURCE)\n\n    def test_active_substance_follow_up_is_cleaned(self):\n''',
    "contextual tests",
)
TESTS.write_text(tests, encoding="utf-8")
