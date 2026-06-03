from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Sequence
import uuid
from datetime import datetime
import pandas as pd
import io


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
    registration_number: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    registration_status: Optional[str] = None
    applications: List[dict] = []


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
        "manufacturer",
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

def parse_active_substances(raw: Optional[str]) -> List[Dict]:
    """
    Parse active substances from raw string.
    Examples:
    - "(360 г/л Глифосат кислоты (изопропиламинная соль))"
    - "(140 г/л феноксапроп-П-этил + 47 г/л антидот - клоквинтосет-мексил)"
    - "(750 г/кг трибенурон-метил)"
    
    Returns list of dicts with:
    - name: substance name
    - concentration: numeric value
    - unit: г/л or г/кг
    - is_antidote: whether it's an antidote
    """
    if not raw:
        return []
    
    substances = []
    
    # Remove outer parentheses
    text = raw.strip()
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
        # e.g., "47 г/л антидот - клоквинтосет-мексил"
        match = re.match(r'(\d+(?:[.,]\d+)?)\s*(г/л|г/кг)\s*(.+)', part)
        
        if match:
            concentration_str = match.group(1).replace(',', '.')
            unit = match.group(2)
            name = match.group(3).strip()
            
            # Clean up the name - remove "антидот -" prefix
            name = re.sub(r'^антидот\s*[-–]?\s*', '', name, flags=re.IGNORECASE)
            
            # Remove trailing parentheses content that's part of the name
            # Keep it as part of the substance name
            
            try:
                concentration = float(concentration_str)
            except:
                concentration = 0
            
            substances.append({
                "name": name.strip(),
                "concentration": concentration,
                "unit": unit,
                "is_antidote": is_antidote
            })
    
    return substances


def normalize_substance_name(name: str) -> str:
    """Normalize substance name for comparison"""
    # Convert to lowercase and remove extra spaces
    normalized = name.lower().strip()
    
    # Remove common suffixes/variations
    normalized = re.sub(r'\s*\(.*?\)\s*', ' ', normalized)  # Remove parentheses content
    normalized = re.sub(r'\s+', ' ', normalized)  # Normalize spaces
    normalized = normalized.strip()
    
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


RESISTANCE_GROUPS = {
    "herbicide": {
        "глифосат": {"system": "HRAC", "group": "9", "name": "EPSPS inhibitors"},
        "трибенурон-метил": {"system": "HRAC", "group": "2", "name": "ALS inhibitors"},
        "метсульфурон-метил": {"system": "HRAC", "group": "2", "name": "ALS inhibitors"},
        "имазамокс": {"system": "HRAC", "group": "2", "name": "ALS inhibitors"},
        "имазетапир": {"system": "HRAC", "group": "2", "name": "ALS inhibitors"},
        "клетодим": {"system": "HRAC", "group": "1", "name": "ACCase inhibitors"},
        "хизалофоп-п-этил": {"system": "HRAC", "group": "1", "name": "ACCase inhibitors"},
        "2,4-д": {"system": "HRAC", "group": "4", "name": "Synthetic auxins"},
        "дикамба": {"system": "HRAC", "group": "4", "name": "Synthetic auxins"},
        "клопиралид": {"system": "HRAC", "group": "4", "name": "Synthetic auxins"},
        "мезотрион": {"system": "HRAC", "group": "27", "name": "HPPD inhibitors"},
        "метрибузин": {"system": "HRAC", "group": "5", "name": "PSII inhibitors"},
    },
    "fungicide": {
        "тебуконазол": {"system": "FRAC", "group": "3", "name": "DMI fungicides"},
        "пропиконазол": {"system": "FRAC", "group": "3", "name": "DMI fungicides"},
        "дифеноконазол": {"system": "FRAC", "group": "3", "name": "DMI fungicides"},
        "азоксистробин": {"system": "FRAC", "group": "11", "name": "QoI fungicides"},
        "пираклостробин": {"system": "FRAC", "group": "11", "name": "QoI fungicides"},
        "карбендазим": {"system": "FRAC", "group": "1", "name": "MBC fungicides"},
        "флудиоксонил": {"system": "FRAC", "group": "12", "name": "Phenylpyrroles"},
        "металаксил-м": {"system": "FRAC", "group": "4", "name": "Phenylamides"},
    },
    "insecticide": {
        "имидаклоприд": {"system": "IRAC", "group": "4A", "name": "Neonicotinoids"},
        "тиаметоксам": {"system": "IRAC", "group": "4A", "name": "Neonicotinoids"},
        "клотианидин": {"system": "IRAC", "group": "4A", "name": "Neonicotinoids"},
        "лямбда-цигалотрин": {"system": "IRAC", "group": "3A", "name": "Pyrethroids"},
        "альфа-циперметрин": {"system": "IRAC", "group": "3A", "name": "Pyrethroids"},
        "дельтаметрин": {"system": "IRAC", "group": "3A", "name": "Pyrethroids"},
        "хлорантранилипрол": {"system": "IRAC", "group": "28", "name": "Diamides"},
        "абамектин": {"system": "IRAC", "group": "6", "name": "Avermectins"},
    },
}


