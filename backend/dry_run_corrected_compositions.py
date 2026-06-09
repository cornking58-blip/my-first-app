"""Dry-run corrected pesticide composition rows against MongoDB.

This script is intentionally read-only. It compares corrected workbook rows with
current MongoDB documents and writes CSV/Markdown reports describing what would
change. It never applies those changes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "corrected_workbooks"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data"
DEFAULT_CORRECTION_REPORT = DEFAULT_OUTPUT_DIR / "composition_excel_corrections_report.csv"

CATEGORY_CONFIG = {
    "herbicides": {
        "workbook": "herbicides_raw_FINAL_checked_corrected.xlsx",
        "sheet": "herbicides_raw",
        "collection": "herbicide_records",
        "parser_type": "herbicide",
    },
    "fungicides": {
        "workbook": "fungicides_raw_FINAL_corrected.xlsx",
        "sheet": "fungicides_raw",
        "collection": "fungicide_records",
        "parser_type": "fungicide",
    },
    "insecticides": {
        "workbook": "insecticides_raw_FINAL_v2_corrected.xlsx",
        "sheet": "insecticides_raw",
        "collection": "insecticide_records",
        "parser_type": "insecticide",
    },
    "seed-treatments": {
        "workbook": "seed_treatments_FINAL_v2_corrected.xlsx",
        "sheet": "seed_treatments_raw",
        "collection": "seed_treatment_records",
        "parser_type": "seed-treatment",
    },
}
CATEGORY_ALIASES = {"seed_treatments": "seed-treatments", "seed-treatments": "seed-treatments"}
REPORT_COLUMNS = [
    "pesticide_category",
    "corrected_source_file",
    "source_sheet",
    "source_row",
    "product_name",
    "product_key",
    "mongo_collection",
    "mongo_record_id_masked",
    "match_status",
    "current_mongo_composition",
    "corrected_excel_composition",
    "fields_that_would_change",
    "safe_to_update",
    "skip_reason",
    "notes",
]
WRITE_METHODS = {
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "replace_one",
    "bulk_write",
    "delete_one",
    "delete_many",
}
COMPOSITION_METADATA_FIELDS = {
    "active_substances_raw",
    "active_substances",
    "composition",
    "parsed_active_substances",
    "composition_warnings",
    "has_composition_warning",
    "composition_warning_codes",
}
PARSER_START = "# ==================== ACTIVE SUBSTANCE PARSER ===================="
PARSER_END = "# ==================== HELPER FUNCTIONS ===================="


def _load_parser_namespace() -> Dict[str, Any]:
    """Load only the parser block from server.py without opening MongoDB."""
    server_source = (ROOT_DIR / "server.py").read_text(encoding="utf-8")
    parser_source = server_source.split(PARSER_START, 1)[1].split(PARSER_END, 1)[0]
    namespace: Dict[str, Any] = {
        "re": re,
        "json": json,
        "Path": Path,
        "ROOT_DIR": ROOT_DIR,
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Sequence": Sequence,
        "Tuple": Tuple,
        "Counter": Counter,
        "defaultdict": defaultdict,
    }
    exec(parser_source, namespace)
    return namespace


PARSER = _load_parser_namespace()
parse_active_substances = PARSER["parse_active_substances"]
validate_active_substance_composition = PARSER["validate_active_substance_composition"]
composition_warning_codes = PARSER["composition_warning_codes"]


def clean_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "нет данных"}:
        return None
    return text


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold().replace("ё", "е")).strip()


def create_mongo_product_key(product_name: str, registration_number: Optional[str]) -> str:
    """Match backend/server.py create_product_key exactly: product name + pipe + registration."""
    return f"{(product_name or '').strip()}|{(registration_number or '').strip()}"


def create_slug_product_key(product_name: str, registration_number: Optional[str]) -> str:
    """Match earlier audit/correction reports that used a slug key."""
    base = re.sub(r"[^0-9a-zа-яё]+", "-", (product_name or "").casefold()).strip("-")
    registration = re.sub(r"[^0-9a-zа-яё]+", "-", (registration_number or "").casefold()).strip("-")
    return f"{base}-{registration}" if registration else base


def mask_document_id(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}…{text[-4:]}"


def _xml_text(element: Optional[ET.Element]) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [unescape(_xml_text(si)) for si in root]


def _column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _cell_value(cell: ET.Element, shared_strings: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = next((child for child in cell if child.tag.endswith("}v") or child.tag == "v"), None)
    inline_node = next((child for child in cell if child.tag.endswith("}is") or child.tag == "is"), None)
    if cell_type == "inlineStr":
        return unescape(_xml_text(inline_node)).strip()
    if value_node is None:
        return ""
    raw = _xml_text(value_node).strip()
    if cell_type == "s":
        try:
            return shared_strings[int(raw)].strip()
        except (ValueError, IndexError):
            return raw
    return raw


def _sheet_paths(zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels
        if "Id" in rel.attrib and "Target" in rel.attrib
    }
    sheets: List[Tuple[str, str]] = []
    for sheet in workbook.iter():
        if not sheet.tag.endswith("}sheet") and sheet.tag != "sheet":
            continue
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_targets.get(rel_id or "")
        if not target:
            continue
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheets.append((sheet.attrib.get("name", target), target))
    return sheets


def read_xlsx_sheet_rows(path: Path, expected_sheet: str) -> List[Dict[str, str]]:
    rows_out: List[Dict[str, str]] = []
    with zipfile.ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        for sheet_name, sheet_path in _sheet_paths(zf):
            if expected_sheet and sheet_name != expected_sheet:
                continue
            root = ET.fromstring(zf.read(sheet_path))
            raw_rows: List[Tuple[int, List[str]]] = []
            for row_node in root.iter():
                if not row_node.tag.endswith("}row") and row_node.tag != "row":
                    continue
                values: Dict[int, str] = {}
                row_number = int(row_node.attrib.get("r", len(raw_rows) + 1))
                for cell in row_node:
                    if not cell.tag.endswith("}c") and cell.tag != "c":
                        continue
                    values[_column_index(cell.attrib.get("r", "A"))] = _cell_value(cell, shared_strings)
                if values:
                    max_index = max(values)
                    raw_rows.append((row_number, [values.get(i, "") for i in range(max_index + 1)]))
            header: List[str] = []
            header_position: Optional[int] = None
            for position, (_row_number, row) in enumerate(raw_rows[:15]):
                normalized = [str(value).strip() for value in row]
                lowered = {value.lower() for value in normalized}
                if "product_name" in lowered and "active_substances_raw" in lowered:
                    header = normalized
                    header_position = position
                    break
            if header_position is None:
                continue
            for row_number, row in raw_rows[header_position + 1 :]:
                record = {
                    column: (row[index].strip() if index < len(row) else "")
                    for index, column in enumerate(header)
                    if column
                }
                if any(record.values()):
                    record["__source_sheet"] = sheet_name
                    record["__source_row"] = str(row_number)
                    rows_out.append(record)
    return rows_out


def load_correction_report(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def normalize_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category, category)


def report_status(report_row: Dict[str, str]) -> str:
    if report_row.get("manual_review_required") == "yes":
        if report_row.get("correction_type") == "unresolved_concentration":
            return "unresolved_concentration_skip"
        return "manual_review_skip"
    if report_row.get("changed") == "no":
        return "source_row_not_changed"
    return "eligible"


def row_has_unresolved_concentration(composition: str, parser_type: str) -> bool:
    parsed = parse_active_substances(composition)
    warnings = validate_active_substance_composition(composition, parsed, parser_type)
    return "unresolved_concentration" in composition_warning_codes(warnings)


def parsed_metadata(composition: str, parser_type: str) -> Dict[str, Any]:
    parsed = parse_active_substances(composition)
    warnings = validate_active_substance_composition(composition, parsed, parser_type)
    return {
        "active_substances_raw": composition,
        "active_substances": parsed,
        "parsed_active_substances": parsed,
        "composition_warnings": warnings,
        "has_composition_warning": bool(warnings),
        "composition_warning_codes": composition_warning_codes(warnings),
    }


class DryRunWriteBlocked(RuntimeError):
    pass


class SafeMongoCollection:
    """Proxy that allows reads and blocks all known PyMongo write methods."""

    def __init__(self, collection: Any):
        self._collection = collection
        self.write_attempts: List[str] = []

    def __getattr__(self, name: str) -> Any:
        if name in WRITE_METHODS:
            def blocked(*_args: Any, **_kwargs: Any) -> None:
                self.write_attempts.append(name)
                raise DryRunWriteBlocked(f"MongoDB write method {name} is blocked in dry-run mode")
            return blocked
        return getattr(self._collection, name)


class SafeMongoDatabase:
    def __init__(self, database: Any):
        self._database = database

    def __getitem__(self, name: str) -> SafeMongoCollection:
        return SafeMongoCollection(self._database[name])

    def __getattr__(self, name: str) -> Any:
        if name in WRITE_METHODS:
            raise DryRunWriteBlocked(f"MongoDB write method {name} is blocked in dry-run mode")
        return getattr(self._database, name)


@dataclass
class CorrectedRow:
    category: str
    corrected_source_file: str
    source_sheet: str
    source_row: str
    product_name: str
    product_key: str
    slug_product_key: str
    registration_number: Optional[str]
    manufacturer: Optional[str]
    formulation: Optional[str]
    original_composition: str
    corrected_composition: str
    report_status: str
    report_notes: str


def build_corrected_rows(
    input_dir: Path,
    correction_report: Path = DEFAULT_CORRECTION_REPORT,
    category_filter: Optional[str] = None,
) -> List[CorrectedRow]:
    report_rows = load_correction_report(correction_report)
    wanted_category = normalize_category(category_filter) if category_filter else None
    corrected_rows: List[CorrectedRow] = []

    workbook_cache: Dict[str, List[Dict[str, str]]] = {}
    for report_row in report_rows:
        category = normalize_category(report_row["pesticide_category"])
        if wanted_category and category != wanted_category:
            continue
        config = CATEGORY_CONFIG[category]
        workbook_name = config["workbook"]
        workbook_path = input_dir / workbook_name
        if not workbook_path.exists():
            raise FileNotFoundError(f"Corrected workbook not found: {workbook_path}")
        if workbook_name not in workbook_cache:
            workbook_cache[workbook_name] = read_xlsx_sheet_rows(workbook_path, config["sheet"])

        corrected_composition = report_row.get("corrected_composition") or report_row.get("original_composition") or ""
        product_name = report_row.get("product_name", "")
        original_composition = report_row.get("original_composition", "")
        matching_excel_rows = []
        for excel_row in workbook_cache[workbook_name]:
            excel_product = clean_value(excel_row.get("product_name")) or ""
            excel_reg = clean_value(excel_row.get("registration_number"))
            excel_composition = clean_value(excel_row.get("active_substances_raw")) or ""
            if (
                create_slug_product_key(excel_product, excel_reg) == report_row.get("product_key")
                and normalize_text(excel_composition) == normalize_text(corrected_composition)
            ):
                matching_excel_rows.append(excel_row)
        # Manual/no-change rows may still contain original text in corrected workbook.
        if not matching_excel_rows:
            for excel_row in workbook_cache[workbook_name]:
                excel_product = clean_value(excel_row.get("product_name")) or ""
                excel_reg = clean_value(excel_row.get("registration_number"))
                excel_composition = clean_value(excel_row.get("active_substances_raw")) or ""
                if (
                    normalize_text(excel_product) == normalize_text(product_name)
                    and normalize_text(excel_composition) in {normalize_text(corrected_composition), normalize_text(original_composition)}
                    and create_slug_product_key(excel_product, excel_reg) == report_row.get("product_key")
                ):
                    matching_excel_rows.append(excel_row)
        if not matching_excel_rows:
            # Keep the report row visible instead of silently losing it.
            matching_excel_rows = [{
                "product_name": product_name,
                "registration_number": "",
                "manufacturer": "",
                "formulation": "",
                "active_substances_raw": corrected_composition,
                "__source_sheet": report_row.get("source_sheet", config["sheet"]),
                "__source_row": report_row.get("source_row", ""),
            }]

        for excel_row in matching_excel_rows:
            excel_product = clean_value(excel_row.get("product_name")) or product_name
            registration_number = clean_value(excel_row.get("registration_number"))
            corrected_rows.append(CorrectedRow(
                category=category,
                corrected_source_file=workbook_name,
                source_sheet=excel_row.get("__source_sheet", report_row.get("source_sheet", config["sheet"])),
                source_row=excel_row.get("__source_row", report_row.get("source_row", "")),
                product_name=excel_product,
                product_key=create_mongo_product_key(excel_product, registration_number),
                slug_product_key=create_slug_product_key(excel_product, registration_number),
                registration_number=registration_number,
                manufacturer=clean_value(excel_row.get("manufacturer")),
                formulation=clean_value(excel_row.get("formulation")),
                original_composition=original_composition,
                corrected_composition=clean_value(excel_row.get("active_substances_raw")) or corrected_composition,
                report_status=report_status(report_row),
                report_notes=report_row.get("notes", ""),
            ))
    return corrected_rows


def _cursor_to_list(cursor: Any) -> List[Dict[str, Any]]:
    if isinstance(cursor, list):
        return cursor
    return list(cursor)


def find_mongo_matches(collection: Any, corrected: CorrectedRow) -> Tuple[List[Dict[str, Any]], str]:
    product_key_matches = _cursor_to_list(collection.find({"product_key": corrected.product_key}))
    if product_key_matches:
        original_matches = [
            row for row in product_key_matches
            if normalize_text(row.get("active_substances_raw")) == normalize_text(corrected.original_composition)
        ]
        if original_matches:
            return original_matches, "product_key + exact original composition"
        return product_key_matches, "product_key"

    identity_query: Dict[str, Any] = {"product_name": corrected.product_name}
    if corrected.registration_number:
        identity_query["registration_number"] = corrected.registration_number
    identity_matches = _cursor_to_list(collection.find(identity_query))
    if identity_matches:
        return identity_matches, "product_name + registration_number fallback"
    return [], "product_key, then product_name + registration_number fallback"


def classify_corrected_row(collection: Any, corrected: CorrectedRow) -> Dict[str, str]:
    config = CATEGORY_CONFIG[corrected.category]
    parser_type = config["parser_type"]
    base = {
        "pesticide_category": corrected.category,
        "corrected_source_file": corrected.corrected_source_file,
        "source_sheet": corrected.source_sheet,
        "source_row": corrected.source_row,
        "product_name": corrected.product_name,
        "product_key": corrected.product_key,
        "mongo_collection": config["collection"],
        "mongo_record_id_masked": "",
        "match_status": "",
        "current_mongo_composition": "",
        "corrected_excel_composition": corrected.corrected_composition,
        "fields_that_would_change": "",
        "safe_to_update": "no",
        "skip_reason": "",
        "notes": corrected.report_notes,
    }

    if corrected.report_status in {"manual_review_skip", "unresolved_concentration_skip", "source_row_not_changed"}:
        base["match_status"] = corrected.report_status
        base["skip_reason"] = corrected.report_status
        return base
    if row_has_unresolved_concentration(corrected.corrected_composition, parser_type):
        base["match_status"] = "unresolved_concentration_skip"
        base["skip_reason"] = "corrected row still has unresolved concentration warning"
        return base

    matches, strategy = find_mongo_matches(collection, corrected)
    base["notes"] = (base["notes"] + f"; mongo match strategy: {strategy}").strip("; ")
    if not matches:
        base["match_status"] = "mongo_record_not_found"
        base["skip_reason"] = "no MongoDB document matched stable identity fields"
        return base

    ids = [mask_document_id(row.get("_id") or row.get("id")) for row in matches]
    base["mongo_record_id_masked"] = ";".join(ids)
    if len(matches) > 1:
        compositions = {normalize_text(row.get("active_substances_raw")) for row in matches}
        base["current_mongo_composition"] = " || ".join(str(row.get("active_substances_raw") or "") for row in matches[:3])
        if len(compositions) == 1:
            base["match_status"] = "duplicate_mongo_records"
            base["skip_reason"] = "more than one MongoDB row matched; current import stores product/application rows and updater must not guess"
        else:
            base["match_status"] = "ambiguous_mongo_match"
            base["skip_reason"] = "multiple MongoDB rows matched with different compositions"
        return base

    mongo_row = matches[0]
    current_composition = str(mongo_row.get("active_substances_raw") or "")
    base["current_mongo_composition"] = current_composition
    if normalize_text(current_composition) == normalize_text(corrected.corrected_composition):
        base["match_status"] = "exact_match_no_change"
        base["safe_to_update"] = "no"
        return base

    identity_mismatches = []
    for field, corrected_value in [
        ("product_name", corrected.product_name),
        ("registration_number", corrected.registration_number),
        ("manufacturer", corrected.manufacturer),
        ("formulation", corrected.formulation),
    ]:
        if corrected_value and normalize_text(mongo_row.get(field)) != normalize_text(corrected_value):
            identity_mismatches.append(field)
    if identity_mismatches:
        base["match_status"] = "ambiguous_mongo_match"
        base["skip_reason"] = "stable identity mismatch: " + ", ".join(identity_mismatches)
        return base

    old_meta = parsed_metadata(current_composition, parser_type)
    new_meta = parsed_metadata(corrected.corrected_composition, parser_type)
    changed_fields = [field for field in sorted(COMPOSITION_METADATA_FIELDS) if old_meta.get(field) != new_meta.get(field)]
    if not changed_fields:
        changed_fields = ["active_substances_raw"]
    base["fields_that_would_change"] = ";".join(changed_fields)
    base["match_status"] = "safe_update_candidate"
    base["safe_to_update"] = "yes"
    return base


def write_reports(rows: Sequence[Dict[str, str]], output_dir: Path) -> Tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "mongodb_composition_dry_run_report.csv"
    md_path = output_dir / "mongodb_composition_dry_run_summary.md"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["match_status"] for row in rows)
    by_category = Counter(row["pesticide_category"] for row in rows)
    protect_rows = [row for row in rows if "протект комби" in normalize_text(row["product_name"])]
    lines = [
        "# MongoDB composition dry-run summary",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "MongoDB writes performed: 0",
        "Dry-run mode: yes — reports only, no database write method is called.",
        "",
        "## Totals",
        f"- Total corrected rows checked: {len(rows)}",
        f"- Exact no-change count: {counts.get('exact_match_no_change', 0)}",
        f"- Safe update candidate count: {counts.get('safe_update_candidate', 0)}",
        f"- Manual-review skip count: {counts.get('manual_review_skip', 0)}",
        f"- Unresolved concentration skip count: {counts.get('unresolved_concentration_skip', 0)}",
        f"- Record not found count: {counts.get('mongo_record_not_found', 0)}",
        f"- Ambiguous match count: {counts.get('ambiguous_mongo_match', 0)}",
        f"- Duplicate Mongo record count: {counts.get('duplicate_mongo_records', 0)}",
        f"- Source row not changed count: {counts.get('source_row_not_changed', 0)}",
        "",
        "## Counts by category",
    ]
    lines.extend(f"- {category}: {count}" for category, count in sorted(by_category.items()))
    lines.extend(["", "## Exact result for Протект Комби"])
    if protect_rows:
        for row in protect_rows:
            lines.extend([
                f"- Category: {row['pesticide_category']}",
                f"  Product: {row['product_name']}",
                f"  Match status: {row['match_status']}",
                f"  Safe to update: {row['safe_to_update']}",
                f"  Skip reason: {row['skip_reason'] or 'none'}",
                f"  Corrected composition: {row['corrected_excel_composition']}",
            ])
    else:
        lines.append("- Протект Комби was not present in checked corrected rows.")
    lines.extend(["", "## Safety confirmation", "- Zero MongoDB writes occurred."])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def run_dry_run(db: Any, input_dir: Path, output_dir: Path, category: Optional[str] = None) -> List[Dict[str, str]]:
    safe_db = SafeMongoDatabase(db)
    corrected_rows = build_corrected_rows(input_dir=input_dir, category_filter=category)
    report_rows: List[Dict[str, str]] = []
    for corrected in corrected_rows:
        collection_name = CATEGORY_CONFIG[corrected.category]["collection"]
        collection = safe_db[collection_name]
        report_rows.append(classify_corrected_row(collection, corrected))
    write_reports(report_rows, output_dir)
    return report_rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run corrected pesticide compositions against MongoDB.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory with corrected workbook copies.")
    parser.add_argument("--category", choices=sorted(CATEGORY_CONFIG), help="Optional single category to check.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for CSV/Markdown reports.")
    parser.add_argument("--mongo-uri-env", default="MONGO_URL", help="Environment variable that contains the MongoDB URI.")
    return parser


def connect_database(mongo_uri_env: str) -> Any:
    mongo_uri = os.environ.get(mongo_uri_env)
    if not mongo_uri:
        raise RuntimeError(f"MongoDB URI environment variable {mongo_uri_env} is not set; no live dry run was performed.")
    try:
        from pymongo import MongoClient  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pymongo is not installed; install backend requirements before live dry run.") from exc
    db_name = os.environ.get("DB_NAME", "herbicides_db")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client[db_name]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    print("MongoDB composition dry run starting. Mode: read-only reports only.")
    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Mongo URI env var: {args.mongo_uri_env} (value hidden)")
    try:
        db = connect_database(args.mongo_uri_env)
        rows = run_dry_run(db, args.input_dir, args.output_dir, args.category)
    except Exception as exc:
        print(f"Dry run could not complete: {exc}", file=sys.stderr)
        return 2
    print(f"Checked corrected rows: {len(rows)}")
    print(f"CSV report: {args.output_dir / 'mongodb_composition_dry_run_report.csv'}")
    print(f"Markdown summary: {args.output_dir / 'mongodb_composition_dry_run_summary.md'}")
    print("MongoDB writes performed: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
