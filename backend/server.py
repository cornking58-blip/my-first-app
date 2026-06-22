from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import re
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Sequence, Tuple
import uuid
from datetime import datetime
import pandas as pd
import io
from collections import Counter, defaultdict


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'herbicides_db')]

# Create the main app
app = FastAPI(title="Herbicides API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class HerbicideRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: Optional[int] = None
    product_name: str
    product_key: str
    formulation: Optional[str] = None
    active_substances_raw: Optional[str] = None
    manufacturer: Optional[str] = None
    registrant: Optional[str] = None
    producer: Optional[str] = None
    company: Optional[str] = None
    applicant: Optional[str] = None
    registration_holder: Optional[str] = None
    registrant_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    producer_name: Optional[str] = None
    organization: Optional[str] = None
    registrant_organization: Optional[str] = None
    certificate_holder: Optional[str] = None
    display_manufacturer: Optional[str] = None
    registration_number: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    registration_status: Optional[str] = None
    rate_raw: Optional[str] = None
    crop: Optional[str] = None
    target_object: Optional[str] = None
    application_method: Optional[str] = None
    waiting_period: Optional[str] = None
    reentry_period_manual: Optional[str] = None
    reentry_period_mech: Optional[str] = None
    restrictions: Optional[str] = None
    source_page: Optional[str] = None
    source_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ImportBatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    records_imported: int
    import_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = "completed"


class ProductCard(BaseModel):
    product_key: str
    product_name: str
    formulation: Optional[str] = None
    active_substances_raw: Optional[str] = None
    manufacturer: Optional[str] = None
    registrant: Optional[str] = None
    producer: Optional[str] = None
    company: Optional[str] = None
    applicant: Optional[str] = None
    registration_holder: Optional[str] = None
    registrant_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    producer_name: Optional[str] = None
    organization: Optional[str] = None
    registrant_organization: Optional[str] = None
    certificate_holder: Optional[str] = None
    display_manufacturer: Optional[str] = None
    registration_number: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    registration_status: Optional[str] = None
    applications: List[dict] = []
    composition_warnings: List[dict] = []
    has_composition_warning: bool = False


class CompareRequest(BaseModel):
    left_key: str
    right_key: str


class AdvancedCompareRequest(BaseModel):
    left_key: str
    right_key: str
    left_price: Optional[float] = None  # Price per L/kg
    right_price: Optional[float] = None  # Price per L/kg
    left_rate: Optional[float] = None  # Manual rate for comparison only
    right_rate: Optional[float] = None  # Manual rate for comparison only
    crop: Optional[str] = None  # Optional crop to check product registration rows


class SearchResult(BaseModel):
    product_key: str
    product_name: str
    formulation: Optional[str] = None
    active_substances_raw: Optional[str] = None
    manufacturer: Optional[str] = None
    registrant: Optional[str] = None
    producer: Optional[str] = None
    company: Optional[str] = None
    applicant: Optional[str] = None
    registration_holder: Optional[str] = None
    registrant_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    producer_name: Optional[str] = None
    organization: Optional[str] = None
    registrant_organization: Optional[str] = None
    certificate_holder: Optional[str] = None
    display_manufacturer: Optional[str] = None
    registration_status: Optional[str] = None
    applications_count: int = 0


RUSSIAN_ENDINGS = (
    "иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ая", "яя", "ое", "ее",
    "ые", "ие", "ый", "ий", "ой", "ую", "юю", "ом", "ем", "ах", "ях",
    "ов", "ев", "ей", "ам", "ям", "ою", "ею", "а", "я", "ы", "и",
    "у", "ю", "е", "о", "ь",
)


OPTIONAL_OCR_SEPARATOR_REGEX = r"[\s\-–—_,.;:()/\\]*"


def normalize_search_text(value: str) -> str:
    """Normalize user text before building a forgiving MongoDB regex."""
    normalized = (value or "").strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-яе]+", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def build_ocr_tolerant_literal_regex(value: str) -> str:
    """Allow OCR/PDF separators inside a searched word, e.g. подсолнечн ик."""
    parts = []
    for char in value:
        if char.isspace():
            if parts and parts[-1] != OPTIONAL_OCR_SEPARATOR_REGEX:
                parts.append(OPTIONAL_OCR_SEPARATOR_REGEX)
            continue
        if char == "е":
            parts.append("[её]")
        else:
            parts.append(re.escape(char))
        parts.append(OPTIONAL_OCR_SEPARATOR_REGEX)

    while parts and parts[-1] == OPTIONAL_OCR_SEPARATOR_REGEX:
        parts.pop()
    return "".join(parts)


def make_flexible_text_regex(value: str) -> str:
    """
    Build a MongoDB regex for forgiving Russian text matching.

    It keeps partial-match behavior, treats ``е`` and ``ё`` as equal, trims common
    Russian endings, and tolerates OCR/PDF word breaks such as ``Подсолнечн ик``.
    Latin/numeric product names still work as regular partial matches.
    """
    normalized = normalize_search_text(value)
    if not normalized:
        return ""

    compact_normalized = normalized.replace(" ", "")
    has_cyrillic = bool(re.search(r"[а-я]", normalized, flags=re.IGNORECASE))
    stem = normalized
    if has_cyrillic and len(compact_normalized) >= 4:
        for ending in RUSSIAN_ENDINGS:
            if compact_normalized.endswith(ending) and len(compact_normalized) - len(ending) >= 3:
                stem = compact_normalized[: -len(ending)]
                break
        else:
            stem = compact_normalized

    pattern = build_ocr_tolerant_literal_regex(stem)

    if has_cyrillic and len(stem.replace(" ", "")) >= 3:
        return f"{pattern}[а-яё]*"
    return pattern


def build_flexible_field_match(field: str, value: str) -> dict:
    return {field: {"$regex": make_flexible_text_regex(value), "$options": "i"}}


HARMFUL_OBJECT_FIELDS = (
    "target_object",
    "harmful_object",
    "harmful_objects",
    "disease",
    "diseases",
)

FUNGICIDE_HARMFUL_OBJECT_FIELDS = HARMFUL_OBJECT_FIELDS
TARGET_OBJECT_IMPORT_COLUMNS = HARMFUL_OBJECT_FIELDS


DISPLAY_MANUFACTURER_FALLBACK = "Производитель не указан"
MANUFACTURER_FIELD_PRIORITY = (
    "manufacturer",
    "registrant",
    "manufacturer_name",
    "registrant_name",
    "producer",
    "producer_name",
    "company",
    "applicant",
    "registration_holder",
    "organization",
    "registrant_organization",
    "certificate_holder",
)


def _normalize_display_manufacturer_value(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "нет данных"}:
        return None
    return text


def _first_display_manufacturer_value(value) -> Optional[str]:
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_display_manufacturer_value(item)
            if normalized:
                return normalized
        return None
    return _normalize_display_manufacturer_value(value)


def get_display_manufacturer(record: Optional[dict]) -> str:
    """Return the best manufacturer/registrant value for UI display."""
    record = record or {}
    for field in MANUFACTURER_FIELD_PRIORITY:
        value = _first_display_manufacturer_value(record.get(field))
        if value:
            return value
    return DISPLAY_MANUFACTURER_FALLBACK


def get_records_display_manufacturer(records: Sequence[dict]) -> str:
    """Return the best manufacturer/registrant value across product rows."""
    records = records or []
    for field in MANUFACTURER_FIELD_PRIORITY:
        for record in records:
            value = _first_display_manufacturer_value(record.get(field))
            if value:
                return value
    return DISPLAY_MANUFACTURER_FALLBACK


def manufacturer_response_fields(record: Optional[dict], records: Optional[Sequence[dict]] = None) -> dict:
    """Return original manufacturer-like fields plus the stable display value."""
    record = record or {}
    response = {field: record.get(field) for field in MANUFACTURER_FIELD_PRIORITY}
    response["display_manufacturer"] = (
        get_records_display_manufacturer(records) if records is not None else get_display_manufacturer(record)
    )
    return response


def build_registration_filters(
    culture: str = "",
    crop: str = "",
    harmful_object: str = "",
    harmful_object_fields: Sequence[str] = ("target_object",),
) -> Optional[dict]:
    """
    Build row-level filters for registration crop and harmful object.
    ``culture`` is the public API parameter; ``crop`` is kept for backward compatibility.
    """
    selected_culture = (culture or crop or "").strip()
    selected_harmful_object = (harmful_object or "").strip()

    filters = {}
    if selected_culture:
        filters["crop"] = build_flexible_field_match("crop", selected_culture)["crop"]
    if selected_harmful_object:
        harmful_matches = [
            build_flexible_field_match(field, selected_harmful_object)
            for field in harmful_object_fields
        ]
        if len(harmful_matches) == 1:
            filters.update(harmful_matches[0])
        else:
            filters["$or"] = harmful_matches

    return filters or None


def build_search_match(query: str) -> Optional[dict]:
    """
    Build MongoDB $match for flexible multi-word search across registration rows.
    Each word from the query must be found in at least one searchable field.
    """
    # Support queries like: "crop + target_object + registration_status"
    # Split by +, comma, semicolon, or whitespace and ignore empty parts.
    tokens = [
        token.strip()
        for token in re.split(r"[+,;\s]+", query.strip())
        if token.strip()
    ]
    if not tokens:
        return None

    searchable_fields = [
        "product_name",
        "crop",
        "target_object",
        "registration_status",
        "active_substances_raw",
        *MANUFACTURER_FIELD_PRIORITY,
    ]

    return {
        "$and": [
            {
                "$or": [
                    build_flexible_field_match(field, token)
                    for field in searchable_fields
                ]
            }
            for token in tokens
        ]
    }


# ==================== ACTIVE SUBSTANCE PARSER ====================

from collections import Counter, defaultdict
from typing import Tuple

SUPPORTED_CONCENTRATION_UNITS_REGEX = r"г/л|г/кг|%"
COMPOSITION_SEPARATOR_REGEX = r"\s*(?:\+|/|,|;|\band\b)\s*"
DASH_CHARS_REGEX = r"[‐‑‒–—−]"

NON_SUBSTANCE_TEXT_PATTERNS = (
    "норма", "расход", "культура", "вредный", "объект", "болезн", "сорняк",
    "производител", "изготовител", "регистрант", "заявител", "регистрац",
    "свидетельств", "препаратив", "форма", "концентрат", "эмульси", "суспензи",
    "раствор", "опрыскиван", "обработка", "протравлив", "семян", "почв",
    "урожай", "срок", "ожидания", "примечан", "том числе", "нет данных",
)


