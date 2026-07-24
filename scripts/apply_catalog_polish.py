from pathlib import Path
import re


CATALOG = Path("backend/product_catalog.py")
MIGRATION = Path("backend/migrate_catalog_to_supabase.py")
SERVER = Path("backend/server.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


catalog = CATALOG.read_text(encoding="utf-8")
catalog = replace_once(
    catalog,
    "from fastapi import APIRouter, HTTPException, Query\n",
    '''from fastapi import APIRouter, HTTPException, Query

try:
    from .catalog_quality import (
        clean_catalog_product_name,
        filter_and_deduplicate_products,
        should_exclude_product,
    )
except ImportError:
    from catalog_quality import (
        clean_catalog_product_name,
        filter_and_deduplicate_products,
        should_exclude_product,
    )
''',
    "catalog quality import",
)
catalog = replace_once(
    catalog,
    '        "product_name": first.get("product_name"),\n',
    '        "product_name": clean_catalog_product_name(first.get("product_name")),\n',
    "clean display name",
)
catalog = replace_once(
    catalog,
    '''    for row in rows:
        row["display_manufacturer"] = row.get("manufacturer")
        row["product_group_title"] = PRODUCT_GROUPS.get(
            row.get("product_group"), {}
        ).get("title", row.get("product_group"))
    return rows
''',
    '''    for row in rows:
        row["display_manufacturer"] = row.get("manufacturer")
        row["product_group_title"] = PRODUCT_GROUPS.get(
            row.get("product_group"), {}
        ).get("title", row.get("product_group"))
    return filter_and_deduplicate_products(rows)[:limit]
''',
    "supabase cleanup",
)
catalog = replace_once(
    catalog,
    '''    products = [_serialize_grouped_product(group, product_rows) for product_rows in grouped.values()]
    products.sort(key=lambda item: normalize_text(str(item.get("product_name") or "")))
    return products[:limit]
''',
    '''    products = []
    for product_rows in grouped.values():
        if should_exclude_product(group, product_rows):
            continue
        products.append(_serialize_grouped_product(group, product_rows))
    products = filter_and_deduplicate_products(products)
    products.sort(key=lambda item: normalize_text(str(item.get("product_name") or "")))
    return products[:limit]
''',
    "mongo product cleanup",
)
catalog = replace_once(
    catalog,
    '''    merged = [item for group_items in results for item in group_items]
    merged.sort(key=lambda item: (
''',
    '''    merged = filter_and_deduplicate_products(
        item for group_items in results for item in group_items
    )
    merged.sort(key=lambda item: (
''',
    "merged catalog cleanup",
)
catalog = replace_once(
    catalog,
    '''        rows = await collection.find({"product_key": product_key}).to_list(length=5000)
        product = _serialize_grouped_product(group, rows)
''',
    '''        rows = await collection.find({"product_key": product_key}).to_list(length=5000)
        if should_exclude_product(group, rows):
            continue
        product = _serialize_grouped_product(group, rows)
''',
    "exact product exclusion",
)
catalog = replace_once(
    catalog,
    '''    if not rows:
        return None
    product = _serialize_grouped_product(group, rows)
''',
    '''    if not rows or should_exclude_product(group, rows):
        return None
    product = _serialize_grouped_product(group, rows)
''',
    "product card exclusion",
)
CATALOG.write_text(catalog, encoding="utf-8")


migration = MIGRATION.read_text(encoding="utf-8")
migration = replace_once(
    migration,
    "from motor.motor_asyncio import AsyncIOMotorClient\n",
    '''from motor.motor_asyncio import AsyncIOMotorClient

try:
    from .catalog_quality import clean_catalog_product_name, should_exclude_product
except ImportError:
    from catalog_quality import clean_catalog_product_name, should_exclude_product
''',
    "migration quality import",
)
migration = replace_once(
    migration,
    '''    for product_key, rows in grouped.items():
        first = rows[0]
''',
    '''    for product_key, rows in grouped.items():
        if should_exclude_product(group, rows):
            continue
        first = rows[0]
''',
    "migration exclusion",
)
migration = replace_once(
    migration,
    '            "product_name": text(first.get("product_name")),\n',
    '            "product_name": clean_catalog_product_name(first.get("product_name")),\n',
    "migration clean name",
)
MIGRATION.write_text(migration, encoding="utf-8")


server = SERVER.read_text(encoding="utf-8")
style_pattern = re.compile(
    r"СТИЛЬ И ФОРМАТ\n.*?- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения\.",
    flags=re.DOTALL,
)
new_style = '''СТИЛЬ И ФОРМАТ
- Пиши по-русски, живо и по делу, как опытный агроном разговаривает с хорошим знакомым прямо в поле.
- Начинай с прямого вывода. Затем простыми словами объясни, почему так, что делать на практике и где основные риски.
- Обычный ответ: 700–1400 знаков, 3–7 коротких абзацев или пунктов. Не растягивай мысль, но давай достаточно деталей для решения.
- В практических вопросах учитывай фазу культуры, развитие вредного объекта, погоду, сроки, предыдущую обработку, механизм действия и риск резистентности.
- О сложном говори простыми словами. Редкое сокращение расшифруй при первом упоминании.
- Тон — доброжелательный и искренне помогающий, без канцелярита и высокомерия. Допустима одна лёгкая полевая шутка, только если она звучит естественно.
- Не шути о безопасности, отравлении, фитотоксичности и риске потери урожая. Не превращай каждый ответ в стендап.
- Не показывай скрытый ход рассуждений и не описывай процесс проверки. Показывай вывод, полезные основания и практические шаги.
- Если данных не хватает, задай в конце не более двух самых важных уточняющих вопросов.
- Не используй Markdown-разметку: без **звёздочек**, # заголовков и обратных кавычек. Для перечней используй символ «•».
- Не показывай пользователю URL, перечень источников и технические ссылки. Источники используй для внутренней проверки фактов.
- Указывай уровень уверенности только при существенной неопределённости.
- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения.'''
server, count = style_pattern.subn(new_style, server, count=1)
if count != 1:
    raise RuntimeError(f"AI style block replacement failed: {count}")

server = replace_once(
    server,
    '''def get_ai_output_token_limit(message: str) -> int:
    normalized = normalize_search_text(message)
    default_limit = 1600 if any(
        normalize_search_text(marker) in normalized
        for marker in AI_DETAILED_ANSWER_MARKERS
    ) else 800
    configured_limit = os.environ.get("AI_MAX_OUTPUT_TOKENS")
    if configured_limit:
        try:
            return max(300, min(int(configured_limit), 2400))
        except ValueError:
            pass
    return default_limit


def get_ai_reasoning_effort() -> str:
    value = (os.environ.get("AI_REASONING_EFFORT") or "low").strip().lower()
    return value if value in {"none", "low", "medium", "high", "xhigh", "max"} else "low"
''',
    '''def get_ai_output_token_limit(message: str) -> int:
    normalized = normalize_search_text(message)
    default_limit = 2000 if any(
        normalize_search_text(marker) in normalized
        for marker in AI_DETAILED_ANSWER_MARKERS
    ) else 1200
    configured_limit = os.environ.get("AI_MAX_OUTPUT_TOKENS")
    if configured_limit:
        try:
            return max(400, min(int(configured_limit), 3200))
        except ValueError:
            pass
    return default_limit


def get_ai_reasoning_effort(message: str = "") -> str:
    configured = (os.environ.get("AI_REASONING_EFFORT") or "").strip().lower()
    if configured:
        return configured if configured in {"none", "low", "medium", "high", "xhigh", "max"} else "low"
    normalized = normalize_search_text(message)
    practical_markers = (
        "что посоветуешь", "что выбрать", "что лучше", "подбери", "схема", "почему",
        "диагноз", "симптом", "фитотокс", "резистент", "совместим", "против",
    )
    return "medium" if any(marker in normalized for marker in practical_markers) else "low"
''',
    "dynamic answer depth",
)
server = replace_once(
    server,
    '''def sanitize_ai_output(answer: str) -> str:
    text = (answer or "").strip()
    text = re.sub(r"\*\*([\s\S]*?)\*\*", r"\1", text)
    text = re.sub(r"__([\s\S]*?)__", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("`", "")
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
''',
    '''def sanitize_ai_output(answer: str) -> str:
    text = (answer or "").strip()
    text = re.sub(r"(?ims)\n\s*Источники\s*:\s*\n.*$", "", text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://[^\s)\]]+", "", text)
    text = re.sub(r"\(\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s)]*)?\s*\)", "", text)
    text = re.sub(r"\*\*([\s\S]*?)\*\*", r"\1", text)
    text = re.sub(r"__([\s\S]*?)__", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("`", "")
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
''',
    "hide links",
)
server = replace_once(
    server,
    '        "reasoning": {"effort": get_ai_reasoning_effort()},\n',
    '        "reasoning": {"effort": get_ai_reasoning_effort(current_message)},\n',
    "dynamic reasoning call",
)
server = replace_once(
    server,
    '    return sanitize_ai_output(append_ai_sources(answer.strip(), sources))\n',
    '    return sanitize_ai_output(answer.strip())\n',
    "hide source list",
)
SERVER.write_text(server, encoding="utf-8")
