import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Query

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

try:
    from .supabase_auth import build_supabase_headers, get_supabase_read_key
except ImportError:
    from supabase_auth import build_supabase_headers, get_supabase_read_key

logger = logging.getLogger(__name__)

PRODUCT_GROUPS: Dict[str, Dict[str, str]] = {
    "herbicide": {
        "collection": "herbicide_records",
        "title": "Гербициды",
    },
    "fungicide": {
        "collection": "fungicide_records",
        "title": "Фунгициды",
    },
    "insecticide": {
        "collection": "insecticide_records",
        "title": "Инсектициды",
    },
    "seed_treatment": {
        "collection": "seed_treatment_records",
        "title": "Протравители",
    },
}

GROUP_MARKERS: Dict[str, Tuple[str, ...]] = {
    "herbicide": ("гербицид", "гербициды"),
    "fungicide": ("фунгицид", "фунгициды"),
    "insecticide": ("инсектицид", "инсектициды"),
    "seed_treatment": ("протравитель", "протравители", "обработка семян"),
}

MANUFACTURER_FIELDS: Tuple[str, ...] = (
    "manufacturer",
    "registrant",
    "producer",
    "company",
    "applicant",
    "registration_holder",
    "registrant_name",
    "manufacturer_name",
    "producer_name",
    "organization",
    "registrant_organization",
    "certificate_holder",
)

SEARCH_FIELDS: Tuple[str, ...] = (
    "product_name",
    "active_substances_raw",
    "crop",
    "target_object",
    *MANUFACTURER_FIELDS,
)


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower().replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-я]+", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def detect_group(message: str) -> str:
    normalized = normalize_text(message)
    for group, markers in GROUP_MARKERS.items():
        if any(normalize_text(marker) in normalized for marker in markers):
            return group
    return ""


def extract_manufacturer(message: str) -> str:
    text = (message or "").strip()
    patterns = (
        r"(?:от|производителя|компании)\s+[«\"]?(.+?)[»\"]?(?:\s*$|[,.!?])",
        r"(?:каталог|препараты|протравители|гербициды|фунгициды|инсектициды)\s+[«\"]?([A-Za-zА-Яа-яЁё0-9 .&_-]+)[»\"]?\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" «»\".,!?-")
        candidate = re.sub(
            r"^(?:компании|производителя)\s+",
            "",
            candidate,
            flags=re.IGNORECASE,
        )
        if len(candidate) >= 3:
            return candidate
    return ""


def _clean_product_phrase(value: str) -> str:
    value = (value or "").strip(" «»\".,!?-")
    value = re.split(
        r"\s+(?:на|по|для|при|против)\s+",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return value.strip(" «»\".,!?-")


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


def is_catalog_request(message: str) -> bool:
    normalized = normalize_text(message)
    return any(marker in normalized for marker in (
        "выпиши все",
        "выпиши",
        "покажи все",
        "покажи",
        "перечисли",
        "дай список",
        "список препаратов",
        "все препараты",
        "полный список",
        "каталог",
    ))


def _loose_pattern(value: str) -> str:
    compact = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "", (value or "").strip())
    if not compact:
        return ""
    separator = r"[\s._&\-]*"
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
    return {"$regex": rf"^\s*{pattern}(?:\s*[,(/\-].*)?\s*$", "$options": "i"}