def normalize_composition_text(raw: str) -> str:
    """Normalize OCR punctuation/spacing while preserving the original source elsewhere."""
    text = str(raw or "")
    text = text.replace("\u00a0", " ").replace("\ufeff", " ")
    text = re.sub(DASH_CHARS_REGEX, "-", text)
    # Treat multiplication signs inside scientific notation (for example 2,5×10⁹)
    # as part of the concentration, not as component separators. Only spaced
    # multiplication signs are safe delimiter variants.
    text = re.sub(r"\s+[×*]\s+", " + ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([+;])\s*", r" \1 ", text)
    text = re.sub(r"\(\s*", "(", text)
    text = re.sub(r"\s*\)", ")", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"(\d)\s*,\s*(\d)", r"\1,\2", text)
    text = re.sub(r"г\s*/\s*л", "г/л", text, flags=re.IGNORECASE)
    text = re.sub(r"г\s*/\s*кг", "г/кг", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*/\s*", " / ", text)
    text = re.sub(r"г\s*/\s*л", "г/л", text, flags=re.IGNORECASE)
    text = re.sub(r"г\s*/\s*кг", "г/кг", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*-\s*", " - ", text)
    text = re.sub(r"(?:\+\s*){2,}", "+", text)
    text = re.sub(r"(?:[,;]\s*){2,}", "; ", text)
    return re.sub(r"\s+", " ", text).strip()


def _composition_compare_key(text: str) -> str:
    normalized = normalize_composition_text(text).casefold().replace("ё", "е")
    normalized = re.sub(r"\s+", " ", normalized).strip(" ()+;,/")
    return normalized


def _warning(code: str, message: str, severity: str = "warning", **details) -> Dict[str, Any]:
    warning = {"code": code, "message": message, "severity": severity}
    warning.update({key: value for key, value in details.items() if value is not None})
    return warning


def _dedupe_warnings(warnings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for warning in warnings:
        key = (warning.get("code"), warning.get("message"), json.dumps(warning.get("details", warning), ensure_ascii=False, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        result.append(warning)
    return result


def _is_known_active_substance_name_for_type(name: str, pesticide_type: Optional[str] = None) -> bool:
    """Exact known-substance check; no fuzzy matching or guessing."""
    normalized = normalize_resistance_lookup_name(name)
    pesticide_type = (pesticide_type or "").strip().lower()
    lookup_types = [pesticide_type] if pesticide_type else list(RESISTANCE_GROUPS.keys())
    if pesticide_type in {"seed-treatment", "seed_treatment", "seed-treatment-mixed"}:
        lookup_types = ["fungicide", "insecticide"]
    for lookup_type in lookup_types:
        table = RESISTANCE_GROUPS.get(lookup_type, {})
        if normalized in table:
            return True
    return False


def _split_known_joined_name_candidates(name: str, pesticide_type: Optional[str] = None) -> List[str]:
    """Split joined names only when every resulting token is already known."""
    clean_name = normalize_composition_text(name).strip()
    delimiter_patterns = [
        r"\s+[-]\s+",
        r"\s*/\s*",
        r"\s*[,;]\s*",
    ]
    for pattern in delimiter_patterns:
        parts = [part.strip(" .()") for part in re.split(pattern, clean_name) if part.strip(" .()")]
        if len(parts) > 1 and all(_is_known_active_substance_name_for_type(part, pesticide_type) for part in parts):
            return parts

    # Lost delimiter: two known multi-letter names glued together. This is deliberately exact:
    # both sides must be known lookup keys, and each side must be at least 4 chars.
    compact = re.sub(r"[\s-]+", "", normalize_resistance_lookup_name(clean_name))
    if len(compact) >= 8:
        for index in range(4, len(compact) - 3):
            left = compact[:index]
            right = compact[index:]
            if (
                _is_known_active_substance_name_for_type(left, pesticide_type)
                and _is_known_active_substance_name_for_type(right, pesticide_type)
            ):
                return [left, right]

    return [name.strip()]


def deduplicate_repeated_composition_fragments(raw: str) -> Tuple[str, bool]:
    """Remove exact repeated composition fragments such as A+B+A+B without changing source data."""
    text = normalize_composition_text(raw)
    if not text:
        return text, False

    had_outer_parentheses = text.startswith("(") and text.endswith(")")
    inner = text[1:-1].strip() if had_outer_parentheses else text
    parts = [part.strip() for part in re.split(r"\s*\+\s*", inner) if part.strip()]
    if len(parts) < 2:
        return text, False

    keys = [_composition_compare_key(part) for part in parts]
    for fragment_len in range(1, min(4, len(parts) // 2) + 1):
        if len(parts) % fragment_len != 0:
            continue
        first = keys[:fragment_len]
        if all(keys[i:i + fragment_len] == first for i in range(0, len(keys), fragment_len)):
            deduped = " + ".join(parts[:fragment_len])
            return (f"({deduped})" if had_outer_parentheses else deduped), True

    deduped_parts = []
    seen = set()
    changed = False
    for part, key in zip(parts, keys):
        if key in seen:
            changed = True
            continue
        seen.add(key)
        deduped_parts.append(part)
    if changed:
        deduped = " + ".join(deduped_parts)
        return (f"({deduped})" if had_outer_parentheses else deduped), True
    return text, False


def validate_active_substance_composition(
    raw_composition: Optional[str],
    parsed_substances: Optional[List[Dict]],
    pesticide_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return structured composition warnings without inventing substances or concentrations."""
    warnings: List[Dict[str, Any]] = []
    raw_text = str(raw_composition or "")
    normalized_raw = normalize_composition_text(raw_text)
    parsed_substances = parsed_substances or []

    if raw_text and raw_text != normalized_raw:
        if "\u00a0" in raw_text or re.search(r"([+;,])\s*\1", raw_text):
            warnings.append(_warning(
                "malformed_delimiters",
                "Composition contains OCR/formatting punctuation that was normalized for parsing.",
                "warning",
            ))

    _, repeated = deduplicate_repeated_composition_fragments(raw_text)
    if repeated:
        warnings.append(_warning(
            "repeated_fragment",
            "Composition contains exactly repeated component fragments; parser deduplicated them.",
            "error",
        ))

    component_markers = len(re.findall(rf"\d+(?:[.,]\d+)?\s*(?:{SUPPORTED_CONCENTRATION_UNITS_REGEX})", normalized_raw, flags=re.IGNORECASE))
    parsed_count = len(parsed_substances)
    if parsed_count > 5 or (component_markers and parsed_count > component_markers + 2):
        warnings.append(_warning(
            "excessive_component_count",
            "Parsed component count is suspicious for the number of concentration markers.",
            "warning",
            parsed_component_count=parsed_count,
            concentration_marker_count=component_markers,
        ))

    normalized_name_counts: Counter = Counter()
    concentrations_by_name: Dict[str, set] = defaultdict(set)
    for substance in parsed_substances:
        name = substance.get("name") or ""
        normalized_name = normalize_substance_name(name)
        if not normalized_name:
            continue
        normalized_name_counts[normalized_name] += 1
        concentrations_by_name[normalized_name].add((substance.get("concentration"), substance.get("unit")))

        if substance.get("concentration_unresolved") or substance.get("concentration") is None or not substance.get("unit"):
            warnings.append(_warning(
                "unresolved_concentration",
                "Known parsed active substance has no reliable separate concentration in the source composition.",
                "error",
                substance=name,
            ))

        lowered_name = normalized_name.casefold()
        if any(pattern in lowered_name for pattern in NON_SUBSTANCE_TEXT_PATTERNS) or re.search(r"\b\d+\s*(?:л|кг|га|т)\b", lowered_name):
            warnings.append(_warning(
                "suspicious_non_substance_text",
                "Parsed name looks like formulation, rate, crop, manufacturer, registration, or note text rather than an active substance.",
                "error",
                substance=name,
            ))

        split_parts = _split_known_joined_name_candidates(name, pesticide_type)
        if len(split_parts) > 1:
            warnings.append(_warning(
                "joined_known_substances",
                "Parsed name contains multiple known active substances joined by a delimiter.",
                "error",
                substance=name,
                split_parts=split_parts,
            ))

    for normalized_name, count in normalized_name_counts.items():
        if count > 1:
            warnings.append(_warning(
                "duplicate_substance",
                "Same normalized active substance appears more than once in one composition.",
                "warning",
                substance=normalized_name,
            ))
        known_concentrations = {item for item in concentrations_by_name[normalized_name] if item[0] is not None and item[1] is not None}
        if len(known_concentrations) > 1:
            warnings.append(_warning(
                "conflicting_concentrations",
                "Same normalized active substance has different concentrations in one composition.",
                "error",
                substance=normalized_name,
                concentrations=sorted(known_concentrations),
            ))

    # Raw-level safe joined-substance detection even if the current parser missed it.
    concentration_name_fragments = re.findall(
        rf"\d+(?:[.,]\d+)?\s*(?:{SUPPORTED_CONCENTRATION_UNITS_REGEX})\s*([^+()]+)",
        normalized_raw,
        flags=re.IGNORECASE,
    )
    for fragment in concentration_name_fragments:
        split_parts = _split_known_joined_name_candidates(fragment.strip(), pesticide_type)
        if len(split_parts) > 1:
            warnings.append(_warning(
                "joined_known_substances",
                "Raw composition contains multiple known active substances joined in one component fragment.",
                "error",
                substance=fragment.strip(),
                split_parts=split_parts,
            ))

    if re.search(r"[а-яА-ЯёЁ]\s{2,}[а-яА-ЯёЁ]", raw_text) or re.search(r"[()]", raw_text) and raw_text.count("(") != raw_text.count(")"):
        warnings.append(_warning(
            "malformed_delimiters",
            "Composition contains suspicious OCR spacing or broken parentheses.",
            "warning",
        ))

    return _dedupe_warnings(warnings)


def composition_warning_codes(warnings: Sequence[Dict[str, Any]]) -> List[str]:
    return sorted({warning.get("code") for warning in warnings if warning.get("code")})


def build_composition_metadata(raw_composition: Optional[str], pesticide_type: Optional[str] = None) -> Dict[str, Any]:
    parsed = parse_active_substances(raw_composition)
    warnings = validate_active_substance_composition(raw_composition, parsed, pesticide_type)
    return {
        "composition_warnings": warnings,
        "has_composition_warning": bool(warnings),
    }


def _iter_canonical_composition_values(raw) -> List[str]:
    """Return unique canonical composition strings without mixing in other fields."""
    if raw is None:
        return []

    values = raw if isinstance(raw, (list, tuple, set)) else [raw]
    canonical_values = []
    seen = set()

    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none"}:
            continue
        dedupe_key = re.sub(r"\s+", " ", text.casefold().replace("ё", "е")).strip()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        canonical_values.append(text)

    return canonical_values


def product_name_composition_candidate(product_name: Optional[str]) -> Optional[str]:
    """Extract explicit composition from product-name parentheses only when units prove it."""
    text = str(product_name or "").strip()
    if not text:
        return None
    candidates = re.findall(r"\(([^()]*)\)", text)
    for candidate in reversed(candidates):
        candidate = candidate.strip()
        if re.search(rf"\d+(?:[.,]\d+)?\s*(?:{SUPPORTED_CONCENTRATION_UNITS_REGEX})", candidate, re.IGNORECASE):
            parsed = parse_active_substances(candidate)
            if parsed:
                return f"({candidate})"
    return None


def clean_seed_treatment_display_name(product_name: Optional[str]) -> Optional[str]:
    """For display only, remove parseable active-substance parentheses from a product title."""
    text = str(product_name or "").strip()
    if not text:
        return product_name

    def replace_if_composition(match: re.Match) -> str:
        inner = match.group(1).strip()
        if re.search(rf"\d+(?:[.,]\d+)?\s*(?:{SUPPORTED_CONCENTRATION_UNITS_REGEX})", inner, re.IGNORECASE):
            if parse_active_substances(inner):
                return ""
        return match.group(0)

    cleaned = re.sub(r"\s*\(([^()]*)\)", replace_if_composition, text)
    return re.sub(r"\s+", " ", cleaned).strip(" ,;")


def seed_treatment_record_composition_candidates(record: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return safe composition candidates in priority order: active field, then product name."""
    candidates: List[Tuple[str, str]] = []
    raw = record.get("active_substances_raw") if isinstance(record, dict) else None
    if raw is not None:
        text = str(raw).strip()
        if text and text.lower() not in {"nan", "none", "нет данных"} and parse_active_substances(text):
            candidates.append(("active_substances_raw", text))
    product_candidate = product_name_composition_candidate(record.get("product_name") if isinstance(record, dict) else None)
    if product_candidate:
        candidates.append(("product_name", product_candidate))
    return candidates




PROTECT_COMBI_CANONICAL_SUBSTANCES = [
    {"name": "Пираклостробин", "concentration": 55, "unit": "г/л", "is_antidote": False},
    {"name": "протиоконазол", "concentration": 48, "unit": "г/л", "is_antidote": False},
    {"name": "Флудиоксонил", "concentration": 37.5, "unit": "г/л", "is_antidote": False},
    {"name": "Тебуконазол", "concentration": 10, "unit": "г/л", "is_antidote": False},
]


def _format_concentration_for_composition(value: Any) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return (str(number).rstrip("0").rstrip(".")).replace(".", ",")


def build_canonical_active_substances_raw(substances: Sequence[Dict[str, Any]]) -> Optional[str]:
    """Build clean UI-facing composition text from final parsed substances."""
    components = []
    for substance in substances or []:
        concentration = substance.get("concentration")
        unit = substance.get("unit")
        name = substance.get("name")
        if concentration is None or not unit or not name:
            return None
        components.append(f"{_format_concentration_for_composition(concentration)} {unit} {name}")
    if not components:
        return None
    return "(" + " + ".join(components) + ")"


PROTECT_COMBI_CANONICAL_COMPOSITION = build_canonical_active_substances_raw(PROTECT_COMBI_CANONICAL_SUBSTANCES)


def normalize_verified_seed_treatment_composition(product_name: Optional[str], raw_composition: Optional[str] = None) -> Optional[str]:
    """Return explicit verified seed-treatment corrections only for named products.

    This intentionally avoids a broad dash rule: ambiguous fragments like
    ``100 г/л A - B`` are not interpreted as two equal concentrations.
    """
    normalized_name = normalize_search_text(clean_seed_treatment_display_name(product_name or ""))
    if normalized_name == "протект комби":
        return PROTECT_COMBI_CANONICAL_COMPOSITION
    return None

def canonical_seed_treatment_composition(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Select one explicit seed-treatment composition without silently merging conflicts."""
    chosen_source = None
    chosen = None
    chosen_original = None
    conflicts = []
    seen = set()
    all_parseable = []

    product_name = next((record.get("product_name") for record in records or [] if isinstance(record, dict) and record.get("product_name")), None)
    verified = normalize_verified_seed_treatment_composition(product_name)
    if verified:
        original = next((record.get("active_substances_raw") for record in records or [] if isinstance(record, dict) and record.get("active_substances_raw")), None)
        return {
            "composition": verified,
            "source": "verified_seed_treatment_correction",
            "source_active_substances_raw": original,
            "manual_review_required": False,
            "conflicting_compositions": [],
        }

    for record in records or []:
        for source, composition in seed_treatment_record_composition_candidates(record):
            deduped, repeated = deduplicate_repeated_composition_fragments(composition)
            key = tuple(_active_substance_dedupe_key(s) for s in parse_active_substances(deduped))
            if not key:
                continue
            all_parseable.append((source, deduped, key, repeated))
            seen.add(key)
            if chosen is None or (chosen_source != "active_substances_raw" and source == "active_substances_raw"):
                chosen_source = source
                chosen = deduped
                chosen_original = composition

    manual_review_required = len(seen) > 1
    if manual_review_required:
        conflicts = sorted({_composition_compare_key(item[1]) for item in all_parseable})

    return {
        "composition": chosen,
        "source": chosen_source,
        "source_active_substances_raw": chosen_original if chosen_original != chosen else None,
        "manual_review_required": manual_review_required,
        "conflicting_compositions": conflicts,
    }


def _active_substance_dedupe_key(substance: Dict) -> tuple:
    return (
        normalize_substance_name(substance.get("name", "")),
        substance.get("concentration"),
        substance.get("unit"),
        bool(substance.get("is_antidote")),
        bool(substance.get("concentration_unresolved")),
    )


def _is_known_active_substance_name(name: str) -> bool:
    """Return True when a name is an exact known HRAC/FRAC/IRAC lookup key."""
    try:
        return _is_known_active_substance_name_for_type(name)
    except NameError:
        return False


def _clean_parsed_substance_name(name: str) -> str:
    """Normalize parser output names without guessing unknown substances."""
    cleaned = normalize_composition_text(name).strip(" .()")
    compact_hyphen = re.sub(r"\s*-\s*", "-", cleaned)
    if _is_known_active_substance_name(compact_hyphen):
        return compact_hyphen
    return cleaned


def _split_joined_active_substance_names(name: str) -> List[str]:
    """Split joined active names only when every resulting side is known."""
    return _split_known_joined_name_candidates(name)


def _build_parsed_substance(name: str, concentration: Optional[float], unit: Optional[str], is_antidote: bool, source_fragment: Optional[str] = None) -> Dict:
    substance = {
        "name": name.strip(),
        "concentration": concentration,
        "unit": unit,
        "is_antidote": is_antidote
    }
    if concentration is None:
        substance["concentration_unresolved"] = True
        substance["concentration_note"] = "Концентрация не указана в исходном поле состава"
    if source_fragment:
        substance["source_fragment"] = source_fragment
    return substance


def _parse_active_substances_text(raw: str) -> List[Dict]:
    substances = []

    # Normalize formatting and deduplicate exact repeated composition fragments for parsing only.
    text, _ = deduplicate_repeated_composition_fragments(raw)

    # Remove outer parentheses
    text = text.strip()
    if text.startswith('('):
        text = text[1:]
    if text.endswith(')'):
        text = text[:-1]

    # Split by + to get individual components
    parts = re.split(r'\s*\+\s*', text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if it's an antidote
        is_antidote = 'антидот' in part.lower()

        # Pattern: number unit name
        # e.g., "360 г/л Глифосат кислоты"
        # e.g., "750 г/кг трибенурон-метил"
        # e.g., "10 % имидаклоприд"
        # e.g., "47 г/л антидот - клоквинтосет-мексил"
        match = re.match(rf'(\d+(?:[.,]\d+)?)\s*({SUPPORTED_CONCENTRATION_UNITS_REGEX})\s*(.+)', part)

        if match:
            concentration_str = match.group(1).replace(',', '.')
            unit = match.group(2)
            name = match.group(3).strip()

            # Clean up the name - remove "антидот -" prefix
            name = re.sub(r'^антидот\s*[-–]?\s*', '', name, flags=re.IGNORECASE)
            name = _clean_parsed_substance_name(name)

            # Remove trailing parentheses content that's part of the name
            # Keep it as part of the substance name

            try:
                concentration = float(concentration_str)
            except:
                concentration = 0

            split_names = _split_joined_active_substance_names(name)
            if len(split_names) == 1:
                substances.append(_build_parsed_substance(split_names[0], concentration, unit, is_antidote))
            else:
                for index, split_name in enumerate(split_names):
                    # The source concentration is reliable only for the name that immediately follows it.
                    # Later names in the same joined fragment are real substances, but their separate
                    # concentrations are not present in the canonical composition field.
                    substances.append(_build_parsed_substance(
                        split_name,
                        concentration if index == 0 else None,
                        unit if index == 0 else None,
                        is_antidote,
                        source_fragment=name,
                    ))

    return substances


def parse_active_substances(raw: Optional[str]) -> List[Dict]:
    """
    Parse active substances from canonical composition text only.
    Examples:
    - "(360 г/л Глифосат кислоты (изопропиламинная соль))"
    - "(140 г/л феноксапроп-П-этил + 47 г/л антидот - клоквинтосет-мексил)"
    - "(750 г/кг трибенурон-метил)"

    Returns list of dicts with:
    - name: substance name
    - concentration: numeric value
    - unit: г/л, г/кг, or %
    - is_antidote: whether it's an antidote
    """
    substances = []
    seen_substances = set()

    for composition in _iter_canonical_composition_values(raw):
        for substance in _parse_active_substances_text(composition):
            dedupe_key = _active_substance_dedupe_key(substance)
            if dedupe_key in seen_substances:
                continue
            seen_substances.add(dedupe_key)
            substances.append(substance)

    return substances




def first_parseable_composition(records: Sequence[Dict[str, Any]], pesticide_type: Optional[str] = None) -> Optional[str]:
    """Pick the first non-empty composition that actually parses, then any non-empty value.

    Mongo rows for one product can contain duplicate application rows. Some old imports also
    left the composition blank on a subset of rows, so relying on records[0] or Mongo $first
    can make the product card and compare endpoint lose active substances.
    """
    if (pesticide_type or "").strip().lower() in {"seed-treatment", "seed_treatment", "seed-treatment-mixed"}:
        selected = canonical_seed_treatment_composition(records)
        if selected.get("composition"):
            return selected["composition"]

    fallback = None
    for record in records or []:
        raw = record.get("active_substances_raw") if isinstance(record, dict) else None
        if raw is None:
            continue
        text = str(raw).strip()
        if not text or text.lower() in {"nan", "none", "нет данных"}:
            continue
        if fallback is None:
            fallback = text
        if parse_active_substances(text):
            return text
    return fallback


def with_canonical_composition(record: Dict[str, Any], records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a copy whose active_substances_raw is the safest product-level composition."""
    pesticide_type = record.get("pesticide_type") or ("seed-treatment" if any(r.get("pesticide_type") == "seed-treatment" for r in records or []) else None)
    if pesticide_type is None and normalize_verified_seed_treatment_composition(record.get("product_name")):
        pesticide_type = "seed-treatment"
    selected = canonical_seed_treatment_composition(records) if (pesticide_type or "").strip().lower() in {"seed-treatment", "seed_treatment", "seed-treatment-mixed"} else {}
    canonical = selected.get("composition") or first_parseable_composition(records, pesticide_type)
    result = dict(record)
    if canonical is not None:
        if result.get("active_substances_raw") and result.get("active_substances_raw") != canonical:
            result["source_active_substances_raw"] = result.get("active_substances_raw")
        if selected.get("source_active_substances_raw"):
            result["source_active_substances_raw"] = selected.get("source_active_substances_raw")
        result["active_substances_raw"] = canonical
    if (pesticide_type or "").strip().lower() in {"seed-treatment", "seed_treatment", "seed-treatment-mixed"}:
        result["product_name"] = clean_seed_treatment_display_name(result.get("product_name"))
    return result

def normalize_substance_name(name: str) -> str:
    """Normalize active substance names for safe comparison and lookups."""
    normalized = str(name or "").casefold().replace("ё", "е").replace("\u00a0", " ")
    normalized = re.sub(r"[‐‑‒–—−]", "-", normalized)

    # Remove explanatory parenthetical tails, then trim only punctuation around the name.
    # Internal punctuation such as ``2,4-д`` stays intact because it is part of the substance name.
    normalized = re.sub(r"\s*\(.*?\)\s*", " ", normalized)
    normalized = re.sub(r"^[\s\.,;:!?'\"«»„“”‘’\[\]{}()]+", "", normalized)
    normalized = re.sub(r"[\s\.,;:!?'\"«»„“”‘’\[\]{}()]+$", "", normalized)
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def get_substance_category(name: str) -> str:
    """
    Determine the functional category/mechanism of a substance.
    This is a simplified categorization based on common herbicide groups.
    """
    name_lower = name.lower()
    
    # Hormonal herbicides (auxin-like)
    if any(x in name_lower for x in ['2,4-д', '2,4-d', 'дикамба', 'клопиралид', 'пиклорам', 'аминопиралид']):
        return "Ауксиноподобные (гормональные)"
    
    # ALS inhibitors
    if any(x in name_lower for x in ['сульфонилмочевин', 'трибенурон', 'метсульфурон', 'тифенсульфурон', 
                                      'римсульфурон', 'никосульфурон', 'просульфурон', 'флорасулам',
                                      'имазетапир', 'имазамокс', 'имазапир']):
        return "Ингибиторы ALS (сульфонилмочевины)"
    
    # ACCase inhibitors (graminicides)
    if any(x in name_lower for x in ['феноксапроп', 'хизалофоп', 'галоксифоп', 'клетодим', 
                                      'пиноксаден', 'флуазифоп', 'пропаквизафоп']):
        return "Ингибиторы ACCase (граминициды)"
    
    # Glyphosate
    if 'глифосат' in name_lower:
        return "Глифосаты (EPSP-ингибиторы)"
    
    # PPO inhibitors
    if any(x in name_lower for x in ['карфентразон', 'оксифлуорфен', 'фомесафен', 'лактофен']):
        return "Ингибиторы PPO"
    
    # PSII inhibitors
    if any(x in name_lower for x in ['метрибузин', 'тербутилазин', 'атразин', 'прометрин']):
        return "Ингибиторы фотосистемы II"
    
    # Pre-emergence herbicides
    if any(x in name_lower for x in ['метолахлор', 'с-метолахлор', 'ацетохлор', 'пропизохлор', 'диметенамид']):
        return "Хлорацетамиды (почвенные)"
    
    # HPPD inhibitors
    if any(x in name_lower for x in ['мезотрион', 'темботрион', 'топрамезон', 'изоксафлютол']):
        return "Ингибиторы HPPD"
    
    # Antidotes/safeners
    if any(x in name_lower for x in ['клоквинтосет', 'мефенпир', 'изоксадифен', 'ципросульфамид']):
        return "Антидот (сэйфнер)"
    
    return "Другие"



UNKNOWN_RESISTANCE_GROUP = {
    "system": None,
    "group": None,
    "name": "группа не определена",
}


OLD_HARDCODED_RESISTANCE_GROUP_COUNT = 28


MANUAL_RU_ALIASES = {
    "глифосат": "glyphosate",
    "трибенурон-метил": "tribenuron_methyl",
    "метсульфурон-метил": "metsulfuron_methyl",
    "имазамокс": "imazamox",
    "имазетапир": "imazethapyr",
    "клетодим": "clethodim",
    "хизалофоп-п-этил": "quizalofop_ethyl",
    "2,4-д": "24_d",
    "дикамба": "dicamba",
    "клопиралид": "clopyralid",
    "мезотрион": "mesotrione",
    "метрибузин": "metribuzin",
    "имидаклоприд": "imidacloprid",
    "тиаметоксам": "thiamethoxam",
    "клотианидин": "clothianidin",
    "лямбда-цигалотрин": "lambda_cyhalothrin",
    "альфа-циперметрин": "alpha_cypermethrin",
    "дельтаметрин": "deltamethrin",
    "хлорантранилипрол": "chlorantraniliprole",
    "абамектин": "abamectin",
    "ацетамиприд": "acetamiprid",
    "диметоат": "dimethoate",
    "карбендазим": "carbendazim",
    "тебуконазол": "tebuconazole",
    "дифеноконазол": "difenoconazole",
    "азоксистробин": "azoxystrobin",
    "пираклостробин": "pyraclostrobin",
    "флудиоксонил": "fludioxonil",
    "металаксил-м": "metalaxyl_m",
    # High-confidence aliases from backend/data/unresolved_resistance_aliases_report.csv.
    # These point only to existing HRAC/FRAC/IRAC records and stay scoped by pesticide type below.
    "изоксафлютол": "isoxaflutole",
    "карфентразон-этил": "carfentrazone_ethyl",
    "пендиметалин": "pendimethalin",
    "пиноксаден": "pinoxaden",
    "прометрин": "prometryn",
    "пропаквизафоп": "propaquizafop",
    "с-метолахлор": "s_metolachlor",
    "темботрион": "tembotrione",
    "тербутилазин": "terbuthylazine",
    "флорасулам": "florasulam",
    "изопиразам": "isopyrazam",
    "пидифлуметофен": "pydiflumetofen",
    "фамоксадон": "famoxadone",
    "фенамидон": "fenamidone",
    "фенпропидин": "fenpropidin",
    "цифлуфенамид": "cyflufenamid",
    "бифентрин": "bifenthrin",
    "зета-циперметрин": "zeta_cypermethrin",
    "индоксакарб": "indoxacarb",
    "малатион": "malathion",
    "пиметрозин": "pymetrozine",
    "пиримифос-метил": "pirimiphos_methyl",
    "спиносад": "spinosad",
    "спиротетрамат": "spirotetramat",
    "фипронил": "fipronil",
    "хлорпирифос": "chlorpyrifos",
    "циантранилипрол": "cyantraniliprole",
    "циперметрин": "cypermethrin",
    "эмамектин бензоат": "emamectin_benzoate",
    "эсфенвалерат": "esfenvalerate",
    "пенфлуфен": "penflufen",
}


MANUAL_RU_ALIAS_PESTICIDE_TYPES = {
    "глифосат": ("herbicide",),
    "трибенурон-метил": ("herbicide",),
    "метсульфурон-метил": ("herbicide",),
    "имазамокс": ("herbicide",),
    "имазетапир": ("herbicide",),
    "клетодим": ("herbicide",),
    "хизалофоп-п-этил": ("herbicide",),
    "2,4-д": ("herbicide",),
    "дикамба": ("herbicide",),
    "клопиралид": ("herbicide",),
    "мезотрион": ("herbicide",),
    "метрибузин": ("herbicide",),
    "имидаклоприд": ("insecticide",),
    "тиаметоксам": ("insecticide",),
    "клотианидин": ("insecticide",),
    "лямбда-цигалотрин": ("insecticide",),
    "альфа-циперметрин": ("insecticide",),
    "дельтаметрин": ("insecticide",),
    "хлорантранилипрол": ("insecticide",),
    "абамектин": ("insecticide",),
    "ацетамиприд": ("insecticide",),
    "диметоат": ("insecticide",),
    "карбендазим": ("fungicide",),
    "тебуконазол": ("fungicide",),
    "дифеноконазол": ("fungicide",),
    "азоксистробин": ("fungicide",),
    "пираклостробин": ("fungicide",),
    "флудиоксонил": ("fungicide",),
    "металаксил-м": ("fungicide",),
    "изоксафлютол": ("herbicide",),
    "карфентразон-этил": ("herbicide",),
    "пендиметалин": ("herbicide",),
    "пиноксаден": ("herbicide",),
    "прометрин": ("herbicide",),
    "пропаквизафоп": ("herbicide",),
    "с-метолахлор": ("herbicide",),
    "темботрион": ("herbicide",),
    "тербутилазин": ("herbicide",),
    "флорасулам": ("herbicide",),
    "изопиразам": ("fungicide",),
    "пидифлуметофен": ("fungicide",),
    "фамоксадон": ("fungicide",),
    "фенамидон": ("fungicide",),
    "фенпропидин": ("fungicide",),
    "цифлуфенамид": ("fungicide",),
    "бифентрин": ("insecticide",),
    "зета-циперметрин": ("insecticide",),
    "индоксакарб": ("insecticide",),
    "малатион": ("insecticide",),
    "пиметрозин": ("insecticide",),
    "пиримифос-метил": ("insecticide",),
    "спиносад": ("insecticide",),
    "спиротетрамат": ("insecticide",),
    "фипронил": ("insecticide",),
    "хлорпирифос": ("insecticide",),
    "циантранилипрол": ("insecticide",),
    "циперметрин": ("insecticide",),
    "эмамектин бензоат": ("insecticide",),
    "эсфенвалерат": ("insecticide",),
    "пенфлуфен": ("fungicide",),
}


RESISTANCE_GROUPS_PATH = ROOT_DIR / "data" / "resistance_groups.json"
RESISTANCE_PESTICIDE_TYPES_BY_SYSTEM = {
    "HRAC": "herbicide",
    "FRAC": "fungicide",
    "IRAC": "insecticide",
}


def _resistance_record_to_group_info(record: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {
        "system": record.get("system"),
        "group": record.get("group_code"),
        "name": record.get("group_name") or "группа не определена",
        "effect_summary": record.get("effect_summary"),
    }


def _resistance_lookup_variants(name: str) -> set:
    """Return normalized lookup keys, including an OCR-space-tolerant compact key."""
    normalized = normalize_resistance_lookup_name(name)
    variants = {normalized} if normalized else set()
    compact = re.sub(r"[\s-]+", "", normalized)
    if compact and compact != normalized:
        variants.add(compact)
    return variants


def load_resistance_groups(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load HRAC/FRAC/IRAC records from backend/data/resistance_groups.json and build lookup indexes."""
    data_path = Path(path) if path else RESISTANCE_GROUPS_PATH
    with data_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("resistance_groups.json must contain a records list")

    indexes = {
        "herbicide": {},
        "fungicide": {},
        "insecticide": {},
    }
    record_entries = {
        "herbicide": [],
        "fungicide": [],
        "insecticide": [],
    }

    for record in records:
        if not isinstance(record, dict):
            continue
        pesticide_type = (record.get("pesticide_type") or RESISTANCE_PESTICIDE_TYPES_BY_SYSTEM.get(record.get("system"), "")).strip().lower()
        if pesticide_type not in indexes:
            continue

        group_info = _resistance_record_to_group_info(record)
        entry = {
            "record": record,
            "group_info": group_info,
            "lookup_names": set(),
        }

        for field in ("active_ingredient_ru", "active_ingredient_en", "active_ingredient_key"):
            value = record.get(field)
            if value:
                for normalized in _resistance_lookup_variants(str(value)):
                    entry["lookup_names"].add(normalized)
                    indexes[pesticide_type].setdefault(normalized, group_info)

        # Russian product imports often use Cyrillic active-substance names while HRAC/FRAC/IRAC
        # source records are mostly English. Store those trusted Russian names in JSON so the
        # data file, not Python code, is the primary alias source. Manual aliases below remain a
        # fallback for backward compatibility.
        ru_aliases = record.get("active_ingredient_ru_aliases") or []
        if isinstance(ru_aliases, list):
            for alias in ru_aliases:
                if alias:
                    for normalized in _resistance_lookup_variants(str(alias)):
                        entry["lookup_names"].add(normalized)
                        indexes[pesticide_type].setdefault(normalized, group_info)

        key = record.get("active_ingredient_key")
        if key:
            for underscored in _resistance_lookup_variants(str(key).replace("_", "-")):
                entry["lookup_names"].add(underscored)
                indexes[pesticide_type].setdefault(underscored, group_info)

        record_entries[pesticide_type].append(entry)

    normalized_alias_scopes = {
        normalize_resistance_lookup_name(alias): scopes
        for alias, scopes in MANUAL_RU_ALIAS_PESTICIDE_TYPES.items()
    }
    for russian_name, active_key in MANUAL_RU_ALIASES.items():
        alias_variants = _resistance_lookup_variants(russian_name)
        key_variants = _resistance_lookup_variants(active_key) | _resistance_lookup_variants(active_key.replace("_", "-"))
        allowed_pesticide_types = normalized_alias_scopes.get(
            normalize_resistance_lookup_name(russian_name),
            tuple(indexes),
        )
        for pesticide_type in allowed_pesticide_types:
            table = indexes.get(pesticide_type)
            if not table:
                continue
            group_info = next((table[key] for key in key_variants if key in table), None)
            if group_info:
                for normalized_alias in alias_variants:
                    table[normalized_alias] = group_info

    return {
        "records": records,
        "record_count": len(records),
        "indexes": indexes,
        "record_entries": record_entries,
    }



def normalize_resistance_lookup_name(name: str) -> str:
    """Normalize names before looking them up in exact resistance group tables."""
    normalized = normalize_substance_name(name).replace("ё", "е")
    normalized = re.sub(r"[‐‑‒–—−]", "-", normalized)
    normalized = re.sub(r"\s*[-]\s*", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


RESISTANCE_GROUP_DATA = load_resistance_groups()
RESISTANCE_GROUPS = RESISTANCE_GROUP_DATA["indexes"]


def _lookup_resistance_group_in_table(substance_name: str, pesticide_type: str) -> Optional[Dict[str, Optional[str]]]:
    table = RESISTANCE_GROUPS.get(pesticide_type, {})
    normalized = normalize_resistance_lookup_name(substance_name)
    lookup_variants = _resistance_lookup_variants(substance_name)

    # Exact lookup order: Russian name, English name, active ingredient key, and manual Russian aliases
    # are all indexed by load_resistance_groups(). Think of this as a fast dictionary: one normalized
    # name points to one HRAC/FRAC/IRAC record.
    for lookup_name in lookup_variants:
        if lookup_name in table:
            return table[lookup_name]

    # Safe partial matching: accept a match only if exactly one JSON/alias key is found as a full
    # token/phrase inside parser leftovers such as "глифосат кислоты". If two records match, we
    # return unknown instead of guessing.
    matches = []
    seen = set()
    compact_normalized = re.sub(r"[\s-]+", "", normalized)
    for known_name, group_info in table.items():
        known_normalized = normalize_resistance_lookup_name(known_name)
        pattern = rf"(?<![а-яa-z0-9]){re.escape(known_normalized)}(?![а-яa-z0-9])"
        compact_known = re.sub(r"[\s-]+", "", known_normalized)
        compact_match = compact_known and compact_known in compact_normalized
        if re.search(pattern, normalized, re.IGNORECASE) or compact_match:
            key = (group_info.get("system"), group_info.get("group"), group_info.get("name"))
            if key not in seen:
                seen.add(key)
                matches.append(group_info)

    if len(matches) == 1:
        return matches[0]

    return None


def get_resistance_group(substance_name: str, pesticide_type: str) -> Dict[str, Optional[str]]:
    """Return HRAC/FRAC/IRAC group data for a known active substance without guessing."""
    if not substance_name:
        return UNKNOWN_RESISTANCE_GROUP.copy()

    pesticide_type = (pesticide_type or "").strip().lower()

    if pesticide_type in {"seed-treatment", "seed_treatment", "seed-treatment-mixed"}:
        # Seed treatments may combine fungicide and insecticide active substances.
        for lookup_type in ("fungicide", "insecticide"):
            group_info = _lookup_resistance_group_in_table(substance_name, lookup_type)
            if group_info:
                return group_info.copy()
        return UNKNOWN_RESISTANCE_GROUP.copy()

    group_info = _lookup_resistance_group_in_table(substance_name, pesticide_type)
    if group_info:
        return group_info.copy()

    return UNKNOWN_RESISTANCE_GROUP.copy()


def get_resistance_lookup_diagnostics(substance_names: Sequence[str], pesticide_type: str) -> Dict[str, Any]:
    """Report which active substance names resolve to resistance groups and which stay unknown."""
    checked = []
    unresolved = []
    for substance_name in substance_names:
        group_info = get_resistance_group(substance_name, pesticide_type)
        result = {
            "substance_name": substance_name,
            "resolved": group_info.get("name") != UNKNOWN_RESISTANCE_GROUP["name"],
            "system": group_info.get("system"),
            "group": group_info.get("group"),
            "resistance_group_name": group_info.get("name"),
        }
        checked.append(result)
        if not result["resolved"]:
            unresolved.append(substance_name)

    return {
        "pesticide_type": pesticide_type,
        "checked": checked,
        "unresolved": unresolved,
    }


def annotate_substances_with_resistance(substances: List[Dict], pesticide_type: str) -> List[Dict]:
    """Add resistance group fields to parsed substances while keeping existing fields intact."""
    annotated = []
    for substance in substances:
        group_info = get_resistance_group(substance.get("name", ""), pesticide_type)
        annotated.append({
            **substance,
            "resistance_system": group_info["system"],
            "resistance_group": group_info["group"],
            "resistance_group_name": group_info["name"],
            "effect_summary": group_info.get("effect_summary"),
        })
    return annotated


def _substance_names_match(left_name: str, right_name: str) -> bool:
    left_norm = normalize_substance_name(left_name)
    right_norm = normalize_substance_name(right_name)
    return bool(left_norm and right_norm and left_norm == right_norm)


def _known_group_key(substance: Dict) -> Optional[tuple]:
    system = substance.get("resistance_system")
    group = substance.get("resistance_group")
    if not system or not group:
        return None
    return (system, group)


def _active_substance_name_set(substances: List[Dict]) -> set:
    return {normalize_substance_name(s.get("name", "")) for s in substances if s.get("name")}


def _resistance_reference_groups(substances: List[Dict]) -> List[Dict[str, Optional[str]]]:
    references = []
    seen = set()
    for substance in substances:
        key = (
            normalize_substance_name(substance.get("name", "")),
            substance.get("resistance_system"),
            substance.get("resistance_group"),
        )
        if key in seen:
            continue
        seen.add(key)
        references.append({
            "substance": substance.get("name"),
            "system": substance.get("resistance_system"),
            "group": substance.get("resistance_group"),
            "group_name": substance.get("resistance_group_name") or "группа не определена",
            "effect_summary": substance.get("effect_summary"),
            "message": (
                f"{substance.get('resistance_system')} {substance.get('resistance_group')} — {substance.get('resistance_group_name')}"
                if substance.get("resistance_system") and substance.get("resistance_group")
                else "группа не определена"
            ),
        })
    return references


def build_resistance_group_analysis(left_active: List[Dict], right_active: List[Dict]) -> Dict[str, Any]:
    """Compare resistance groups as neutral product information, not agronomic advice."""
    unknown_group_substances = []
    seen_unknown = set()

    for side, substances in (("left", left_active), ("right", right_active)):
        for substance in substances:
            if not substance.get("resistance_system") or not substance.get("resistance_group"):
                key = (side, substance.get("name"))
                if key not in seen_unknown:
                    unknown_group_substances.append({
                        "side": side,
                        "substance": substance.get("name"),
                        "message": "группа не определена",
                    })
                    seen_unknown.add(key)

    reference_groups = {
        "left": _resistance_reference_groups(left_active),
        "right": _resistance_reference_groups(right_active),
    }
    left_names = _active_substance_name_set(left_active)
    right_names = _active_substance_name_set(right_active)
    identical_sets = bool(left_names or right_names) and left_names == right_names

    if identical_sets:
        return {
            "same_group_matches": [],
            "different_group_matches": [],
            "unknown_group_substances": unknown_group_substances,
            "reference_groups": reference_groups,
            "identical_active_substance_sets": True,
            "plain_explanation": "Действующие вещества совпадают. Группы устойчивости указаны справочно.",
        }

    same_group_bucket = {}
    different_group_matches = []
    seen_different = set()

    for left_substance in left_active:
        for right_substance in right_active:
            if _substance_names_match(left_substance.get("name", ""), right_substance.get("name", "")):
                continue

            left_key = _known_group_key(left_substance)
            right_key = _known_group_key(right_substance)
            if not left_key or not right_key:
                continue

            left_system, left_group = left_key
            right_system, right_group = right_key

            if left_key == right_key:
                bucket_key = (
                    left_system,
                    left_group,
                    left_substance.get("resistance_group_name"),
                    left_substance.get("effect_summary") or right_substance.get("effect_summary"),
                )
                bucket = same_group_bucket.setdefault(bucket_key, {"left": set(), "right": set()})
                bucket["left"].add(left_substance.get("name"))
                bucket["right"].add(right_substance.get("name"))
            else:
                pair_key = (left_substance.get("name"), left_system, left_group, right_substance.get("name"), right_system, right_group)
                if pair_key not in seen_different:
                    different_group_matches.append({
                        "left_substance": left_substance.get("name"),
                        "left_group": f"{left_system} {left_group}",
                        "right_substance": right_substance.get("name"),
                        "right_group": f"{right_system} {right_group}",
                        "message": "Действующие вещества и группы устойчивости разные.",
                    })
                    seen_different.add(pair_key)

    same_group_matches = [
        {
            "system": system,
            "group": group,
            "group_name": group_name,
            "effect_summary": effect_summary,
            "left_substances": sorted(names["left"]),
            "right_substances": sorted(names["right"]),
            "warning": "Действующие вещества разные, но группа устойчивости одна. По механизму действия препараты близки.",
        }
        for (system, group, group_name, effect_summary), names in same_group_bucket.items()
    ]

    if same_group_matches:
        plain_explanation = "Действующие вещества разные, но группа устойчивости одна. По механизму действия препараты близки."
    elif different_group_matches:
        plain_explanation = "Действующие вещества и группы устойчивости разные."
    elif unknown_group_substances:
        plain_explanation = "Для части действующих веществ группа не определена."
    else:
        plain_explanation = "Группы устойчивости указаны справочно."

    return {
        "same_group_matches": same_group_matches,
        "different_group_matches": different_group_matches,
        "unknown_group_substances": unknown_group_substances,
        "reference_groups": reference_groups,
        "identical_active_substance_sets": False,
        "plain_explanation": plain_explanation,
    }

SUPPORTED_RATE_UNITS = {"л/га", "л/т", "кг/га", "кг/т", "г/га", "г/т", "мл/га", "мл/т"}
NORMALIZED_RATE_UNITS = {
    "г/га": ("кг/га", 1000),
    "г/т": ("кг/т", 1000),
    "мл/га": ("л/га", 1000),
    "мл/т": ("л/т", 1000),
}
RATE_UNIT_REGEX = re.compile(r"(мл|л|кг|г)\s*/\s*(га|т)", flags=re.IGNORECASE)


def normalize_rate_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    compact_unit = re.sub(r"\s+", "", unit.lower().replace("ё", "е"))
    return compact_unit if compact_unit in SUPPORTED_RATE_UNITS else None


def normalize_rate_value(rate: float, unit: Optional[str]) -> tuple[float, Optional[str]]:
    normalized_unit = normalize_rate_unit(unit)
    if normalized_unit in NORMALIZED_RATE_UNITS:
        target_unit, divisor = NORMALIZED_RATE_UNITS[normalized_unit]
        return rate / divisor, target_unit
    return rate, normalized_unit


def parse_rate_max_with_unit(rate_raw: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """Parse max application rate and normalize small units to kg or l units."""
    if not rate_raw:
        return None, None

    numbers = re.findall(r"(\d+(?:[.,]\d+)?)", rate_raw)
    if not numbers:
        return None, None

    rates = []
    for number in numbers:
        try:
            rates.append(float(number.replace(",", ".")))
        except ValueError:
            pass

    if not rates:
        return None, None

    unit_match = RATE_UNIT_REGEX.search(rate_raw)
    raw_unit = f"{unit_match.group(1).lower()}/{unit_match.group(2).lower()}" if unit_match else None
    return normalize_rate_value(max(rates), raw_unit)


def parse_rate_max(rate_raw: Optional[str]) -> Optional[float]:
    """Backward-compatible helper that returns only the numeric max application rate."""
    rate, _unit = parse_rate_max_with_unit(rate_raw)
    return rate


def select_comparison_rate(
    manual_rate: Optional[float],
    registered_rate: Optional[float],
    registered_unit: Optional[str],
) -> tuple[Optional[float], Optional[str], str]:
    """Use manual numeric rate with the registered normalized unit, otherwise use registered rate."""
    if manual_rate is not None:
        return manual_rate, registered_unit, "manual"
    return registered_rate, registered_unit, "max_registered"


def get_max_registered_rate(records: List[Dict]) -> tuple[Optional[float], Optional[str]]:
    rates = []
    for record in records:
        parsed_rate, parsed_unit = parse_rate_max_with_unit(record.get("rate_raw"))
        if parsed_rate is not None:
            rates.append((parsed_rate, parsed_unit))
    return max(rates, key=lambda item: item[0], default=(None, None))


def normalize_concentration_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    compact_unit = re.sub(r"\s+", "", unit.lower().replace("ё", "е"))
    return compact_unit if compact_unit in {"г/кг", "г/л"} else None


def calculate_active_amount(concentration: Optional[float], concentration_unit: Optional[str], rate_used: Optional[float], rate_unit: Optional[str]) -> Optional[float]:
    """Calculate active substance amount for compatible concentration and rate units."""
    if concentration is None or rate_used is None:
        return None

    normalized_concentration_unit = normalize_concentration_unit(concentration_unit)
    normalized_rate_unit = normalize_rate_unit(rate_unit)

    # Backward compatibility for old rows that had no application unit parsed.
    if normalized_rate_unit is None:
        return concentration * rate_used

    if normalized_concentration_unit == "г/кг" and normalized_rate_unit.startswith("кг/"):
        return concentration * rate_used
    if normalized_concentration_unit == "г/л" and normalized_rate_unit.startswith("л/"):
        return concentration * rate_used

    return None


def calculate_total_active_amount(substances: List[Dict], rate_used: Optional[float], rate_unit: Optional[str]) -> Optional[float]:
    amounts = [
        calculate_active_amount(substance.get("concentration"), substance.get("unit"), rate_used, rate_unit)
        for substance in substances
    ]
    compatible_amounts = [amount for amount in amounts if amount is not None]
    if not compatible_amounts:
        return None
    return sum(compatible_amounts)


def build_substance_cost_breakdown(
    side: str,
    substances: List[Dict],
    price: Optional[float],
    rate_used: Optional[float],
    rate_unit: Optional[str],
) -> List[Dict[str, Any]]:
    """Estimate full-treatment cost per gram for each active substance separately."""
    if not price or not rate_used:
        return []

    breakdown = []
    total_cost_per_ha = price * rate_used

    for substance in substances:
        concentration = substance.get("concentration")
        if concentration is None or concentration <= 0:
            continue

        grams_per_ha = calculate_active_amount(concentration, substance.get("unit"), rate_used, rate_unit)
        if grams_per_ha is None or grams_per_ha <= 0:
            continue

        # Do not split treatment cost between components. This metric means:
        # full treatment cost per hectare / grams of this substance delivered per hectare.
        estimated_cost_per_gram = total_cost_per_ha / grams_per_ha

        breakdown.append({
            "side": side,
            "substance_name": substance.get("name"),
            "name": substance.get("name"),  # Backward-friendly alias for existing frontend code.
            "concentration": concentration,
            "unit": substance.get("unit"),
            "rate_used": rate_used,
            "rate_unit": rate_unit,
            "grams_per_ha": round(grams_per_ha, 4),
            # Preserved for API compatibility only. The new calculation no longer allocates
            # a misleading proportional per-substance cost share.
            "estimated_cost_share_per_ha": None,
            "estimated_cost_per_gram": round(estimated_cost_per_gram, 6),
        })

    return breakdown


def sum_known_concentrations(substances: List[Dict]) -> float:
    return sum(
        substance.get("concentration") or 0
        for substance in substances
        if substance.get("concentration") is not None
    )


def concentration_difference(left_substance: Dict, right_substance: Dict) -> Optional[float]:
    left_concentration = left_substance.get("concentration")
    right_concentration = right_substance.get("concentration")
    if left_concentration is None or right_concentration is None:
        return None
    return abs(left_concentration - right_concentration)


def build_price_analysis(
    left_price: Optional[float],
    right_price: Optional[float],
    left_rate_used: Optional[float],
    right_rate_used: Optional[float],
    left_rate_unit: Optional[str],
    right_rate_unit: Optional[str],
    left_active: List[Dict],
    right_active: List[Dict],
) -> Optional[Dict[str, Any]]:
    if not left_price and not right_price:
        return None

    left_total_concentration = sum_known_concentrations(left_active)
    right_total_concentration = sum_known_concentrations(right_active)
    left_substances_cost = build_substance_cost_breakdown("left", left_active, left_price, left_rate_used, left_rate_unit)
    right_substances_cost = build_substance_cost_breakdown("right", right_active, right_price, right_rate_used, right_rate_unit)

    return {
        "left_price_per_unit": left_price,
        "right_price_per_unit": right_price,
        "left_cost_per_ha": round(left_price * left_rate_used, 2) if left_price and left_rate_used else None,
        "right_cost_per_ha": round(right_price * right_rate_used, 2) if right_price and right_rate_used else None,
        # Kept for compatibility, but frontend now highlights per-substance costs for multi-component products.
        "left_cost_per_gram_ai": round(left_price / left_total_concentration, 4) if left_price and left_total_concentration > 0 else None,
        "right_cost_per_gram_ai": round(right_price / right_total_concentration, 4) if right_price and right_total_concentration > 0 else None,
        "left_substances_cost": left_substances_cost,
        "right_substances_cost": right_substances_cost,
        "substances_cost": left_substances_cost + right_substances_cost,
    }


def normalize_crop_for_registration(crop: Optional[str]) -> str:
    return normalize_search_text(crop or "")


def normalize_crop_compact_for_registration(crop: Optional[str]) -> str:
    """Normalize crop text for direct comparisons across OCR/PDF spacing issues."""
    return normalize_crop_for_registration(crop).replace(" ", "")


CROP_REGISTRATION_ENDINGS = (
    "иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ая", "яя", "ое", "ее",
    "ые", "ие", "ый", "ий", "ой", "ую", "юю", "ом", "ем", "ах", "ях",
    "ов", "ев", "ей", "ам", "ям", "ою", "ею", "а", "я", "ы", "и",
    "у", "ю", "е", "о", "ь",
)


def crop_registration_stems(crop: Optional[str]) -> set[str]:
    """Return tolerant crop forms for registration checks, including inflected Russian words."""
    normalized = normalize_crop_for_registration(crop)
    if not normalized:
        return set()

    forms = {normalized.replace(" ", "")}
    for token in normalized.split():
        compact_token = token.replace(" ", "")
        if len(compact_token) < 3:
            continue
        forms.add(compact_token)
        for ending in CROP_REGISTRATION_ENDINGS:
            if compact_token.endswith(ending) and len(compact_token) - len(ending) >= 3:
                forms.add(compact_token[: -len(ending)])
                break
    return forms


def has_crop_registration(records: List[Dict], crop: Optional[str]) -> bool:
    target_forms = crop_registration_stems(crop)
    if not target_forms:
        return False

    for record in records:
        record_forms = crop_registration_stems(str(record.get("crop") or ""))
        if not record_forms:
            continue

        if any(
            target_form == record_form
            or target_form in record_form
            or record_form in target_form
            for target_form in target_forms
            for record_form in record_forms
        ):
            return True

    return False


def build_crop_registration(crop: Optional[str], left_records: List[Dict], right_records: List[Dict]) -> Optional[Dict[str, Any]]:
    normalized_crop = (crop or "").strip()
    if not normalized_crop:
        return None

    left_has_registration = has_crop_registration(left_records, normalized_crop)
    right_has_registration = has_crop_registration(right_records, normalized_crop)

    return {
        "crop": normalized_crop,
        "left": {
            "has_registration": left_has_registration,
            "message": "Есть регистрация на выбранную культуру" if left_has_registration else "Нет регистрации на выбранную культуру",
        },
        "right": {
            "has_registration": right_has_registration,
            "message": "Есть регистрация на выбранную культуру" if right_has_registration else "Нет регистрации на выбранную культуру",
        },
    }


async def build_advanced_compare_response(
    request: AdvancedCompareRequest,
    collection,
    pesticide_type: str,
    left_not_found: str = "Left product not found",
    right_not_found: str = "Right product not found",
) -> Dict[str, Any]:
    """Build one advanced comparison response while endpoint URLs remain unchanged."""
    left_records = await collection.find({"product_key": request.left_key}).to_list(length=1000)
    right_records = await collection.find({"product_key": request.right_key}).to_list(length=1000)

    if not left_records:
        raise HTTPException(status_code=404, detail=left_not_found)
    if not right_records:
        raise HTTPException(status_code=404, detail=right_not_found)

    left_first = with_canonical_composition(left_records[0], left_records)
    right_first = with_canonical_composition(right_records[0], right_records)

    left_substances = parse_active_substances(left_first.get("active_substances_raw"))
    right_substances = parse_active_substances(right_first.get("active_substances_raw"))

    left_active = [s for s in left_substances if not s["is_antidote"]]
    right_active = [s for s in right_substances if not s["is_antidote"]]

    left_antidotes = annotate_substances_with_resistance([s for s in left_substances if s["is_antidote"]], pesticide_type)
    right_antidotes = annotate_substances_with_resistance([s for s in right_substances if s["is_antidote"]], pesticide_type)
    left_active = annotate_substances_with_resistance(left_active, pesticide_type)
    right_active = annotate_substances_with_resistance(right_active, pesticide_type)

    left_max_rate, left_max_rate_unit = get_max_registered_rate(left_records)
    right_max_rate, right_max_rate_unit = get_max_registered_rate(right_records)
    left_rate_used, left_rate_unit, left_rate_source = select_comparison_rate(request.left_rate, left_max_rate, left_max_rate_unit)
    right_rate_used, right_rate_unit, right_rate_source = select_comparison_rate(request.right_rate, right_max_rate, right_max_rate_unit)

    identical_substances = []
    similar_by_category = []

    for left_substance in left_active:
        left_name_norm = normalize_substance_name(left_substance["name"])
        for right_substance in right_active:
            right_name_norm = normalize_substance_name(right_substance["name"])
            if left_name_norm == right_name_norm:
                left_per_ha = (calculate_active_amount(left_substance["concentration"], left_substance.get("unit"), left_rate_used, left_rate_unit)) if left_rate_used else None
                right_per_ha = (calculate_active_amount(right_substance["concentration"], right_substance.get("unit"), right_rate_used, right_rate_unit)) if right_rate_used else None
                identical_substances.append({
                    "name": left_substance["name"],
                    "left_concentration": left_substance["concentration"],
                    "right_concentration": right_substance["concentration"],
                    "left_unit": left_substance["unit"],
                    "right_unit": right_substance["unit"],
                    "left_per_ha": round(left_per_ha, 2) if left_per_ha else None,
                    "right_per_ha": round(right_per_ha, 2) if right_per_ha else None,
                    "concentration_diff": (
                        round(concentration_difference(left_substance, right_substance), 2)
                        if concentration_difference(left_substance, right_substance) is not None else None
                    ),
                    "same_concentration": (
                        concentration_difference(left_substance, right_substance) < 0.01
                        if concentration_difference(left_substance, right_substance) is not None else False
                    ),
                    "resistance_system": left_substance.get("resistance_system") or right_substance.get("resistance_system"),
                    "resistance_group": left_substance.get("resistance_group") or right_substance.get("resistance_group"),
                    "resistance_group_name": left_substance.get("resistance_group_name") or right_substance.get("resistance_group_name"),
                    "effect_summary": left_substance.get("effect_summary") or right_substance.get("effect_summary"),
                })

    left_categories = {get_substance_category(s["name"]): s for s in left_active}
    right_categories = {get_substance_category(s["name"]): s for s in right_active}
    for category in set(left_categories.keys()) & set(right_categories.keys()):
        if category != "Другие":
            left_cat_subs = [s for s in left_active if get_substance_category(s["name"]) == category]
            right_cat_subs = [s for s in right_active if get_substance_category(s["name"]) == category]
            if not any(_substance_names_match(l["name"], r["name"]) for l in left_cat_subs for r in right_cat_subs):
                similar_by_category.append({
                    "category": category,
                    "left_substances": [{"name": s["name"], "concentration": s["concentration"], "unit": s["unit"]} for s in left_cat_subs],
                    "right_substances": [{"name": s["name"], "concentration": s["concentration"], "unit": s["unit"]} for s in right_cat_subs],
                    "note": "Разные действующие вещества одной функциональной группы"
                })

    left_unique = []
    for substance in left_active:
        name_norm = normalize_substance_name(substance["name"])
        if not any(
            name_norm == normalize_substance_name(item["name"])
            for item in identical_substances
        ):
            per_ha = (calculate_active_amount(substance["concentration"], substance.get("unit"), left_rate_used, left_rate_unit)) if left_rate_used else None
            left_unique.append({
                **substance,
                "category": get_substance_category(substance["name"]),
                "per_ha": round(per_ha, 2) if per_ha else None,
            })

    right_unique = []
    for substance in right_active:
        name_norm = normalize_substance_name(substance["name"])
        if not any(
            name_norm == normalize_substance_name(item["name"])
            for item in identical_substances
        ):
            per_ha = (calculate_active_amount(substance["concentration"], substance.get("unit"), right_rate_used, right_rate_unit)) if right_rate_used else None
            right_unique.append({
                **substance,
                "category": get_substance_category(substance["name"]),
                "per_ha": round(per_ha, 2) if per_ha else None,
            })

    left_total_concentration = sum_known_concentrations(left_active)
    right_total_concentration = sum_known_concentrations(right_active)
    left_total_per_ha = calculate_total_active_amount(left_active, left_rate_used, left_rate_unit)
    right_total_per_ha = calculate_total_active_amount(right_active, right_rate_used, right_rate_unit)

    group_analysis = build_resistance_group_analysis(left_active, right_active)
    price_analysis = build_price_analysis(
        request.left_price,
        request.right_price,
        left_rate_used,
        right_rate_used,
        left_rate_unit,
        right_rate_unit,
        left_active,
        right_active,
    )
    crop_registration = build_crop_registration(request.crop, left_records, right_records)

    analysis = {
        "identical_substances": identical_substances,
        "similar_by_category": similar_by_category,
        "left_unique_substances": left_unique,
        "right_unique_substances": right_unique,
    }
    response = {
        "left": {
            "product_key": left_first.get("product_key"),
            "product_name": left_first.get("product_name"),
            "display_product_name": left_first.get("product_name"),
            "raw_product_name": left_records[0].get("product_name"),
            "formulation": left_first.get("formulation"),
            "active_substances_raw": left_first.get("active_substances_raw"),
            "source_active_substances_raw": left_first.get("source_active_substances_raw"),
            "active_substances": left_active,
            **build_composition_metadata(left_first.get("active_substances_raw"), pesticide_type),
            **manufacturer_response_fields(left_first, left_records),
            "registration_status": left_first.get("registration_status"),
            "max_rate": left_max_rate,
            "max_rate_unit": left_max_rate_unit,
            "rate_used": left_rate_used,
            "rate_unit": left_rate_unit,
            "rate_source": left_rate_source,
            "substances": left_active,
            "antidotes": left_antidotes,
            "total_concentration": left_total_concentration,
            "total_per_ha": round(left_total_per_ha, 2) if left_total_per_ha else None,
            "substance_count": len(left_active),
        },
        "right": {
            "product_key": right_first.get("product_key"),
            "product_name": right_first.get("product_name"),
            "display_product_name": right_first.get("product_name"),
            "raw_product_name": right_records[0].get("product_name"),
            "formulation": right_first.get("formulation"),
            "active_substances_raw": right_first.get("active_substances_raw"),
            "source_active_substances_raw": right_first.get("source_active_substances_raw"),
            "active_substances": right_active,
            **build_composition_metadata(right_first.get("active_substances_raw"), pesticide_type),
            **manufacturer_response_fields(right_first, right_records),
            "registration_status": right_first.get("registration_status"),
            "max_rate": right_max_rate,
            "max_rate_unit": right_max_rate_unit,
            "rate_used": right_rate_used,
            "rate_unit": right_rate_unit,
            "rate_source": right_rate_source,
            "substances": right_active,
            "antidotes": right_antidotes,
            "total_concentration": right_total_concentration,
            "total_per_ha": round(right_total_per_ha, 2) if right_total_per_ha else None,
            "substance_count": len(right_active),
        },
        "analysis": analysis,
        "identical_substances": identical_substances,
        "similar_by_category": similar_by_category,
        "left_unique_substances": left_unique,
        "right_unique_substances": right_unique,
        "group_analysis": group_analysis,
        "price_analysis": price_analysis,
    }
    if crop_registration:
        response["crop_registration"] = crop_registration
    return response


def build_seed_treatment_display_record(record: Dict[str, Any], records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Build safe seed-treatment response fields from the same canonical source.

    MongoDB keeps the imported raw product name unchanged. API responses, however,
    should show a clean product title and expose parsed composition so the frontend
    does not have to parse display strings.
    """
    base = with_canonical_composition(record or {}, records or [])
    canonical_raw = base.get("active_substances_raw")
    substances = parse_active_substances(canonical_raw)
    metadata = build_composition_metadata(canonical_raw, "seed-treatment")
    return {
        "raw_product_name": (record or {}).get("product_name"),
        "product_name": clean_seed_treatment_display_name(base.get("product_name")),
        "display_product_name": clean_seed_treatment_display_name(base.get("product_name")),
        "active_substances_raw": canonical_raw,
        "source_active_substances_raw": base.get("source_active_substances_raw"),
        "active_substances": substances,
        "substances": substances,
        "substance_count": len([s for s in substances if not s.get("is_antidote")]),
        **metadata,
    }



def build_seed_treatment_search_response(grouped_record: Dict[str, Any]) -> Dict[str, Any]:
    """Build one /api/seed-treatments/search item from the aggregation row."""
    r = grouped_record
    return {
        "product_key": r["_id"],
        **build_seed_treatment_display_record(
            {
                "product_name": r.get("product_name"),
                "active_substances_raw": None,
                "pesticide_type": "seed-treatment",
            },
            build_seed_treatment_search_records(r),
        ),
        "formulation": r.get("formulation"),
        "manufacturer": r.get("manufacturer"),
        "registrant": next((v for v in r.get("registrant", []) if v), None),
        "producer": next((v for v in r.get("producer", []) if v), None),
        "company": next((v for v in r.get("company", []) if v), None),
        "applicant": next((v for v in r.get("applicant", []) if v), None),
        "registration_holder": next((v for v in r.get("registration_holder", []) if v), None),
        "registrant_name": next((v for v in r.get("registrant_name", []) if v), None),
        "manufacturer_name": next((v for v in r.get("manufacturer_name", []) if v), None),
        "producer_name": next((v for v in r.get("producer_name", []) if v), None),
        "organization": next((v for v in r.get("organization", []) if v), None),
        "registrant_organization": next((v for v in r.get("registrant_organization", []) if v), None),
        "certificate_holder": next((v for v in r.get("certificate_holder", []) if v), None),
        "display_manufacturer": get_display_manufacturer({**r, "manufacturer": next((v for v in r.get("all_manufacturers", []) if v), r.get("manufacturer"))}),
        "registration_status": r.get("registration_status"),
        "pesticide_type": r.get("pesticide_type"),
        "applications_count": r.get("applications_count", 0),
    }


def build_seed_treatment_search_records(grouped_record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recreate product-level composition candidates from an aggregation result."""
    records = []
    product_name = grouped_record.get("product_name") if isinstance(grouped_record, dict) else None
    for value in (grouped_record.get("active_substances_raw_values", []) if isinstance(grouped_record, dict) else []):
        records.append({
            "product_name": product_name,
            "active_substances_raw": value,
            "pesticide_type": "seed-treatment",
        })
    # Always include product_name as its own candidate. This covers rows where
    # active_substances_raw is blank but the imported title contains composition.
    records.append({
        "product_name": product_name,
        "active_substances_raw": None,
        "pesticide_type": "seed-treatment",
    })
    return records


# ==================== HELPER FUNCTIONS ====================


def clean_value(val) -> Optional[str]:
    """Clean and normalize a value from Excel"""
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if val_str.lower() in ['nan', 'none', '']:
        return None
    return val_str


def clean_record_id(val) -> Optional[Any]:
    """Clean Excel record identifiers without forcing text IDs to integers."""
    cleaned = clean_value(val)
    if cleaned is None:
        return None
    try:
        numeric = float(cleaned)
        if numeric.is_integer():
            return int(numeric)
    except (TypeError, ValueError):
        pass
    return cleaned


def first_clean_value(row, columns: Sequence[str]) -> Optional[str]:
    """Return the first non-empty Excel value from a list of possible column names."""
    for column in columns:
        value = clean_value(row.get(column))
        if value:
            return value
    return None


def create_product_key(product_name: str, registration_number: Optional[str]) -> str:
    """Create a unique product key from name and registration number"""
    name = (product_name or "").strip()
    reg_num = (registration_number or "").strip()
    return f"{name}|{reg_num}"


def is_active_status(status: Optional[str]) -> bool:
    """Check if a registration status is active"""
    if not status:
        return False
    status_lower = status.lower().strip()
    return status_lower == "действует"


# ==================== ENDPOINTS ====================

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        await db.command("ping")
        records_count = await db.herbicide_records.count_documents({})
        return {
            "status": "healthy",
            "database": "connected",
            "records_count": records_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@api_router.post("/admin/import-excel")
async def import_excel(file: UploadFile = File(...)):
    """Import herbicide data from Excel file"""
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents), sheet_name='herbicides_raw', header=3)
        
        await db.herbicide_records.delete_many({})
        
        records = []
        for idx, row in df.iterrows():
            product_name = clean_value(row.get('product_name'))
            if not product_name:
                continue
            
            registration_number = clean_value(row.get('registration_number'))
            product_key = create_product_key(product_name, registration_number)
            
            record = {
                "id": str(uuid.uuid4()),
                "record_id": clean_record_id(row.get('record_id')),
                "product_name": product_name,
                "product_key": product_key,
                "formulation": clean_value(row.get('formulation')),
                "active_substances_raw": clean_value(row.get('active_substances_raw')),
                "manufacturer": clean_value(row.get('manufacturer')),
                "registrant": clean_value(row.get('registrant')),
                "producer": clean_value(row.get('producer')),
                "company": clean_value(row.get('company')),
                "applicant": clean_value(row.get('applicant')),
                "registration_holder": clean_value(row.get('registration_holder')),
                "registrant_name": clean_value(row.get('registrant_name')),
                "manufacturer_name": clean_value(row.get('manufacturer_name')),
                "producer_name": clean_value(row.get('producer_name')),
                "organization": clean_value(row.get('organization')),
                "registrant_organization": clean_value(row.get('registrant_organization')),
                "certificate_holder": clean_value(row.get('certificate_holder')),
                "registration_number": registration_number,
                "registration_start_date": clean_value(row.get('registration_start_date')),
                "registration_end_date": clean_value(row.get('registration_end_date')),
                "registration_status": clean_value(row.get('registration_status')),
                "rate_raw": clean_value(row.get('rate_raw')),
                "crop": clean_value(row.get('crop')),
                "target_object": first_clean_value(row, TARGET_OBJECT_IMPORT_COLUMNS),
                "application_method": clean_value(row.get('application_method')),
                "waiting_period": clean_value(row.get('waiting_period')),
                "reentry_period_manual": clean_value(row.get('reentry_period_manual')),
                "reentry_period_mech": clean_value(row.get('reentry_period_mech')),
                "restrictions": clean_value(row.get('restrictions')),
                "source_page": clean_value(row.get('source_page')),
                "source_type": clean_value(row.get('source_type')),
                "notes": clean_value(row.get('notes')),
                "created_at": datetime.utcnow()
            }
            records.append(record)
        
        if records:
            await db.herbicide_records.insert_many(records)
        
        import_batch = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "records_imported": len(records),
            "import_date": datetime.utcnow(),
            "status": "completed"
        }
        await db.import_batches.insert_one(import_batch)
        
        unique_products = await db.herbicide_records.distinct("product_key")
        
        return {
            "message": "Import successful",
            "records_imported": len(records),
            "unique_products": len(unique_products),
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/herbicides/search", response_model=List[SearchResult])
async def search_herbicides(
    culture: str = Query(default="", description="Filter by culture/crop"),
    harmful_object: str = Query(default="", description="Filter by target object"),
    crop: str = Query(default="", description="Deprecated alias for culture"),
    q: str = Query(default="", description="Search query"),
    only_active: bool = Query(default=False, description="Show only active registrations"),
    limit: int = Query(default=50, le=200, description="Maximum results")
):
    """Search herbicides by name, crop, target, or active substances"""
    try:
        pipeline = []

        registration_filters = build_registration_filters(culture, crop, harmful_object)
        if registration_filters:
            pipeline.append({"$match": registration_filters})
        
        if q and q.strip():
            search_match = build_search_match(q)
            if search_match:
                pipeline.append({"$match": search_match})

        if only_active:
            pipeline.append({"$match": {"registration_status": "Действует"}})
        
        pipeline.extend([
            {
                "$group": {
                    "_id": "$product_key",
                    "product_name": {"$first": "$product_name"},
                    "formulation": {"$first": "$formulation"},
                    "active_substances_raw_values": {"$addToSet": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
                    "registrant": {"$push": "$registrant"},
                    "producer": {"$push": "$producer"},
                    "company": {"$push": "$company"},
                    "applicant": {"$push": "$applicant"},
                    "registration_holder": {"$push": "$registration_holder"},
                    "registrant_name": {"$push": "$registrant_name"},
                    "manufacturer_name": {"$push": "$manufacturer_name"},
                    "producer_name": {"$push": "$producer_name"},
                    "organization": {"$push": "$organization"},
                    "registrant_organization": {"$push": "$registrant_organization"},
                    "certificate_holder": {"$push": "$certificate_holder"},
                    "all_manufacturers": {"$push": "$manufacturer"},
                    "registration_status": {"$first": "$registration_status"},
                    "applications_count": {"$sum": 1}
                }
            },
            {"$sort": {"product_name": 1}},
            {"$limit": limit}
        ])
        
        results = await db.herbicide_records.aggregate(pipeline).to_list(length=limit)
        
        return [
            SearchResult(
                product_key=r["_id"],
                product_name=r["product_name"],
                formulation=r.get("formulation"),
                active_substances_raw=first_parseable_composition([{"active_substances_raw": value} for value in r.get("active_substances_raw_values", [])]),
                manufacturer=r.get("manufacturer"),
                registrant=next((v for v in r.get("registrant", []) if v), None),
                producer=next((v for v in r.get("producer", []) if v), None),
                company=next((v for v in r.get("company", []) if v), None),
                applicant=next((v for v in r.get("applicant", []) if v), None),
                registration_holder=next((v for v in r.get("registration_holder", []) if v), None),
                registrant_name=next((v for v in r.get("registrant_name", []) if v), None),
                manufacturer_name=next((v for v in r.get("manufacturer_name", []) if v), None),
                producer_name=next((v for v in r.get("producer_name", []) if v), None),
                organization=next((v for v in r.get("organization", []) if v), None),
                registrant_organization=next((v for v in r.get("registrant_organization", []) if v), None),
                certificate_holder=next((v for v in r.get("certificate_holder", []) if v), None),
                display_manufacturer=get_display_manufacturer({**r, "manufacturer": next((v for v in r.get("all_manufacturers", []) if v), r.get("manufacturer"))}),
                registration_status=r.get("registration_status"),
                applications_count=r.get("applications_count", 0)
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/herbicides/{product_key:path}", response_model=ProductCard)
async def get_herbicide(product_key: str):
    """Get a single herbicide product with all its applications"""
    try:
        records = await db.herbicide_records.find(
            {"product_key": product_key}
        ).to_list(length=1000)
        
        if not records:
            raise HTTPException(status_code=404, detail="Product not found")
        
        first_record = with_canonical_composition(records[0], records)
        
        applications = []
        for r in records:
            app = {
                "crop": r.get("crop"),
                "target_object": r.get("target_object"),
                "rate_raw": r.get("rate_raw"),
                "application_method": r.get("application_method"),
                "waiting_period": r.get("waiting_period"),
                "reentry_period_manual": r.get("reentry_period_manual"),
                "reentry_period_mech": r.get("reentry_period_mech"),
                "restrictions": r.get("restrictions")
            }
            if any(v for v in app.values() if v and v != "нет данных"):
                applications.append(app)
        
        return ProductCard(
            product_key=product_key,
            product_name=first_record.get("product_name"),
            formulation=first_record.get("formulation"),
            active_substances_raw=first_record.get("active_substances_raw"),
            **build_composition_metadata(first_record.get("active_substances_raw"), "herbicide"),
            **manufacturer_response_fields(first_record, records),
            registration_number=first_record.get("registration_number"),
            registration_start_date=first_record.get("registration_start_date"),
            registration_end_date=first_record.get("registration_end_date"),
            registration_status=first_record.get("registration_status"),
            applications=applications
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get herbicide failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/herbicides/compare")
async def compare_herbicides(request: CompareRequest):
    """Compare two herbicide products (basic)"""
    try:
        left_records = await db.herbicide_records.find(
            {"product_key": request.left_key}
        ).to_list(length=1000)
        
        right_records = await db.herbicide_records.find(
            {"product_key": request.right_key}
        ).to_list(length=1000)
        
        if not left_records:
            raise HTTPException(status_code=404, detail="Left product not found")
        if not right_records:
            raise HTTPException(status_code=404, detail="Right product not found")
        
        def build_product_info(records):
            first = records[0]
            crops = list(set(r.get("crop") for r in records if r.get("crop")))
            targets = list(set(r.get("target_object") for r in records if r.get("target_object")))
            rates = list(set(r.get("rate_raw") for r in records if r.get("rate_raw")))
            
            return {
                "product_key": first.get("product_key"),
                "product_name": first.get("product_name"),
                "formulation": first.get("formulation"),
                "active_substances_raw": first.get("active_substances_raw"),
                **build_composition_metadata(first.get("active_substances_raw"), "herbicide"),
                "manufacturer": first.get("manufacturer"),
                **manufacturer_response_fields(first, records),
                "registration_number": first.get("registration_number"),
                "registration_status": first.get("registration_status"),
                "registration_start_date": first.get("registration_start_date"),
                "registration_end_date": first.get("registration_end_date"),
                "crops": crops,
                "targets": targets,
                "rates": rates,
                "applications_count": len(records)
            }
        
        left_info = build_product_info(left_records)
        right_info = build_product_info(right_records)
        
        left_crops = set(left_info["crops"])
        right_crops = set(right_info["crops"])
        
        return {
            "left": left_info,
            "right": right_info,
            "comparison": {
                "common_crops": list(left_crops & right_crops),
                "left_only_crops": list(left_crops - right_crops),
                "right_only_crops": list(right_crops - left_crops)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/herbicides/compare-advanced")
async def compare_herbicides_advanced(request: AdvancedCompareRequest):
    """Advanced comparison endpoint; URL unchanged, shared implementation."""
    try:
        return await build_advanced_compare_response(
            request,
            db.herbicide_records,
            "herbicide",
            "Left product not found",
            "Right product not found",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advanced compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/import-insecticides")
async def import_insecticides(file: UploadFile = File(...)):
    """Import insecticide data from Excel file"""
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents), sheet_name='insecticides_raw', header=3)
        
        await db.insecticide_records.delete_many({})
        
        records = []
        for idx, row in df.iterrows():
            product_name = clean_value(row.get('product_name'))
            if not product_name:
                continue
            
            registration_number = clean_value(row.get('registration_number'))
            product_key = create_product_key(product_name, registration_number)
            
            record = {
                "id": str(uuid.uuid4()),
                "record_id": clean_record_id(row.get('record_id')),
                "product_name": product_name,
                "product_key": product_key,
                "formulation": clean_value(row.get('formulation')),
                "active_substances_raw": clean_value(row.get('active_substances_raw')),
                "manufacturer": clean_value(row.get('manufacturer')),
                "registrant": clean_value(row.get('registrant')),
                "producer": clean_value(row.get('producer')),
                "company": clean_value(row.get('company')),
                "applicant": clean_value(row.get('applicant')),
                "registration_holder": clean_value(row.get('registration_holder')),
                "registrant_name": clean_value(row.get('registrant_name')),
                "manufacturer_name": clean_value(row.get('manufacturer_name')),
                "producer_name": clean_value(row.get('producer_name')),
                "organization": clean_value(row.get('organization')),
                "registrant_organization": clean_value(row.get('registrant_organization')),
                "certificate_holder": clean_value(row.get('certificate_holder')),
                "registration_number": registration_number,
                "registration_start_date": clean_value(row.get('registration_start_date')),
                "registration_end_date": clean_value(row.get('registration_end_date')),
                "registration_status": clean_value(row.get('registration_status')),
                "rate_raw": clean_value(row.get('rate_raw')),
                "crop": clean_value(row.get('crop')),
                "target_object": first_clean_value(row, TARGET_OBJECT_IMPORT_COLUMNS),
                "application_method": clean_value(row.get('application_method')),
                "waiting_period": clean_value(row.get('waiting_period')),
                "reentry_period_manual": clean_value(row.get('reentry_period_manual')),
                "reentry_period_mech": clean_value(row.get('reentry_period_mech')),
                "restrictions": clean_value(row.get('restrictions')),
                "source_page": clean_value(row.get('source_page')),
                "source_type": clean_value(row.get('source_type')),
                "notes": clean_value(row.get('notes')),
                "created_at": datetime.utcnow()
            }
            records.append(record)
        
        if records:
            await db.insecticide_records.insert_many(records)
        
        import_batch = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "records_imported": len(records),
            "import_date": datetime.utcnow(),
            "status": "completed",
            "type": "insecticides"
        }
        await db.import_batches.insert_one(import_batch)
        
        unique_products = await db.insecticide_records.distinct("product_key")
        
        return {
            "message": "Insecticide import successful",
            "records_imported": len(records),
            "unique_products": len(unique_products),
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Insecticide import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/insecticides/search", response_model=List[SearchResult])
async def search_insecticides(
    culture: str = Query(default="", description="Filter by culture/crop"),
    harmful_object: str = Query(default="", description="Filter by target object"),
    crop: str = Query(default="", description="Deprecated alias for culture"),
    q: str = Query(default="", description="Search query"),
    only_active: bool = Query(default=False, description="Show only active registrations"),
    limit: int = Query(default=50, le=200, description="Maximum results")
):
    """Search insecticides by name, crop, target, or active substances"""
    try:
        pipeline = []

        registration_filters = build_registration_filters(culture, crop, harmful_object)
        if registration_filters:
            pipeline.append({"$match": registration_filters})
        
        if q and q.strip():
            search_match = build_search_match(q)
            if search_match:
                pipeline.append({"$match": search_match})

        if only_active:
            pipeline.append({"$match": {"registration_status": "Действует"}})
        
        pipeline.extend([
            {
                "$group": {
                    "_id": "$product_key",
                    "product_name": {"$first": "$product_name"},
                    "formulation": {"$first": "$formulation"},
                    "active_substances_raw_values": {"$addToSet": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
                    "registrant": {"$push": "$registrant"},
                    "producer": {"$push": "$producer"},
                    "company": {"$push": "$company"},
                    "applicant": {"$push": "$applicant"},
                    "registration_holder": {"$push": "$registration_holder"},
                    "registrant_name": {"$push": "$registrant_name"},
                    "manufacturer_name": {"$push": "$manufacturer_name"},
                    "producer_name": {"$push": "$producer_name"},
                    "organization": {"$push": "$organization"},
                    "registrant_organization": {"$push": "$registrant_organization"},
                    "certificate_holder": {"$push": "$certificate_holder"},
                    "all_manufacturers": {"$push": "$manufacturer"},
                    "registration_status": {"$first": "$registration_status"},
                    "applications_count": {"$sum": 1}
                }
            },
            {"$sort": {"product_name": 1}},
            {"$limit": limit}
        ])
        
        results = await db.insecticide_records.aggregate(pipeline).to_list(length=limit)
        
        return [
            SearchResult(
                product_key=r["_id"],
                product_name=r["product_name"],
                formulation=r.get("formulation"),
                active_substances_raw=first_parseable_composition([{"active_substances_raw": value} for value in r.get("active_substances_raw_values", [])]),
                manufacturer=r.get("manufacturer"),
                registrant=next((v for v in r.get("registrant", []) if v), None),
                producer=next((v for v in r.get("producer", []) if v), None),
                company=next((v for v in r.get("company", []) if v), None),
                applicant=next((v for v in r.get("applicant", []) if v), None),
                registration_holder=next((v for v in r.get("registration_holder", []) if v), None),
                registrant_name=next((v for v in r.get("registrant_name", []) if v), None),
                manufacturer_name=next((v for v in r.get("manufacturer_name", []) if v), None),
                producer_name=next((v for v in r.get("producer_name", []) if v), None),
                organization=next((v for v in r.get("organization", []) if v), None),
                registrant_organization=next((v for v in r.get("registrant_organization", []) if v), None),
                certificate_holder=next((v for v in r.get("certificate_holder", []) if v), None),
                display_manufacturer=get_display_manufacturer({**r, "manufacturer": next((v for v in r.get("all_manufacturers", []) if v), r.get("manufacturer"))}),
                registration_status=r.get("registration_status"),
                applications_count=r.get("applications_count", 0)
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Insecticide search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/insecticides/{product_key:path}", response_model=ProductCard)
async def get_insecticide(product_key: str):
    """Get a single insecticide product with all its applications"""
    try:
        records = await db.insecticide_records.find(
            {"product_key": product_key}
        ).to_list(length=1000)
        
        if not records:
            raise HTTPException(status_code=404, detail="Insecticide product not found")
        
        first_record = with_canonical_composition(records[0], records)
        
        applications = []
        for r in records:
            app = {
                "crop": r.get("crop"),
                "target_object": r.get("target_object"),
                "rate_raw": r.get("rate_raw"),
                "application_method": r.get("application_method"),
                "waiting_period": r.get("waiting_period"),
                "reentry_period_manual": r.get("reentry_period_manual"),
                "reentry_period_mech": r.get("reentry_period_mech"),
                "restrictions": r.get("restrictions")
            }
            if any(v for v in app.values() if v and v != "нет данных"):
                applications.append(app)
        
        return ProductCard(
            product_key=product_key,
            product_name=first_record.get("product_name"),
            formulation=first_record.get("formulation"),
            active_substances_raw=first_record.get("active_substances_raw"),
            **build_composition_metadata(first_record.get("active_substances_raw"), "insecticide"),
            **manufacturer_response_fields(first_record, records),
            registration_number=first_record.get("registration_number"),
            registration_start_date=first_record.get("registration_start_date"),
            registration_end_date=first_record.get("registration_end_date"),
            registration_status=first_record.get("registration_status"),
            applications=applications
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get insecticide failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/insecticides/compare-advanced")
async def compare_insecticides_advanced(request: AdvancedCompareRequest):
    """Advanced comparison endpoint; URL unchanged, shared implementation."""
    try:
        return await build_advanced_compare_response(
            request,
            db.insecticide_records,
            "insecticide",
            "Left insecticide not found",
            "Right insecticide not found",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advanced compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/import-fungicides")
async def import_fungicides(file: UploadFile = File(...)):
    """Import fungicide data from Excel file"""
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents), sheet_name='fungicides_raw', header=3)
        
        await db.fungicide_records.delete_many({})
        
        records = []
        for idx, row in df.iterrows():
            product_name = clean_value(row.get('product_name'))
            if not product_name:
                continue
            
            registration_number = clean_value(row.get('registration_number'))
            product_key = create_product_key(product_name, registration_number)
            
            record = {
                "id": str(uuid.uuid4()),
                "record_id": clean_record_id(row.get('record_id')),
                "product_name": product_name,
                "product_key": product_key,
                "formulation": clean_value(row.get('formulation')),
                "active_substances_raw": clean_value(row.get('active_substances_raw')),
                "manufacturer": clean_value(row.get('manufacturer')),
                "registrant": clean_value(row.get('registrant')),
                "producer": clean_value(row.get('producer')),
                "company": clean_value(row.get('company')),
                "applicant": clean_value(row.get('applicant')),
                "registration_holder": clean_value(row.get('registration_holder')),
                "registrant_name": clean_value(row.get('registrant_name')),
                "manufacturer_name": clean_value(row.get('manufacturer_name')),
                "producer_name": clean_value(row.get('producer_name')),
                "organization": clean_value(row.get('organization')),
                "registrant_organization": clean_value(row.get('registrant_organization')),
                "certificate_holder": clean_value(row.get('certificate_holder')),
                "registration_number": registration_number,
                "registration_start_date": clean_value(row.get('registration_start_date')),
                "registration_end_date": clean_value(row.get('registration_end_date')),
                "registration_status": clean_value(row.get('registration_status')),
                "rate_raw": clean_value(row.get('rate_raw')),
                "crop": clean_value(row.get('crop')),
                "target_object": first_clean_value(row, TARGET_OBJECT_IMPORT_COLUMNS),
                "application_method": clean_value(row.get('application_method')),
                "waiting_period": clean_value(row.get('waiting_period')),
                "reentry_period_manual": clean_value(row.get('reentry_period_manual')),
                "reentry_period_mech": clean_value(row.get('reentry_period_mech')),
                "restrictions": clean_value(row.get('restrictions')),
                "source_page": clean_value(row.get('source_page')),
                "source_type": clean_value(row.get('source_type')),
                "notes": clean_value(row.get('notes')),
                "created_at": datetime.utcnow()
            }
            records.append(record)
        
        if records:
            await db.fungicide_records.insert_many(records)
        
        import_batch = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "records_imported": len(records),
            "import_date": datetime.utcnow(),
            "status": "completed",
            "type": "fungicides"
        }
        await db.import_batches.insert_one(import_batch)
        
        unique_products = await db.fungicide_records.distinct("product_key")
        
        return {
            "message": "Fungicide import successful",
            "records_imported": len(records),
            "unique_products": len(unique_products),
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Fungicide import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/fungicides/search", response_model=List[SearchResult])
async def search_fungicides(
    culture: str = Query(default="", description="Filter by culture/crop"),
    harmful_object: str = Query(default="", description="Filter by target object"),
    crop: str = Query(default="", description="Deprecated alias for culture"),
    q: str = Query(default="", description="Search query"),
    only_active: bool = Query(default=False, description="Show only active registrations"),
    limit: int = Query(default=50, le=200, description="Maximum results")
):
    """Search fungicides by name, crop, target, or active substances"""
    try:
        pipeline = []

        registration_filters = build_registration_filters(
            culture, crop, harmful_object, FUNGICIDE_HARMFUL_OBJECT_FIELDS
        )
        if registration_filters:
            pipeline.append({"$match": registration_filters})
        
        if q and q.strip():
            search_match = build_search_match(q)
            if search_match:
                pipeline.append({"$match": search_match})

        if only_active:
            pipeline.append({"$match": {"registration_status": "Действует"}})
        
        pipeline.extend([
            {
                "$group": {
                    "_id": "$product_key",
                    "product_name": {"$first": "$product_name"},
                    "formulation": {"$first": "$formulation"},
                    "active_substances_raw_values": {"$addToSet": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
                    "registrant": {"$push": "$registrant"},
                    "producer": {"$push": "$producer"},
                    "company": {"$push": "$company"},
                    "applicant": {"$push": "$applicant"},
                    "registration_holder": {"$push": "$registration_holder"},
                    "registrant_name": {"$push": "$registrant_name"},
                    "manufacturer_name": {"$push": "$manufacturer_name"},
                    "producer_name": {"$push": "$producer_name"},
                    "organization": {"$push": "$organization"},
                    "registrant_organization": {"$push": "$registrant_organization"},
                    "certificate_holder": {"$push": "$certificate_holder"},
                    "all_manufacturers": {"$push": "$manufacturer"},
                    "registration_status": {"$first": "$registration_status"},
                    "applications_count": {"$sum": 1}
                }
            },
            {"$sort": {"product_name": 1}},
            {"$limit": limit}
        ])
        
        results = await db.fungicide_records.aggregate(pipeline).to_list(length=limit)
        
        return [
            SearchResult(
                product_key=r["_id"],
                product_name=r["product_name"],
                formulation=r.get("formulation"),
                active_substances_raw=first_parseable_composition([{"active_substances_raw": value} for value in r.get("active_substances_raw_values", [])]),
                manufacturer=r.get("manufacturer"),
                registrant=next((v for v in r.get("registrant", []) if v), None),
                producer=next((v for v in r.get("producer", []) if v), None),
                company=next((v for v in r.get("company", []) if v), None),
                applicant=next((v for v in r.get("applicant", []) if v), None),
                registration_holder=next((v for v in r.get("registration_holder", []) if v), None),
                registrant_name=next((v for v in r.get("registrant_name", []) if v), None),
                manufacturer_name=next((v for v in r.get("manufacturer_name", []) if v), None),
                producer_name=next((v for v in r.get("producer_name", []) if v), None),
                organization=next((v for v in r.get("organization", []) if v), None),
                registrant_organization=next((v for v in r.get("registrant_organization", []) if v), None),
                certificate_holder=next((v for v in r.get("certificate_holder", []) if v), None),
                display_manufacturer=get_display_manufacturer({**r, "manufacturer": next((v for v in r.get("all_manufacturers", []) if v), r.get("manufacturer"))}),
                registration_status=r.get("registration_status"),
                applications_count=r.get("applications_count", 0)
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Fungicide search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/fungicides/{product_key:path}", response_model=ProductCard)
async def get_fungicide(product_key: str):
    """Get a single fungicide product with all its applications"""
    try:
        records = await db.fungicide_records.find(
            {"product_key": product_key}
        ).to_list(length=1000)
        
        if not records:
            raise HTTPException(status_code=404, detail="Fungicide product not found")
        
        first_record = with_canonical_composition(records[0], records)
        
        applications = []
        for r in records:
            app = {
                "crop": r.get("crop"),
                "target_object": r.get("target_object"),
                "rate_raw": r.get("rate_raw"),
                "application_method": r.get("application_method"),
                "waiting_period": r.get("waiting_period"),
                "reentry_period_manual": r.get("reentry_period_manual"),
                "reentry_period_mech": r.get("reentry_period_mech"),
                "restrictions": r.get("restrictions")
            }
            if any(v for v in app.values() if v and v != "нет данных"):
                applications.append(app)
        
        return ProductCard(
            product_key=product_key,
            product_name=first_record.get("product_name"),
            formulation=first_record.get("formulation"),
            active_substances_raw=first_record.get("active_substances_raw"),
            **build_composition_metadata(first_record.get("active_substances_raw"), "fungicide"),
            **manufacturer_response_fields(first_record, records),
            registration_number=first_record.get("registration_number"),
            registration_start_date=first_record.get("registration_start_date"),
            registration_end_date=first_record.get("registration_end_date"),
            registration_status=first_record.get("registration_status"),
            applications=applications
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get fungicide failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/fungicides/compare-advanced")
async def compare_fungicides_advanced(request: AdvancedCompareRequest):
    """Advanced comparison endpoint; URL unchanged, shared implementation."""
    try:
        return await build_advanced_compare_response(
            request,
            db.fungicide_records,
            "fungicide",
            "Left fungicide not found",
            "Right fungicide not found",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advanced compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/import-seed-treatments")
async def import_seed_treatments(file: UploadFile = File(...)):
    """Import seed treatment data from Excel file"""
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents), sheet_name='seed_treatments_raw', header=3)
        
        await db.seed_treatment_records.delete_many({})
        
        records = []
        for idx, row in df.iterrows():
            product_name = clean_value(row.get('product_name'))
            if not product_name:
                continue
            
            registration_number = clean_value(row.get('registration_number'))
            product_key = create_product_key(product_name, registration_number)
            
            record = {
                "id": str(uuid.uuid4()),
                "record_id": clean_record_id(row.get('record_id')),
                "product_name": product_name,
                "product_key": product_key,
                "formulation": clean_value(row.get('formulation')),
                "active_substances_raw": clean_value(row.get('active_substances_raw')),
                "manufacturer": clean_value(row.get('manufacturer')),
                "registrant": clean_value(row.get('registrant')),
                "producer": clean_value(row.get('producer')),
                "company": clean_value(row.get('company')),
                "applicant": clean_value(row.get('applicant')),
                "registration_holder": clean_value(row.get('registration_holder')),
                "registrant_name": clean_value(row.get('registrant_name')),
                "manufacturer_name": clean_value(row.get('manufacturer_name')),
                "producer_name": clean_value(row.get('producer_name')),
                "organization": clean_value(row.get('organization')),
                "registrant_organization": clean_value(row.get('registrant_organization')),
                "certificate_holder": clean_value(row.get('certificate_holder')),
                "registration_number": registration_number,
                "registration_start_date": clean_value(row.get('registration_start_date')),
                "registration_end_date": clean_value(row.get('registration_end_date')),
                "registration_status": clean_value(row.get('registration_status')),
                "rate_raw": clean_value(row.get('rate_raw')),
                "crop": clean_value(row.get('crop')),
                "target_object": first_clean_value(row, TARGET_OBJECT_IMPORT_COLUMNS),
                "application_method": clean_value(row.get('application_method')),
                "waiting_period": clean_value(row.get('waiting_period')),
                "reentry_period_manual": clean_value(row.get('reentry_period_manual')),
                "reentry_period_mech": clean_value(row.get('reentry_period_mech')),
                "restrictions": clean_value(row.get('restrictions')),
                "source_page": clean_value(row.get('source_page')),
                "source_type": clean_value(row.get('source_type')),
                "notes": clean_value(row.get('notes')),
                "pesticide_type": clean_value(row.get('pesticide_type')),
                "created_at": datetime.utcnow()
            }
            records.append(record)
        
        if records:
            await db.seed_treatment_records.insert_many(records)
        
        import_batch = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "records_imported": len(records),
            "import_date": datetime.utcnow(),
            "status": "completed",
            "type": "seed_treatments"
        }
        await db.import_batches.insert_one(import_batch)
        
        unique_products = await db.seed_treatment_records.distinct("product_key")
        
        return {
            "message": "Seed treatment import successful",
            "records_imported": len(records),
            "unique_products": len(unique_products),
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Seed treatment import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/seed-treatments/search")
async def search_seed_treatments(
    culture: str = Query(default="", description="Filter by culture/crop"),
    harmful_object: str = Query(default="", description="Filter by target object"),
    crop: str = Query(default="", description="Deprecated alias for culture"),
    q: str = Query(default="", description="Search query"),
    only_active: bool = Query(default=False, description="Show only active registrations"),
    limit: int = Query(default=50, le=200, description="Maximum results")
):
    """Search seed treatments by name, crop, target, or active substances"""
    try:
        pipeline = []

        registration_filters = build_registration_filters(culture, crop, harmful_object)
        if registration_filters:
            pipeline.append({"$match": registration_filters})
        
        if q and q.strip():
            search_match = build_search_match(q)
            if search_match:
                pipeline.append({"$match": search_match})

        if only_active:
            pipeline.append({"$match": {"registration_status": "Действует"}})
        
        pipeline.extend([
            {
                "$group": {
                    "_id": "$product_key",
                    "product_name": {"$first": "$product_name"},
                    "formulation": {"$first": "$formulation"},
                    "active_substances_raw_values": {"$addToSet": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
                    "registrant": {"$push": "$registrant"},
                    "producer": {"$push": "$producer"},
                    "company": {"$push": "$company"},
                    "applicant": {"$push": "$applicant"},
                    "registration_holder": {"$push": "$registration_holder"},
                    "registrant_name": {"$push": "$registrant_name"},
                    "manufacturer_name": {"$push": "$manufacturer_name"},
                    "producer_name": {"$push": "$producer_name"},
                    "organization": {"$push": "$organization"},
                    "registrant_organization": {"$push": "$registrant_organization"},
                    "certificate_holder": {"$push": "$certificate_holder"},
                    "all_manufacturers": {"$push": "$manufacturer"},
                    "registration_status": {"$first": "$registration_status"},
                    "pesticide_type": {"$first": "$pesticide_type"},
                    "applications_count": {"$sum": 1}
                }
            },
            {"$sort": {"product_name": 1}},
            {"$limit": limit}
        ])
        
        results = await db.seed_treatment_records.aggregate(pipeline).to_list(length=limit)
        
        return [build_seed_treatment_search_response(r) for r in results]
        
    except Exception as e:
        logger.error(f"Seed treatment search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/seed-treatments/{product_key:path}")
async def get_seed_treatment(product_key: str):
    """Get a single seed treatment product with all its applications"""
    try:
        records = await db.seed_treatment_records.find(
            {"product_key": product_key}
        ).to_list(length=1000)
        
        if not records:
            raise HTTPException(status_code=404, detail="Seed treatment product not found")
        
        first_record = with_canonical_composition(records[0], records)
        
        applications = []
        for r in records:
            app = {
                "crop": r.get("crop"),
                "target_object": r.get("target_object"),
                "rate_raw": r.get("rate_raw"),
                "application_method": r.get("application_method"),
                "waiting_period": r.get("waiting_period"),
                "reentry_period_manual": r.get("reentry_period_manual"),
                "reentry_period_mech": r.get("reentry_period_mech"),
                "restrictions": r.get("restrictions")
            }
            if any(v for v in app.values() if v and v != "нет данных"):
                applications.append(app)
        
        return {
            "product_key": product_key,
            **build_seed_treatment_display_record(first_record, records),
            "formulation": first_record.get("formulation"),
            "manufacturer": first_record.get("manufacturer"),
            **manufacturer_response_fields(first_record, records),
            "registration_number": first_record.get("registration_number"),
            "registration_start_date": first_record.get("registration_start_date"),
            "registration_end_date": first_record.get("registration_end_date"),
            "registration_status": first_record.get("registration_status"),
            "pesticide_type": first_record.get("pesticide_type"),
            "applications": applications
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get seed treatment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/seed-treatments/compare-advanced")
async def compare_seed_treatments_advanced(request: AdvancedCompareRequest):
    """Advanced comparison endpoint; URL unchanged, shared implementation."""
    try:
        return await build_advanced_compare_response(
            request,
            db.seed_treatment_records,
            "seed-treatment",
            "Left seed treatment not found",
            "Right seed treatment not found",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Advanced compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/herbicides/crops", response_model=List[str])
async def herbicide_crops():
    return await get_distinct_values("herbicide_records", "crop")


@api_router.get("/herbicides/harmful-objects", response_model=List[str])
async def herbicide_harmful_objects(crop: str = Query(default="")):
    fq = build_registration_filters(culture=crop) or {}
    return await get_distinct_values("herbicide_records", "target_object", fq)


@api_router.get("/insecticides/crops", response_model=List[str])
async def insecticide_crops():
    return await get_distinct_values("insecticide_records", "crop")


@api_router.get("/insecticides/harmful-objects", response_model=List[str])
async def insecticide_harmful_objects(crop: str = Query(default="")):
    fq = build_registration_filters(culture=crop) or {}
    return await get_distinct_values("insecticide_records", "target_object", fq)


@api_router.get("/fungicides/crops", response_model=List[str])
async def fungicide_crops():
    return await get_distinct_values("fungicide_records", "crop")


@api_router.get("/fungicides/harmful-objects", response_model=List[str])
async def fungicide_harmful_objects(crop: str = Query(default="")):
    fq = build_registration_filters(culture=crop) or {}
    return await get_distinct_values_from_fields(
        "fungicide_records", FUNGICIDE_HARMFUL_OBJECT_FIELDS, fq
    )


@api_router.get("/seed-treatments/crops", response_model=List[str])
async def seed_treatment_crops():
    return await get_distinct_values("seed_treatment_records", "crop")


@api_router.get("/seed-treatments/harmful-objects", response_model=List[str])
async def seed_treatment_harmful_objects(crop: str = Query(default="")):
    fq = build_registration_filters(culture=crop) or {}
    return await get_distinct_values("seed_treatment_records", "target_object", fq)


@api_router.get("/stats")
async def get_stats():
    """Get database statistics for herbicides, insecticides, fungicides and seed treatments"""
    try:
        # Herbicide stats
        herb_total = await db.herbicide_records.count_documents({})
        herb_products = await db.herbicide_records.distinct("product_key")
        herb_active = await db.herbicide_records.count_documents({"registration_status": "Действует"})
        
        # Insecticide stats
        ins_total = await db.insecticide_records.count_documents({})
        ins_products = await db.insecticide_records.distinct("product_key")
        ins_active = await db.insecticide_records.count_documents({"registration_status": "Действует"})
        
        # Fungicide stats
        fun_total = await db.fungicide_records.count_documents({})
        fun_products = await db.fungicide_records.distinct("product_key")
        fun_active = await db.fungicide_records.count_documents({"registration_status": "Действует"})

        # Seed treatment stats
        st_total = await db.seed_treatment_records.count_documents({})
        st_products = await db.seed_treatment_records.distinct("product_key")
        st_active = await db.seed_treatment_records.count_documents({"registration_status": "Действует"})
        
        return {
            "total_records": herb_total,
            "unique_products": len(herb_products),
            "active_registrations": herb_active,
            "insecticides": {
                "total_records": ins_total,
                "unique_products": len(ins_products),
                "active_registrations": ins_active
            },
            "fungicides": {
                "total_records": fun_total,
                "unique_products": len(fun_products),
                "active_registrations": fun_active
            },
            "seed_treatments": {
                "total_records": st_total,
                "unique_products": len(st_products),
                "active_registrations": st_active
            }
        }
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
