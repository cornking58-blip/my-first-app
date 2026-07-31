import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx

try:
    from .catalog_quality import canonical_product_name
    from .product_catalog import (
        PRODUCT_GROUPS,
        _supabase_headers,
        build_catalog_ai_context,
        build_direct_catalog_answer,
        extract_comparison_names,
        is_catalog_request,
        find_mongo_product,
        search_catalog_products,
        search_supabase_products,
        supabase_configured,
    )
except ImportError:
    from catalog_quality import canonical_product_name
    from product_catalog import (
        PRODUCT_GROUPS,
        _supabase_headers,
        build_catalog_ai_context,
        build_direct_catalog_answer,
        extract_comparison_names,
        is_catalog_request,
        find_mongo_product,
        search_catalog_products,
        search_supabase_products,
        supabase_configured,
    )


GENERIC_SINGLE_PRODUCT_WORDS = {
    "что", "думаешь", "скажешь", "посоветуешь", "препарат", "фунгицид",
    "гербицид", "инсектицид", "протравитель", "ржавчина", "подсолнечник",
    "пшеница", "соя", "кукуруза", "болезнь", "сорняк", "вредитель",
}

FIELD_TOPIC_MARKERS = (
    "против ", "на подсолнеч", "на пшениц", "на со", "на кукуруз",
    "болезн", "ржавчин", "сорня", "вредител", "обработк", "фаза ",
    "норма ", "схема ", "посоветуй", "что лучше",
)


def catalog_backend_mode() -> str:
    configured = ("supabase" if supabase_configured() else "mongo")
    value = (re.sub(r"\s+", "", __import__("os").environ.get("CATALOG_BACKEND", "")) or configured).lower()
    return value if value in {"supabase", "mongo", "auto"} else configured


def _clean_candidate(value: str) -> str:
    value = (value or "").strip(" \t\r\n«»\"'.,!?—–-")
    value = re.sub(r"^(?:а\s+)?(?:что\s+(?:думаешь|скажешь)\s+(?:о|про)\s+)", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^(?:а\s+)?(?:как\s+насч[её]т|что\s+насч[её]т)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+(?:что\s+думаешь|что\s+скажешь).*$", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\s+(?:тогда\s+)?(?:для\s+чего|зачем|как\s+работает|что\s+делает|какую\s+роль\s+играет)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:(?:расскажи|напиши|покажи)\s+(?:о|про)\s+|дай\s+информацию\s+(?:о|про)\s+)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:препарат(?:е|а|ом)?|торгов(?:ое|ого)\s+названи(?:е|я)|фунгицид(?:е|а|ом)?|гербицид(?:е|а|ом)?|инсектицид(?:е|а|ом)?|протравител(?:ь|е|я|ем)?)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip(" \t\r\n«»\"'.,!?—–-")


def extract_single_product_candidate(message: str) -> Optional[str]:
    text = (message or "").strip()
    if not text:
        return None

    first_clause = re.split(r"[?!.]", text, maxsplit=1)[0].strip()
    patterns = (
        r"^(?:а\s+)?(?:что\s+(?:думаешь|скажешь)\s+(?:о|про)\s+)(.+)$",
        r"^(?:а\s+)?(?:как\s+насч[её]т|что\s+насч[её]т)\s+(.+)$",
        r"^а\s+(.+)$",
        r"^(?:что\s+такое\s+)(.+)$",
    )
    candidate = ""
    for pattern in patterns:
        match = re.match(pattern, first_clause, flags=re.IGNORECASE)
        if match:
            candidate = _clean_candidate(match.group(1))
            break

    if not candidate:
        compact = _clean_candidate(first_clause)
        if 1 <= len(compact.split()) <= 3:
            candidate = compact

    if not candidate or len(candidate) > 90 or len(candidate.split()) > 4:
        return None
    normalized = candidate.casefold().replace("ё", "е")
    if normalized in GENERIC_SINGLE_PRODUCT_WORDS:
        return None
    if any(marker in normalized for marker in FIELD_TOPIC_MARKERS):
        return None
    if not re.search(r"[A-Za-zА-Яа-яЁё]", candidate):
        return None
    return candidate


def _is_within_one_edit(left: str, right: str) -> bool:
    """Return True only for an unambiguous one-character typo."""
    left = canonical_product_name(left)
    right = canonical_product_name(right)
    if not left or not right or left == right or abs(len(left) - len(right)) > 1:
        return False

    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1

    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    short_index = 0
    long_index = 0
    skipped = False
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue
        if skipped:
            return False
        skipped = True
        long_index += 1
    return True


def select_unambiguous_catalog_match(
    results: List[Dict[str, Any]],
    product_name: str,
) -> Optional[Dict[str, Any]]:
    """Prefer exact name; accept one-character typo only when exactly one row matches."""
    target = canonical_product_name(product_name)
    exact_matches = [
        item for item in results
        if canonical_product_name(str(item.get("product_name") or "")) == target
    ]
    if exact_matches:
        return exact_matches[0]

    if len(target) < 5:
        return None
    close_matches = [
        item for item in results
        if _is_within_one_edit(product_name, str(item.get("product_name") or ""))
    ]
    return close_matches[0] if len(close_matches) == 1 else None


