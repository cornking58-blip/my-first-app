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


async def find_catalog_product(db: Any, product_name: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    target = canonical_product_name(product_name)
    mode = catalog_backend_mode()

    if mode in {"supabase", "auto"} and supabase_configured():
        results = await search_supabase_products(query=product_name, limit=12)
    elif mode == "supabase":
        return None, []
    else:
        results = await search_catalog_products(db, query=product_name, limit=12)

    suggestions: List[str] = []
    exact = None
    for item in results:
        name = str(item.get("product_name") or "").strip()
        if name and name not in suggestions:
            suggestions.append(name)
        if name and canonical_product_name(name) == target:
            exact = item
            break

    if exact:
        group = str(exact.get("product_group") or "")
        key = str(exact.get("product_key") or "")
        if mode in {"supabase", "auto"} and supabase_configured():
            full = await get_supabase_product(group, key)
            if full:
                return full, suggestions[:5]
        mongo_product = await find_mongo_product(db, product_name)
        if mongo_product:
            return mongo_product, suggestions[:5]
        return dict(exact), suggestions[:5]

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

    candidate = extract_single_product_candidate(message)
    if candidate:
        product, suggestions = await find_catalog_product(db, candidate)
        if product:
            return {
                "source": "Единый справочник пестицидов РФ",
                "intent": "single_product",
                "requested_product": candidate,
                "products": [product],
                "verified_from_catalog": True,
                "catalog_lookup_attempted": True,
                "allow_web_fallback": False,
                "notice": "Препарат найден в каталоге. Используй только переданные данные.",
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