def _first_nonempty(record: Dict[str, Any], fields: Sequence[str]) -> Optional[str]:
    for field in fields:
        value = record.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _serialize_grouped_product(group: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    first = rows[0]
    composition = next(
        (
            str(row.get("active_substances_raw")).strip()
            for row in rows
            if row.get("active_substances_raw") and str(row.get("active_substances_raw")).strip()
        ),
        None,
    )
    statuses = {str(row.get("registration_status") or "").strip().lower() for row in rows}
    status = "Действует" if "действует" in statuses else first.get("registration_status")
    return {
        "product_key": first.get("product_key"),
        "product_group": group,
        "product_group_title": PRODUCT_GROUPS[group]["title"],
        "product_name": clean_catalog_product_name(first.get("product_name")),
        "formulation": first.get("formulation"),
        "active_substances_raw": composition,
        "manufacturer": _first_nonempty(first, MANUFACTURER_FIELDS),
        "display_manufacturer": _first_nonempty(first, MANUFACTURER_FIELDS),
        "registration_number": first.get("registration_number"),
        "registration_start_date": first.get("registration_start_date"),
        "registration_end_date": first.get("registration_end_date"),
        "registration_status": status,
        "applications_count": len(rows),
    }


def _application(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "crop": row.get("crop"),
        "target_object": row.get("target_object"),
        "rate_raw": row.get("rate_raw"),
        "application_method": row.get("application_method"),
        "waiting_period": row.get("waiting_period"),
        "reentry_period_manual": row.get("reentry_period_manual"),
        "reentry_period_mech": row.get("reentry_period_mech"),
        "restrictions": row.get("restrictions"),
        "source_page": row.get("source_page"),
        "source_type": row.get("source_type"),
        "notes": row.get("notes"),
        "pesticide_type": row.get("pesticide_type"),
    }


def supabase_configured() -> bool:
    return bool((os.environ.get("SUPABASE_URL") or "").strip() and get_supabase_read_key())


def _supabase_headers() -> Dict[str, str]:
    return build_supabase_headers(get_supabase_read_key())


async def search_supabase_products(
    query: str = "",
    group: str = "",
    manufacturer: str = "",
    culture: str = "",
    harmful_object: str = "",
    only_active: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    payload = {
        "p_query": query,
        "p_group": group,
        "p_manufacturer": manufacturer,
        "p_culture": culture,
        "p_harmful_object": harmful_object,
        "p_only_active": only_active,
        "p_limit": limit,
    }
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(
            f"{base_url}/rest/v1/rpc/search_catalog_products",
            headers=_supabase_headers(),
            json=payload,
        )
        response.raise_for_status()
        rows = response.json()
    for row in rows:
        row["display_manufacturer"] = row.get("manufacturer")
        row["product_group_title"] = PRODUCT_GROUPS.get(
            row.get("product_group"), {}
        ).get("title", row.get("product_group"))
    return filter_and_deduplicate_products(rows)[:limit]


async def _search_mongo_group(
    db: Any,
    group: str,
    query: str,
    manufacturer: str,
    culture: str,
    harmful_object: str,
    only_active: bool,
    limit: int,
) -> List[Dict[str, Any]]:
    collection = db[PRODUCT_GROUPS[group]["collection"]]
    filters: List[Dict[str, Any]] = []
    if query.strip():
        tokens = [token for token in normalize_text(query).split() if len(token) >= 3]
        if tokens:
            filters.append({
                "$and": [
                    {"$or": [{field: _regex(token)} for field in SEARCH_FIELDS]}
                    for token in tokens[:8]
                ]
            })
    if manufacturer.strip():
        filters.append({
            "$or": [{field: _regex(manufacturer, loose=True)} for field in MANUFACTURER_FIELDS]
        })
    if culture.strip():
        filters.append({"crop": _regex(culture)})
    if harmful_object.strip():
        filters.append({"target_object": _regex(harmful_object)})
    if only_active:
        filters.append({"registration_status": _regex("Действует", exact=True)})

    mongo_query: Dict[str, Any] = {"$and": filters} if filters else {}
    rows = await collection.find(mongo_query).to_list(length=max(limit * 30, 3000))
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("product_key") or "").strip()
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    products = []
    for product_rows in grouped.values():
        if should_exclude_product(group, product_rows):
            continue
        products.append(_serialize_grouped_product(group, product_rows))
    products = filter_and_deduplicate_products(products)
    products.sort(key=lambda item: normalize_text(str(item.get("product_name") or "")))
    return products[:limit]


async def search_mongo_products(
    db: Any,
    query: str = "",
    group: str = "",
    manufacturer: str = "",
    culture: str = "",
    harmful_object: str = "",
    only_active: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    groups = [group] if group in PRODUCT_GROUPS else list(PRODUCT_GROUPS)
    per_group_limit = min(max(limit, 50), 500)
    results = await asyncio.gather(*[
        _search_mongo_group(
            db,
            current_group,
            query,
            manufacturer,
            culture,
            harmful_object,
            only_active,
            per_group_limit,
        )
        for current_group in groups
    ])
    merged = filter_and_deduplicate_products(
        item for group_items in results for item in group_items
    )
    merged.sort(key=lambda item: (
        normalize_text(str(item.get("product_name") or "")),
        str(item.get("product_group") or ""),
    ))
    return merged[:limit]


def catalog_backend_mode() -> str:
    value = (os.environ.get("CATALOG_BACKEND") or "").strip().lower()
    if value in {"supabase", "mongo", "auto"}:
        return value
    return "supabase" if supabase_configured() else "mongo"


def catalog_mongo_fallback_allowed() -> bool:
    value = (os.environ.get("CATALOG_ALLOW_MONGO_FALLBACK") or "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


async def search_catalog_products(
    db: Any,
    query: str = "",
    group: str = "",
    manufacturer: str = "",
    culture: str = "",
    harmful_object: str = "",
    only_active: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    mode = catalog_backend_mode()
    if mode in {"supabase", "auto"}:
        if not supabase_configured():
            if mode == "supabase":
                raise HTTPException(status_code=503, detail="Каталог Supabase не настроен")
        else:
            try:
                return await search_supabase_products(
                    query=query,
                    group=group,
                    manufacturer=manufacturer,
                    culture=culture,
                    harmful_object=harmful_object,
                    only_active=only_active,
                    limit=limit,
                )
            except Exception as error:
                if mode == "supabase" and not catalog_mongo_fallback_allowed():
                    logger.error("Supabase catalog search failed without fallback: %s", type(error).__name__)
                    raise HTTPException(status_code=503, detail="Каталог временно недоступен")
                logger.warning("Supabase catalog search failed, using MongoDB fallback: %s", type(error).__name__)

    return await search_mongo_products(
        db,
        query=query,
        group=group,
        manufacturer=manufacturer,
        culture=culture,
        harmful_object=harmful_object,
        only_active=only_active,
        limit=limit,
    )


async def find_mongo_product(db: Any, product_name: str) -> Optional[Dict[str, Any]]:
    for group, config in PRODUCT_GROUPS.items():
        collection = db[config["collection"]]
        row = await collection.find_one({"product_name": _product_name_regex(product_name)})
        if not row:
            continue
        product_key = row.get("product_key")
        rows = await collection.find({"product_key": product_key}).to_list(length=5000)
        if should_exclude_product(group, rows):
            continue
        product = _serialize_grouped_product(group, rows)
        product["applications"] = [_application(item) for item in rows]
        return product
    return None


async def get_mongo_product(db: Any, group: str, product_key: str) -> Optional[Dict[str, Any]]:
    if group not in PRODUCT_GROUPS:
        return None
    collection = db[PRODUCT_GROUPS[group]["collection"]]
    rows = await collection.find({"product_key": product_key}).to_list(length=5000)
    if not rows or should_exclude_product(group, rows):
        return None
    product = _serialize_grouped_product(group, rows)
    product["applications"] = [_application(row) for row in rows]
    return product


async def build_catalog_ai_context(db: Any, message: str) -> Dict[str, Any]:
    comparison = extract_comparison_names(message)
    if comparison:
        left, right = await asyncio.gather(
            find_mongo_product(db, comparison[0]),
            find_mongo_product(db, comparison[1]),
        )
        found = [product for product in (left, right) if product]
        return {
            "source": "Единый справочник пестицидов РФ",
            "intent": "product_comparison",
            "requested_products": list(comparison),
            "products": found,
            "verified_from_catalog": len(found) == 2,
            "notice": (
                "Оба препарата найдены в базе. Интернет-поиск не требуется."
                if len(found) == 2
                else "Часть препаратов не найдена в базе."
            ),
        }

    group = detect_group(message)
    manufacturer = extract_manufacturer(message)
    if is_catalog_request(message) and (group or manufacturer):
        products = await search_catalog_products(
            db,
            group=group,
            manufacturer=manufacturer,
            limit=500,
        )
        return {
            "source": "Единый справочник пестицидов РФ",
            "intent": "manufacturer_catalog",
            "product_group": group,
            "manufacturer": manufacturer,
            "products": products,
            "verified_from_catalog": bool(products),
            "notice": f"Найдено препаратов: {len(products)}. Это полный результат запроса к базе без интернет-поиска.",
        }

    products = await search_catalog_products(db, query=message, group=group, limit=20)
    return {
        "source": "Единый справочник пестицидов РФ",
        "intent": "general_catalog_search",
        "product_group": group,
        "products": products,
        "verified_from_catalog": bool(products),
        "notice": (
            "Найдены релевантные данные в базе. Интернет-поиск не требуется."
            if products
            else "В базе не найдено релевантных препаратов."
        ),
    }


def build_direct_catalog_answer(context: Dict[str, Any]) -> Optional[str]:
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
    router = APIRouter(prefix="/api")

    @router.get("/products/search")
    async def search_products(
        q: str = Query(default=""),
        group: str = Query(default=""),
        manufacturer: str = Query(default=""),
        culture: str = Query(default=""),
        harmful_object: str = Query(default=""),
        only_active: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=500),
    ):
        return await search_catalog_products(
            db,
            query=q,
            group=group,
            manufacturer=manufacturer,
            culture=culture,
            harmful_object=harmful_object,
            only_active=only_active,
            limit=limit,
        )

    @router.get("/products/{group}/{product_key:path}")
    async def get_product(group: str, product_key: str):
        product = await get_mongo_product(db, group, product_key)
        if not product:
            raise HTTPException(status_code=404, detail="Препарат не найден")
        return product

    return router
