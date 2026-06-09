"""Audit pesticide active-substance compositions from source XLSX files.

This script intentionally uses only the Python standard library so it can run in
minimal CI/container environments where pandas/openpyxl are unavailable.
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
DATA_DIR = ROOT_DIR / "data"

SOURCE_FILES = {
    "herbicides": REPO_ROOT / "herbicides_raw_FINAL_checked.xlsx",
    "fungicides": REPO_ROOT / "fungicides_raw_FINAL.xlsx",
    "insecticides": REPO_ROOT / "insecticides_raw_FINAL_v2.xlsx",
    "seed-treatments": REPO_ROOT / "seed_treatments_FINAL_v2.xlsx",
}

COMPOSITION_FIELD_NAMES = {
    "active_substances_raw",
    "active_substances",
    "composition",
    "canonical_composition",
    "active_ingredients",
    "active_ingredient",
}

PARSER_START = "# ==================== ACTIVE SUBSTANCE PARSER ===================="
PARSER_END = "# ==================== HELPER FUNCTIONS ===================="


def _load_parser_namespace() -> Dict[str, Any]:
    """Execute the parser section from server.py without importing FastAPI/Mongo."""
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
normalize_substance_name = PARSER["normalize_substance_name"]
deduplicate_repeated_composition_fragments = PARSER["deduplicate_repeated_composition_fragments"]


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
    sheets = []
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


def read_xlsx_rows(path: Path) -> Iterable[Dict[str, str]]:
    with zipfile.ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        for _sheet_name, sheet_path in _sheet_paths(zf):
            root = ET.fromstring(zf.read(sheet_path))
            raw_rows: List[List[str]] = []
            for row in root.iter():
                if not row.tag.endswith("}row") and row.tag != "row":
                    continue
                values: Dict[int, str] = {}
                for cell in row:
                    if not cell.tag.endswith("}c") and cell.tag != "c":
                        continue
                    ref = cell.attrib.get("r", "A")
                    values[_column_index(ref)] = _cell_value(cell, shared_strings)
                if values:
                    max_index = max(values)
                    raw_rows.append([values.get(i, "") for i in range(max_index + 1)])

            header_index = None
            headers: List[str] = []
            for index, row in enumerate(raw_rows[:15]):
                normalized = [str(value).strip() for value in row]
                lowered = {value.lower() for value in normalized}
                if "product_name" in lowered and (
                    "active_substances_raw" in lowered or "active_substances" in lowered or "composition" in lowered
                ):
                    header_index = index
                    headers = normalized
                    break
            if header_index is None:
                continue

            for row in raw_rows[header_index + 1 :]:
                record = {
                    header: (row[idx].strip() if idx < len(row) else "")
                    for idx, header in enumerate(headers)
                    if header
                }
                if any(record.values()):
                    yield record


def clean_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "нет данных"}:
        return None
    return text


def product_key(product_name: str, registration_number: Optional[str]) -> str:
    base = re.sub(r"[^0-9a-zа-яё]+", "-", (product_name or "").casefold()).strip("-")
    reg = re.sub(r"[^0-9a-zа-яё]+", "-", (registration_number or "").casefold()).strip("-")
    return f"{base}-{reg}" if reg else base


def composition_fields(record: Dict[str, str]) -> List[Tuple[str, str]]:
    values: List[Tuple[str, str]] = []
    seen = set()
    for field, value in record.items():
        normalized_field = field.strip().lower()
        if normalized_field in COMPOSITION_FIELD_NAMES or "composition" in normalized_field:
            cleaned = clean_value(value)
            if not cleaned:
                continue
            key = re.sub(r"\s+", " ", cleaned.casefold().replace("ё", "е")).strip()
            if key in seen:
                continue
            seen.add(key)
            values.append((field, cleaned))
    return values


def severity_for(warnings: Sequence[Dict[str, Any]]) -> str:
    if any(warning.get("severity") == "error" for warning in warnings):
        return "error"
    if warnings:
        return "warning"
    return "clean"


def notes_for(raw: str, parsed: Sequence[Dict[str, Any]], warnings: Sequence[Dict[str, Any]]) -> str:
    notes: List[str] = []
    deduped, changed = deduplicate_repeated_composition_fragments(raw)
    if changed:
        notes.append(f"automatic parser dedupe: {deduped}")
    unresolved = [item.get("name") for item in parsed if item.get("concentration_unresolved")]
    if unresolved:
        notes.append("unresolved concentration: " + ", ".join(name for name in unresolved if name))
    if not warnings:
        notes.append("clean")
    return "; ".join(notes)


def audit() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_compositions = set()
    for category, path in SOURCE_FILES.items():
        if not path.exists():
            continue
        for record in read_xlsx_rows(path):
            product_name = clean_value(record.get("product_name"))
            if not product_name:
                continue
            registration_number = clean_value(record.get("registration_number"))
            key = product_key(product_name, registration_number)
            for _field, raw in composition_fields(record):
                unique_key = (category, key, re.sub(r"\s+", " ", raw.casefold().replace("ё", "е")).strip())
                if unique_key in seen_compositions:
                    continue
                seen_compositions.add(unique_key)
                pesticide_type = category[:-1] if category.endswith("s") else category
                if category == "seed-treatments":
                    pesticide_type = "seed-treatment"
                parsed = parse_active_substances(raw)
                warnings = validate_active_substance_composition(raw, parsed, pesticide_type)
                warning_codes = composition_warning_codes(warnings)
                rows.append({
                    "pesticide_category": category,
                    "product_name": product_name,
                    "product_key": key,
                    "raw_composition": raw,
                    "parsed_component_count": len(parsed),
                    "parsed_substances": json.dumps(parsed, ensure_ascii=False),
                    "warning_codes": ";".join(warning_codes),
                    "severity": severity_for(warnings),
                    "automatic_fix_applied": "yes" if deduplicate_repeated_composition_fragments(raw)[1] else "no",
                    "requires_manual_review": "yes" if warnings else "no",
                    "notes": notes_for(raw, parsed, warnings),
                })
    return rows


def write_reports(rows: Sequence[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    report_csv = DATA_DIR / "composition_audit_report.csv"
    columns = [
        "pesticide_category", "product_name", "product_key", "raw_composition",
        "parsed_component_count", "parsed_substances", "warning_codes", "severity",
        "automatic_fix_applied", "requires_manual_review", "notes",
    ]
    with report_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    clean = sum(1 for row in rows if row["severity"] == "clean")
    suspicious = total - clean
    auto_fixed = sum(1 for row in rows if row["automatic_fix_applied"] == "yes")
    manual = sum(1 for row in rows if row["requires_manual_review"] == "yes")
    warning_counts = Counter(
        code
        for row in rows
        for code in row["warning_codes"].split(";")
        if code
    )
    category_counts = Counter(row["pesticide_category"] for row in rows)
    suspicious_rows = [row for row in rows if row["severity"] != "clean"]
    top_suspicious = sorted(
        suspicious_rows,
        key=lambda row: (row["severity"] != "error", -len(row["warning_codes"].split(";")), row["product_name"]),
    )[:20]
    protect_rows = [row for row in rows if "протект комби" in row["product_name"].casefold()]

    summary_lines = [
        "# Active-substance composition audit summary",
        "",
        f"Total unique product compositions checked: {total}",
        f"Clean count: {clean}",
        f"Suspicious count: {suspicious}",
        f"Automatically corrected count: {auto_fixed}",
        f"Manual-review count: {manual}",
        "",
        "## Warning counts",
    ]
    summary_lines += [f"- {code}: {count}" for code, count in warning_counts.most_common()] or ["- none: 0"]
    summary_lines += ["", "## Counts by pesticide category"]
    summary_lines += [f"- {category}: {count}" for category, count in sorted(category_counts.items())]
    summary_lines += ["", "## Top suspicious products"]
    summary_lines += [
        f"- {row['pesticide_category']} / {row['product_name']} / {row['warning_codes']} / {row['notes']}".rstrip()
        for row in top_suspicious
    ] or ["- none"]
    summary_lines += ["", "## Exact details for Протект Комби"]
    if protect_rows:
        for row in protect_rows:
            summary_lines += [
                f"- Category: {row['pesticide_category']}",
                f"  Product key: {row['product_key']}",
                f"  Raw composition: {row['raw_composition']}",
                f"  Parsed component count: {row['parsed_component_count']}",
                f"  Parsed substances: {row['parsed_substances']}",
                f"  Warning codes: {row['warning_codes'] or 'none'}",
                f"  Notes: {row['notes']}",
            ]
    else:
        summary_lines.append("- Протект Комби was not found in the audited source files.")

    (DATA_DIR / "composition_audit_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    detail_lines = [
        "# Active-substance composition audit report",
        "",
        "This concise Markdown report lists suspicious compositions. The full row-level report is in `composition_audit_report.csv`.",
        "",
        "| category | product | warnings | severity | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in suspicious_rows[:200]:
        detail_lines.append(
            "| {pesticide_category} | {product_name} | {warning_codes} | {severity} | {notes} |".format(
                **{key: str(value).replace("|", "\\|").replace("\n", " ") for key, value in row.items()}
            )
        )
    if len(suspicious_rows) > 200:
        detail_lines.append(f"\n_Showing first 200 of {len(suspicious_rows)} suspicious rows; see CSV for all rows._")
    (DATA_DIR / "composition_audit_report.md").write_text("\n".join(detail_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    audited_rows = audit()
    write_reports(audited_rows)
    print(json.dumps({
        "total": len(audited_rows),
        "clean": sum(1 for row in audited_rows if row["severity"] == "clean"),
        "suspicious": sum(1 for row in audited_rows if row["severity"] != "clean"),
        "auto_fixed": sum(1 for row in audited_rows if row["automatic_fix_applied"] == "yes"),
        "manual_review": sum(1 for row in audited_rows if row["requires_manual_review"] == "yes"),
    }, ensure_ascii=False, indent=2))