def normalize_resistance_lookup_name(name: str) -> str:
    """Normalize names before looking them up in exact resistance group tables."""
    normalized = normalize_substance_name(name).replace("ё", "е")
    normalized = re.sub(r"[‐‑‒–—−]", "-", normalized)
    normalized = re.sub(r"\s*[-]\s*", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _lookup_resistance_group_in_table(substance_name: str, pesticide_type: str) -> Optional[Dict[str, Optional[str]]]:
    table = RESISTANCE_GROUPS.get(pesticide_type, {})
    normalized = normalize_resistance_lookup_name(substance_name)

    if normalized in table:
        return table[normalized]

    # Careful partial matching: only accept an explicit known key as a full token/phrase
    # inside parser leftovers such as "глифосат кислоты". This avoids guessing by family.
    for known_name, group_info in table.items():
        known_normalized = normalize_resistance_lookup_name(known_name)
        pattern = rf"(?<![а-яa-z0-9]){re.escape(known_normalized)}(?![а-яa-z0-9])"
        if re.search(pattern, normalized, re.IGNORECASE):
            return group_info

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
        })
    return annotated


def _substance_names_match(left_name: str, right_name: str) -> bool:
    left_norm = normalize_substance_name(left_name)
    right_norm = normalize_substance_name(right_name)
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm


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
                bucket_key = (left_system, left_group, left_substance.get("resistance_group_name"))
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
            "left_substances": sorted(names["left"]),
            "right_substances": sorted(names["right"]),
            "warning": "Действующие вещества разные, но группа устойчивости одна. По механизму действия препараты близки.",
        }
        for (system, group, group_name), names in same_group_bucket.items()
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

def parse_rate_max(rate_raw: Optional[str]) -> Optional[float]:
    """
    Parse the maximum application rate from raw string.
    Examples:
    - "0,6-0,8" -> 0.8
    - "1,5" -> 1.5
    - "0,4-0,6" -> 0.6
    """
    if not rate_raw:
        return None
    
    # Find all numbers in the string
    numbers = re.findall(r'(\d+(?:[.,]\d+)?)', rate_raw)
    
    if not numbers:
        return None
    
    # Convert to floats and get max
    rates = []
    for n in numbers:
        try:
            rates.append(float(n.replace(',', '.')))
        except:
            pass
    
    return max(rates) if rates else None

def select_comparison_rate(manual_rate: Optional[float], registered_rate: Optional[float]) -> tuple[Optional[float], str]:
    """Use a manual comparison rate when provided; otherwise keep max registered rate behavior."""
    if manual_rate is not None:
        return manual_rate, "manual"
    return registered_rate, "max_registered"


def get_max_registered_rate(records: List[Dict]) -> Optional[float]:
    rates = []
    for record in records:
        parsed = parse_rate_max(record.get("rate_raw"))
        if parsed is not None:
            rates.append(parsed)
    return max(rates, default=None)