def _normalize_substance_text(value: Any) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _composition_contains_substance(composition: Any, substance_name: str) -> bool:
    candidate = _normalize_substance_text(substance_name).replace(" ", "")
    composition_text = _normalize_substance_text(composition).replace(" ", "")
    return bool(len(candidate) >= 4 and candidate in composition_text)


def select_catalog_substance_matches(
    results: List[Dict[str, Any]],
    substance_name: str,
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    seen = set()
    for item in results:
        if not _composition_contains_substance(item.get("active_substances_raw"), substance_name):
            continue
        key = (
            str(item.get("product_group") or ""),
            str(item.get("product_key") or item.get("product_name") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        matches.append(dict(item))
    return matches


async def find_catalog_substance(db: Any, substance_name: str) -> List[Dict[str, Any]]:
    mode = catalog_backend_mode()
    if mode in {"supabase", "auto"} and supabase_configured():
        results = await search_supabase_products(query=substance_name, limit=50)
    elif mode == "supabase":
        return []
    else:
        results = await search_catalog_products(db, query=substance_name, limit=50)
    return select_catalog_substance_matches(results, substance_name)[:20]


async def get_supabase_product(group: str, product_key: str) -> Optional[Dict[str, Any]]:
    import os

    base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    if not base_url or group not in PRODUCT_GROUPS:
        return None
    product_query = (
        f"{base_url}/rest/v1/catalog_products"
        f"?product_group=eq.{quote(group, safe='')}"
        f"&source_product_key=eq.{quote(product_key, safe='')}"
        "&select=*"
        "&limit=1"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(product_query, headers=_supabase_headers())
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        row = rows[0]
        product_id = row.get("id")
        applications = []
        if product_id:
            app_response = await client.get(
                f"{base_url}/rest/v1/catalog_applications?product_id=eq.{quote(str(product_id), safe='')}&select=*",
                headers=_supabase_headers(),
            )
            app_response.raise_for_status()
            applications = app_response.json()

    return {
        "product_key": row.get("source_product_key"),
        "product_group": row.get("product_group"),
        "product_group_title": PRODUCT_GROUPS.get(row.get("product_group"), {}).get("title"),
        "product_name": row.get("product_name"),
        "formulation": row.get("formulation"),
        "active_substances_raw": row.get("active_substances_raw"),
        "manufacturer": row.get("manufacturer"),
        "display_manufacturer": row.get("manufacturer"),
        "registration_number": row.get("registration_number"),
        "registration_start_date": row.get("registration_start_date"),
        "registration_end_date": row.get("registration_end_date"),
        "registration_status": row.get("registration_status"),
        "applications_count": len(applications),
        "applications": applications,
    }


def is_short_contextual_fragment(value: str) -> bool:
    candidate = _clean_candidate(value)
    normalized = canonical_product_name(candidate)
    return bool(
        normalized
        and 1 <= len(candidate.split()) <= 2
        and 3 <= len(normalized) <= 32
        and not is_catalog_request(value)
    )


async def search_catalog_candidate_products(
    db: Any,
    query: str,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    mode = catalog_backend_mode()
    if mode in {"supabase", "auto"} and supabase_configured():
        return await search_supabase_products(query=query, limit=limit)
    if mode == "supabase":
        return []
    return await search_catalog_products(db, query=query, limit=limit)


async def find_catalog_product(db: Any, product_name: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    mode = catalog_backend_mode()
    results = await search_catalog_candidate_products(db, product_name, limit=12)

    suggestions: List[str] = []
    for item in results:
        name = str(item.get("product_name") or "").strip()
        if name and name not in suggestions:
            suggestions.append(name)

    matched = select_unambiguous_catalog_match(results, product_name)
    if matched:
        group = str(matched.get("product_group") or "")
        key = str(matched.get("product_key") or "")
        if mode in {"supabase", "auto"} and supabase_configured():
            full = await get_supabase_product(group, key)
            if full:
                return full, suggestions[:5]
        mongo_product = await find_mongo_product(db, str(matched.get("product_name") or product_name))
        if mongo_product:
            return mongo_product, suggestions[:5]
        return dict(matched), suggestions[:5]

    return None, suggestions[:5]


async def build_strict_catalog_ai_context(db: Any, message: str) -> Dict[str, Any]:
    comparison = extract_comparison_names(message)
    if comparison:
        left_result, right_result = await __import__("asyncio").gather(
            find_catalog_product(db, comparison[0]),
            find_catalog_product(db, comparison[1]),
        )
        left, left_suggestions = left_result
        right, right_suggestions = right_result
        found = [product for product in (left, right) if product]
        if len(found) == 2:
            return {
                "source": "Единый справочник пестицидов РФ",
                "intent": "product_comparison",
                "requested_products": list(comparison),
                "products": found,
                "verified_from_catalog": True,
                "catalog_lookup_attempted": True,
                "allow_web_fallback": False,
                "notice": "Оба препарата найдены в каталоге. Интернет-поиск не требуется.",
            }
        return {
            "source": "Единый справочник пестицидов РФ",
            "intent": "product_not_found",
            "requested_products": list(comparison),
            "missing_products": [name for name, product in zip(comparison, (left, right)) if not product],
            "products": found,
            "suggestions": list(dict.fromkeys(left_suggestions + right_suggestions))[:6],
            "verified_from_catalog": False,
            "catalog_lookup_attempted": True,
            "allow_web_fallback": False,
        }

    if is_catalog_request(message):
        catalog_context = await build_catalog_ai_context(db, message)
        if catalog_context.get("intent") == "manufacturer_catalog":
            catalog_context["catalog_lookup_attempted"] = True
            catalog_context["allow_web_fallback"] = False
            return catalog_context

    candidate = extract_single_product_candidate(message)
    if candidate:
        product, suggestions = await find_catalog_product(db, candidate)
        if product:
            return {
                "source": "Единый справочник пестицидов РФ",
                "intent": "single_product",
                "entity_type": "product",
                "requested_product": candidate,
                "products": [product],
                "verified_from_catalog": True,
                "catalog_lookup_attempted": True,
                "allow_web_fallback": False,
                "notice": "Препарат найден в каталоге. Используй только переданные данные.",
            }

        if is_short_contextual_fragment(candidate) and suggestions:
            candidate_products = await search_catalog_candidate_products(db, candidate, limit=12)
            if candidate_products:
                return {
                    "source": "Единый справочник пестицидов РФ",
                    "intent": "contextual_product_followup",
                    "entity_type": "product_fragment",
                    "requested_fragment": candidate,
                    "products": candidate_products,
                    "suggestions": suggestions,
                    "verified_from_catalog": True,
                    "catalog_lookup_attempted": True,
                    "allow_web_fallback": False,
                    "notice": (
                        "Короткое уточнение найдено в названиях нескольких препаратов. "
                        "Используй предыдущие сообщения диалога, чтобы выбрать только "
                        "однозначно подходящее полное название."
                    ),
                    "answer_instruction": (
                        "Свяжи короткий фрагмент с предыдущей репликой пользователя. "
                        "Например, после «препарат Амистар» слово «Голд» означает "
                        "«Амистар Голд», но только если такой вариант есть среди переданных "
                        "кандидатов. Если контекст не даёт одного точного варианта, задай "
                        "один короткий уточняющий вопрос. Не объявляй фрагмент новым препаратом."
                    ),
                }

        substance_products = await find_catalog_substance(db, candidate)
        if substance_products:
            return {
                "source": "Единый справочник пестицидов РФ",
                "intent": "active_substance",
                "entity_type": "active_substance",
                "requested_substance": candidate,
                "products": substance_products,
                "verified_from_catalog": True,
                "catalog_lookup_attempted": True,
                "allow_web_fallback": False,
                "notice": (
                    "Термин найден в составах препаратов как действующее вещество, "
                    "а не как торговое название."
                ),
                "answer_instruction": (
                    "Объясни роль действующего вещества простыми словами: механизм действия, "
                    "зачем оно нужно в смеси, сильные и слабые стороны, практическое применение "
                    "и риск резистентности. Учитывай предыдущие сообщения диалога."
                ),
            }

        return {
            "source": "Единый справочник пестицидов РФ",
            "intent": "product_not_found",
            "requested_product": candidate,
            "missing_products": [candidate],
            "products": [],
            "suggestions": suggestions,
            "verified_from_catalog": False,
            "catalog_lookup_attempted": True,
            "allow_web_fallback": False,
        }

    context = await build_catalog_ai_context(db, message)
    context.setdefault("catalog_lookup_attempted", True)
    return context


def build_strict_direct_answer(context: Dict[str, Any]) -> Optional[str]:
    existing = build_direct_catalog_answer(context)
    if existing:
        return existing
    if context.get("intent") != "product_not_found":
        return None

    missing = context.get("missing_products") or []
    requested = ", ".join(str(item) for item in missing if item) or str(context.get("requested_product") or "препарат")
    lines = [
        f"Не нашёл точное название «{requested}» в каталоге bAIkov.",
        "Состав и регламент угадывать не буду — именно так появляются уверенные, но неверные ответы.",
    ]
    suggestions = context.get("suggestions") or []
    if suggestions:
        lines.append("Похожие названия в базе: " + ", ".join(str(item) for item in suggestions[:5]) + ".")
    lines.append("Проверь написание названия или пришли фото этикетки.")
    return "\n\n".join(lines)
