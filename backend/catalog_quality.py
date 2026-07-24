import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple


EXCLUDED_PRODUCT_NAMES = {
    "кимк",
    "фумифаст",
    "fumifast",
}

PRODUCT_NAME_ALIASES = {
    "кимкомби": "кингкомби",
    "кингкомби": "кингкомби",
}

FUMIGANT_MARKERS = (
    "фумигант",
    "фумигац",
    "обработка склад",
    "обработки склад",
    "складских помещ",
    "зернохранилищ",
    "пустых склад",
    "незагруженных склад",
    "газовая обработка",
)

ROW_CLASSIFICATION_FIELDS = (
    "product_name",
    "pesticide_type",
    "application_method",
    "crop",
    "target_object",
    "notes",
    "restrictions",
    "source_type",
)


def normalize_catalog_text(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def clean_catalog_product_name(value: Any) -> str:
    text = str(value or "").strip(" \t\r\n,;|—–-")
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_product_name(value: Any) -> str:
    normalized = normalize_catalog_text(clean_catalog_product_name(value))
    compact = normalized.replace(" ", "")
    return PRODUCT_NAME_ALIASES.get(compact, compact)


def is_explicitly_excluded_name(value: Any) -> bool:
    normalized = normalize_catalog_text(value)
    compact = normalized.replace(" ", "")
    return normalized in EXCLUDED_PRODUCT_NAMES or compact in EXCLUDED_PRODUCT_NAMES


def is_fumigant_row(row: Dict[str, Any]) -> bool:
    haystack = " ".join(
        normalize_catalog_text(row.get(field))
        for field in ROW_CLASSIFICATION_FIELDS
        if row.get(field) is not None
    )
    return any(marker in haystack for marker in FUMIGANT_MARKERS)


def should_exclude_product(group: str, rows: Sequence[Dict[str, Any]]) -> bool:
    if not rows:
        return True
    if any(is_explicitly_excluded_name(row.get("product_name")) for row in rows):
        return True
    if group == "seed_treatment" and any(is_fumigant_row(row) for row in rows):
        return True
    return False


def _product_priority(product: Dict[str, Any]) -> Tuple[int, int, int, int]:
    active = 1 if normalize_catalog_text(product.get("registration_status")) == "действует" else 0
    composition = 1 if str(product.get("active_substances_raw") or "").strip() else 0
    applications = int(product.get("applications_count") or 0)
    name_length = len(clean_catalog_product_name(product.get("product_name")))
    return active, composition, applications, name_length


def filter_and_deduplicate_products(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []

    for raw_product in products or []:
        product = dict(raw_product)
        group = str(product.get("product_group") or "").strip()
        name = clean_catalog_product_name(product.get("product_name"))
        if not name or is_explicitly_excluded_name(name):
            continue

        product["product_name"] = name
        identity = canonical_product_name(name)
        if not identity:
            continue
        key = (group, identity)

        current = selected.get(key)
        if current is None:
            selected[key] = product
            order.append(key)
        elif _product_priority(product) > _product_priority(current):
            selected[key] = product

    return [selected[key] for key in order]