def build_substance_cost_breakdown(side: str, substances: List[Dict], price: Optional[float], rate_used: Optional[float]) -> List[Dict[str, Any]]:
    """Estimate cost metrics for each active substance separately."""
    if not price or not rate_used:
        return []

    breakdown = []
    total_cost_per_ha = price * rate_used
    total_concentration = sum(s.get("concentration") or 0 for s in substances)

    for substance in substances:
        concentration = substance.get("concentration") or 0
        if concentration <= 0:
            continue

        grams_per_ha = concentration * rate_used
        estimated_cost_share_per_ha = (
            total_cost_per_ha * concentration / total_concentration
            if total_concentration > 0 else None
        )
        estimated_cost_per_gram = (
            estimated_cost_share_per_ha / grams_per_ha
            if estimated_cost_share_per_ha is not None and grams_per_ha > 0 else None
        )

        breakdown.append({
            "side": side,
            "substance_name": substance.get("name"),
            "name": substance.get("name"),  # Backward-friendly alias for existing frontend code.
            "concentration": concentration,
            "unit": substance.get("unit"),
            "rate_used": rate_used,
            "grams_per_ha": round(grams_per_ha, 4),
            "estimated_cost_share_per_ha": round(estimated_cost_share_per_ha, 4) if estimated_cost_share_per_ha is not None else None,
            "estimated_cost_per_gram": round(estimated_cost_per_gram, 6) if estimated_cost_per_gram is not None else None,
        })

    return breakdown


