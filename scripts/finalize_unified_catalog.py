from pathlib import Path


SERVER = Path("backend/server.py")
CATALOG = Path("backend/product_catalog.py")
TESTS = Path("tests/test_unified_catalog.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


catalog = CATALOG.read_text(encoding="utf-8")
catalog = catalog.replace("from urllib.parse import quote\n", "")

catalog = replace_once(
    catalog,
    '''def extract_comparison_names(message: str) -> Optional[Tuple[str, str]]:
    text = (message or "").strip()
    patterns = (
        r"чем\s+(.+?)\s+отличается\s+от\s+(.+?)(?:[?.!]|$)",
        r"сравни(?:ть)?\s+(.+?)\s+(?:с|и|против)\s+(.+?)(?:[?.!]|$)",
        r"(.+?)\s+против\s+(.+?)(?:[?.!]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            left = match.group(1).strip(" «»\\\".,!?-")
            right = match.group(2).strip(" «»\\\".,!?-")
            if left and right:
                return left, right
    return None
''',
    '''def _clean_product_phrase(value: str) -> str:
    value = (value or "").strip(" «»\\\".,!?-")
    value = re.split(
        r"\s+(?:на|по|для|при|против)\s+",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return value.strip(" «»\\\".,!?-")


def extract_comparison_names(message: str) -> Optional[Tuple[str, str]]:
    text = (message or "").strip()
    patterns = (
        r"чем\s+(.+?)\s+отличается\s+от\s+(.+?)(?:[?.!]|$)",
        r"сравни(?:ть)?\s+(.+?)\s+(?:с|и|против)\s+(.+?)(?:[?.!]|$)",
        r"(.+?)\s+против\s+(.+?)(?:[?.!]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            left = _clean_product_phrase(match.group(1))
            right = _clean_product_phrase(match.group(2))
            if left and right:
                return left, right
    return None
''',
    "comparison parser",
)

catalog = replace_once(
    catalog,
    '''def _regex(value: str, exact: bool = False) -> Dict[str, Any]:
    escaped = re.escape((value or "").strip())
    pattern = rf"^\s*{escaped}\s*$" if exact else escaped
    return {"$regex": pattern, "$options": "i"}
''',
    '''def _loose_pattern(value: str) -> str:
    compact = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "", (value or "").strip())
    if not compact:
        return ""
    separator = r"[\\s._&\\-]*"
    return separator.join(re.escape(char) for char in compact)


def _regex(value: str, exact: bool = False, loose: bool = False) -> Dict[str, Any]:
    pattern = _loose_pattern(value) if loose else re.escape((value or "").strip())
    if exact:
        pattern = rf"^\s*{pattern}\s*$"
    return {"$regex": pattern, "$options": "i"}


def _product_name_regex(value: str) -> Dict[str, Any]:
    normalized = normalize_text(value)
    compact = normalized.replace(" ", "")
    if re.search(r"[а-я]", compact, flags=re.IGNORECASE) and len(compact) >= 5:
        for ending in ("иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ом", "ем", "ах", "ях", "ов", "ев", "ей", "ам", "ям", "ою", "ею", "а", "я", "ы", "и", "у", "ю", "е", "о", "ь"):
            if compact.endswith(ending) and len(compact) - len(ending) >= 4:
                compact = compact[:-len(ending)]
                break
        pattern = _loose_pattern(compact) + r"[а-яё]*"
    else:
        pattern = _loose_pattern(normalized)
    return {"$regex": rf"^\s*{pattern}(?:\s*[,(/\\-].*)?\s*$", "$options": "i"}
''',
    "flexible regex helpers",
)

catalog = replace_once(
    catalog,
    '''    if manufacturer.strip():
        filters.append({
            "$or": [{field: _regex(manufacturer)} for field in MANUFACTURER_FIELDS]
        })
''',
    '''    if manufacturer.strip():
        filters.append({
            "$or": [{field: _regex(manufacturer, loose=True)} for field in MANUFACTURER_FIELDS]
        })
''',
    "manufacturer search",
)

catalog = replace_once(
    catalog,
    '''        row = await collection.find_one({"product_name": _regex(product_name, exact=True)})
''',
    '''        row = await collection.find_one({"product_name": _product_name_regex(product_name)})
''',
    "product lookup",
)

catalog = replace_once(
    catalog,
    '''def create_products_router(db: Any) -> APIRouter:
''',
    '''def build_direct_catalog_answer(context: Dict[str, Any]) -> Optional[str]:
    if context.get("intent") != "manufacturer_catalog":
        return None
    products = context.get("products")
    if not isinstance(products, list) or not products:
        return None

    group = str(context.get("product_group") or "")
    group_title = PRODUCT_GROUPS.get(group, {}).get("title", "Препараты")
    manufacturer = str(context.get("manufacturer") or "").strip()
    heading = f"{group_title} {manufacturer}".strip()
    lines = [f"{heading} — найдено {len(products)}:"]
    for product in products:
        name = str(product.get("product_name") or "Без названия").strip()
        composition = str(product.get("active_substances_raw") or "").strip()
        formulation = str(product.get("formulation") or "").strip()
        details = " · ".join(value for value in (composition, formulation) if value)
        lines.append(f"• {name}" + (f" — {details}" if details else ""))
    return "\n".join(lines)


def create_products_router(db: Any) -> APIRouter:
''',
    "direct catalog formatter",
)
CATALOG.write_text(catalog, encoding="utf-8")

server = SERVER.read_text(encoding="utf-8")
server = replace_once(
    server,
    "from product_catalog import build_catalog_ai_context, create_products_router\n",
    "from product_catalog import build_catalog_ai_context, build_direct_catalog_answer, create_products_router\n",
    "direct answer import",
)
server = replace_once(
    server,
    '''def context_has_verified_product_data(context: Dict[str, Any]) -> bool:
    if context.get("comparison"):
        return True
    products = context.get("products")
    return isinstance(products, list) and len(products) > 0
''',
    '''def context_has_verified_product_data(context: Dict[str, Any]) -> bool:
    if "verified_from_catalog" in context:
        return bool(context.get("verified_from_catalog"))
    if context.get("comparison"):
        return True
    products = context.get("products")
    return isinstance(products, list) and len(products) > 0
''',
    "verified catalog flag",
)
server = replace_once(
    server,
    '''        else:
            context = await build_ai_chat_context(chat, content)
            use_web_search = (
                should_use_ai_web_search(content)
                or should_force_product_web_search(content, context)
            )
            reservation = await reserve_ai_usage(current_user, use_web_search)
            model_messages = build_ai_model_messages(chat.get("messages", []), content, context)
            answer = await generate_ai_answer(
                model_messages,
                content,
                force_web_search=use_web_search,
            )
''',
    '''        else:
            context = await build_ai_chat_context(chat, content)
            direct_answer = build_direct_catalog_answer(context)
            if direct_answer:
                answer = direct_answer
            else:
                use_web_search = (
                    should_use_ai_web_search(content)
                    or should_force_product_web_search(content, context)
                )
                reservation = await reserve_ai_usage(current_user, use_web_search)
                model_messages = build_ai_model_messages(chat.get("messages", []), content, context)
                answer = await generate_ai_answer(
                    model_messages,
                    content,
                    force_web_search=use_web_search,
                )
''',
    "direct database answer flow",
)
SERVER.write_text(server, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    def test_ai_is_database_first(self):
        self.assertIn("return await build_catalog_ai_context(db, message)", SERVER)
        self.assertIn('"verified_from_catalog": len(found) == 2', CATALOG)
        self.assertIn("Интернет-поиск не требуется", CATALOG)
''',
    '''    def test_ai_is_database_first(self):
        self.assertIn("return await build_catalog_ai_context(db, message)", SERVER)
        self.assertIn('"verified_from_catalog": len(found) == 2', CATALOG)
        self.assertIn("Интернет-поиск не требуется", CATALOG)
        self.assertIn("build_direct_catalog_answer(context)", SERVER)
        self.assertIn('return "\\n".join(lines)', CATALOG)

    def test_product_names_are_found_with_inflection_and_context(self):
        self.assertIn("_product_name_regex(product_name)", CATALOG)
        self.assertIn("_clean_product_phrase", CATALOG)
        self.assertIn("loose=True", CATALOG)
''',
    "database-first tests",
)
TESTS.write_text(tests, encoding="utf-8")