def build_price_analysis(
    left_price: Optional[float],
    right_price: Optional[float],
    left_rate_used: Optional[float],
    right_rate_used: Optional[float],
    left_active: List[Dict],
    right_active: List[Dict],
) -> Optional[Dict[str, Any]]:
    if not left_price and not right_price:
        return None

    left_total_concentration = sum(s["concentration"] for s in left_active)
    right_total_concentration = sum(s["concentration"] for s in right_active)
    left_substances_cost = build_substance_cost_breakdown("left", left_active, left_price, left_rate_used)
    right_substances_cost = build_substance_cost_breakdown("right", right_active, right_price, right_rate_used)

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

    left_first = left_records[0]
    right_first = right_records[0]

    left_substances = parse_active_substances(left_first.get("active_substances_raw"))
    right_substances = parse_active_substances(right_first.get("active_substances_raw"))

    left_active = [s for s in left_substances if not s["is_antidote"]]
    right_active = [s for s in right_substances if not s["is_antidote"]]

    left_antidotes = annotate_substances_with_resistance([s for s in left_substances if s["is_antidote"]], pesticide_type)
    right_antidotes = annotate_substances_with_resistance([s for s in right_substances if s["is_antidote"]], pesticide_type)
    left_active = annotate_substances_with_resistance(left_active, pesticide_type)
    right_active = annotate_substances_with_resistance(right_active, pesticide_type)

    left_max_rate = get_max_registered_rate(left_records)
    right_max_rate = get_max_registered_rate(right_records)
    left_rate_used, left_rate_source = select_comparison_rate(request.left_rate, left_max_rate)
    right_rate_used, right_rate_source = select_comparison_rate(request.right_rate, right_max_rate)

    identical_substances = []
    similar_by_category = []

    for left_substance in left_active:
        left_name_norm = normalize_substance_name(left_substance["name"])
        for right_substance in right_active:
            right_name_norm = normalize_substance_name(right_substance["name"])
            if left_name_norm == right_name_norm or left_name_norm in right_name_norm or right_name_norm in left_name_norm:
                left_per_ha = (left_substance["concentration"] * left_rate_used) if left_rate_used else None
                right_per_ha = (right_substance["concentration"] * right_rate_used) if right_rate_used else None
                identical_substances.append({
                    "name": left_substance["name"],
                    "left_concentration": left_substance["concentration"],
                    "right_concentration": right_substance["concentration"],
                    "left_unit": left_substance["unit"],
                    "right_unit": right_substance["unit"],
                    "left_per_ha": round(left_per_ha, 2) if left_per_ha else None,
                    "right_per_ha": round(right_per_ha, 2) if right_per_ha else None,
                    "concentration_diff": round(abs(left_substance["concentration"] - right_substance["concentration"]), 2),
                    "same_concentration": abs(left_substance["concentration"] - right_substance["concentration"]) < 0.01,
                    "resistance_system": left_substance.get("resistance_system") or right_substance.get("resistance_system"),
                    "resistance_group": left_substance.get("resistance_group") or right_substance.get("resistance_group"),
                    "resistance_group_name": left_substance.get("resistance_group_name") or right_substance.get("resistance_group_name"),
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
            name_norm == normalize_substance_name(item["name"]) or
            name_norm in normalize_substance_name(item["name"]) or
            normalize_substance_name(item["name"]) in name_norm
            for item in identical_substances
        ):
            per_ha = (substance["concentration"] * left_rate_used) if left_rate_used else None
            left_unique.append({
                **substance,
                "category": get_substance_category(substance["name"]),
                "per_ha": round(per_ha, 2) if per_ha else None,
            })

    right_unique = []
    for substance in right_active:
        name_norm = normalize_substance_name(substance["name"])
        if not any(
            name_norm == normalize_substance_name(item["name"]) or
            name_norm in normalize_substance_name(item["name"]) or
            normalize_substance_name(item["name"]) in name_norm
            for item in identical_substances
        ):
            per_ha = (substance["concentration"] * right_rate_used) if right_rate_used else None
            right_unique.append({
                **substance,
                "category": get_substance_category(substance["name"]),
                "per_ha": round(per_ha, 2) if per_ha else None,
            })

    left_total_concentration = sum(s["concentration"] for s in left_active)
    right_total_concentration = sum(s["concentration"] for s in right_active)
    left_total_per_ha = (left_total_concentration * left_rate_used) if left_rate_used else None
    right_total_per_ha = (right_total_concentration * right_rate_used) if right_rate_used else None

    group_analysis = build_resistance_group_analysis(left_active, right_active)
    price_analysis = build_price_analysis(
        request.left_price,
        request.right_price,
        left_rate_used,
        right_rate_used,
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
            "formulation": left_first.get("formulation"),
            "active_substances_raw": left_first.get("active_substances_raw"),
            "registration_status": left_first.get("registration_status"),
            "max_rate": left_max_rate,
            "rate_used": left_rate_used,
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
            "formulation": right_first.get("formulation"),
            "active_substances_raw": right_first.get("active_substances_raw"),
            "registration_status": right_first.get("registration_status"),
            "max_rate": right_max_rate,
            "rate_used": right_rate_used,
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
                    "active_substances_raw": {"$first": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
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
                active_substances_raw=r.get("active_substances_raw"),
                manufacturer=r.get("manufacturer"),
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
        
        first_record = records[0]
        
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
            manufacturer=first_record.get("manufacturer"),
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
                "manufacturer": first.get("manufacturer"),
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
                    "active_substances_raw": {"$first": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
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
                active_substances_raw=r.get("active_substances_raw"),
                manufacturer=r.get("manufacturer"),
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
        
        first_record = records[0]
        
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
            manufacturer=first_record.get("manufacturer"),
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
                    "active_substances_raw": {"$first": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
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
                active_substances_raw=r.get("active_substances_raw"),
                manufacturer=r.get("manufacturer"),
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
        
        first_record = records[0]
        
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
            manufacturer=first_record.get("manufacturer"),
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
                    "active_substances_raw": {"$first": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
                    "registration_status": {"$first": "$registration_status"},
                    "pesticide_type": {"$first": "$pesticide_type"},
                    "applications_count": {"$sum": 1}
                }
            },
            {"$sort": {"product_name": 1}},
            {"$limit": limit}
        ])
        
        results = await db.seed_treatment_records.aggregate(pipeline).to_list(length=limit)
        
        return [
            {
                "product_key": r["_id"],
                "product_name": r["product_name"],
                "formulation": r.get("formulation"),
                "active_substances_raw": r.get("active_substances_raw"),
                "manufacturer": r.get("manufacturer"),
                "registration_status": r.get("registration_status"),
                "pesticide_type": r.get("pesticide_type"),
                "applications_count": r.get("applications_count", 0)
            }
            for r in results
        ]
        
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
        
        first_record = records[0]
        
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
            "product_name": first_record.get("product_name"),
            "formulation": first_record.get("formulation"),
            "active_substances_raw": first_record.get("active_substances_raw"),
            "manufacturer": first_record.get("manufacturer"),
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
