"""Create corrected pesticide source workbook copies from text correction reports.

The repository intentionally does not store generated ``*_corrected.xlsx`` files
because they are binary artifacts.  This script recreates them locally from the
original source workbooks and the CSV correction report.

The implementation uses only the Python standard library.  XLSX files are ZIP
archives containing XML files, so the script edits the relevant worksheet XML,
adds review metadata, and writes corrected copies without touching originals.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import zipfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "backend" / "data"
DEFAULT_REPORT_PATH = DATA_DIR / "composition_excel_corrections_report.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "corrected_workbooks"

SOURCE_FILES = {
    "herbicides": REPO_ROOT / "herbicides_raw_FINAL_checked.xlsx",
    "fungicides": REPO_ROOT / "fungicides_raw_FINAL.xlsx",
    "insecticides": REPO_ROOT / "insecticides_raw_FINAL_v2.xlsx",
    "seed-treatments": REPO_ROOT / "seed_treatments_FINAL_v2.xlsx",
}

OUTPUT_FILENAMES = {
    "herbicides": "herbicides_raw_FINAL_checked_corrected.xlsx",
    "fungicides": "fungicides_raw_FINAL_corrected.xlsx",
    "insecticides": "insecticides_raw_FINAL_v2_corrected.xlsx",
    "seed-treatments": "seed_treatments_FINAL_v2_corrected.xlsx",
}

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"

ET.register_namespace("", NS_MAIN)
ET.register_namespace("r", NS_REL)

REVIEW_COLUMNS = [
    "source_row",
    "product_name",
    "product_key",
    "original_composition",
    "corrected_composition",
    "action_taken",
    "review_status",
    "unresolved_fields",
    "notes",
]

REQUIRED_REPORT_COLUMNS = {
    "pesticide_category",
    "source_file",
    "source_sheet",
    "source_row",
    "product_name",
    "product_key",
    "original_composition",
    "corrected_composition",
    "correction_type",
    "changed",
    "manual_review_required",
    "unresolved_fields",
    "notes",
}


@dataclass(frozen=True)
class SheetInfo:
    name: str
    path: str
    rel_id: str


@dataclass
class WorksheetRow:
    number: int
    values: List[str]
    cells: Dict[int, ET.Element]
    element: ET.Element


@dataclass
class GenerationResult:
    output_path: Path
    records_reviewed: int
    records_changed: int
    manual_review_records: int
    unresolved_records: int
    matched_excel_rows: int


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


def _column_letters(index_1_based: int) -> str:
    letters = ""
    index = index_1_based
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


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


def _set_cell_inline_string(cell: ET.Element, text: str) -> None:
    for child in list(cell):
        cell.remove(child)
    cell.attrib["t"] = "inlineStr"
    inline_string = ET.SubElement(cell, f"{{{NS_MAIN}}}is")
    text_node = ET.SubElement(inline_string, f"{{{NS_MAIN}}}t")
    if text and (text[0].isspace() or text[-1].isspace()):
        text_node.attrib["{http://www.w3.org/XML/1998/namespace}space"] = "preserve"
    text_node.text = text


def _append_inline_cell(row: ET.Element, column_1_based: int, row_number: int, value: str) -> ET.Element:
    cell = ET.Element(
        f"{{{NS_MAIN}}}c",
        {"r": f"{_column_letters(column_1_based)}{row_number}", "t": "inlineStr"},
    )
    inline_string = ET.SubElement(cell, f"{{{NS_MAIN}}}is")
    text_node = ET.SubElement(inline_string, f"{{{NS_MAIN}}}t")
    text_node.text = "" if value is None else str(value)
    row.append(cell)
    return cell


def _sheet_paths(zf: zipfile.ZipFile) -> List[SheetInfo]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels
        if "Id" in rel.attrib and "Target" in rel.attrib
    }

    sheets: List[SheetInfo] = []
    for sheet in workbook.iter():
        if not sheet.tag.endswith("}sheet") and sheet.tag != "sheet":
            continue
        rel_id = sheet.attrib.get(f"{{{NS_REL}}}id")
        target = rel_targets.get(rel_id or "")
        if not target:
            continue
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheets.append(SheetInfo(sheet.attrib.get("name", target), target, rel_id or ""))
    return sheets


def _parse_worksheet_rows(zf: zipfile.ZipFile, sheet_path: str) -> Tuple[ET.Element, List[WorksheetRow]]:
    shared_strings = _read_shared_strings(zf)
    root = ET.fromstring(zf.read(sheet_path))
    rows: List[WorksheetRow] = []

    for row in root.iter():
        if not row.tag.endswith("}row") and row.tag != "row":
            continue
        values_by_index: Dict[int, str] = {}
        cells_by_index: Dict[int, ET.Element] = {}
        row_number = int(row.attrib.get("r", len(rows) + 1))
        for cell in row:
            if not cell.tag.endswith("}c") and cell.tag != "c":
                continue
            column_index = _column_index(cell.attrib.get("r", "A"))
            values_by_index[column_index] = _cell_value(cell, shared_strings)
            cells_by_index[column_index] = cell
        if values_by_index:
            max_index = max(values_by_index)
            values = [values_by_index.get(index, "") for index in range(max_index + 1)]
            rows.append(WorksheetRow(row_number, values, cells_by_index, row))
    return root, rows


def product_key(product_name: str, registration_number: Optional[str]) -> str:
    base = re.sub(r"[^0-9a-zа-яё]+", "-", (product_name or "").casefold()).strip("-")
    registration = re.sub(r"[^0-9a-zа-яё]+", "-", (registration_number or "").casefold()).strip("-")
    return f"{base}-{registration}" if registration else base


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold().replace("ё", "е")).strip()


def _find_header_row(rows: Sequence[WorksheetRow]) -> WorksheetRow:
    for row in rows[:15]:
        lowered = [value.strip().lower() for value in row.values]
        if "product_name" in lowered and "active_substances_raw" in lowered:
            return row
    raise ValueError("Could not find header row with product_name and active_substances_raw")


def _header_indexes(header_row: WorksheetRow) -> Dict[str, int]:
    return {value.strip(): index for index, value in enumerate(header_row.values) if value.strip()}


def _read_report(report_path: Path) -> List[Dict[str, str]]:
    with report_path.open(encoding="utf-8", newline="") as report_file:
        reader = csv.DictReader(report_file)
        missing_columns = REQUIRED_REPORT_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Correction report is missing required columns: {missing}")
        return list(reader)


def _review_status(report_row: Dict[str, str]) -> str:
    if report_row.get("manual_review_required") != "yes":
        return "corrected_automatically"
    if report_row.get("correction_type") == "unresolved_concentration":
        return "concentration_unresolved"
    if report_row.get("changed") == "no":
        return "source_corrupted_no_safe_fix"
    return "manual_review_required"


def _find_matching_rows(
    rows: Sequence[WorksheetRow],
    header_row: WorksheetRow,
    indexes: Dict[str, int],
    report_row: Dict[str, str],
) -> List[WorksheetRow]:
    product_name_index = indexes["product_name"]
    composition_index = indexes["active_substances_raw"]
    registration_index = indexes.get("registration_number")

    matches: List[WorksheetRow] = []
    for row in rows:
        if row.number <= header_row.number:
            continue
        values = row.values
        product_name = values[product_name_index] if product_name_index < len(values) else ""
        registration_number = ""
        if registration_index is not None and registration_index < len(values):
            registration_number = values[registration_index]
        composition = values[composition_index] if composition_index < len(values) else ""
        if (
            product_key(product_name, registration_number) == report_row["product_key"]
            and _normalized_text(composition) == _normalized_text(report_row["original_composition"])
        ):
            matches.append(row)

    if matches:
        return matches

    # Fallback for rows where the registration number is absent in the source.
    for row in rows:
        if row.number <= header_row.number:
            continue
        values = row.values
        product_name = values[product_name_index] if product_name_index < len(values) else ""
        composition = values[composition_index] if composition_index < len(values) else ""
        if (
            _normalized_text(product_name) == _normalized_text(report_row["product_name"])
            and _normalized_text(composition) == _normalized_text(report_row["original_composition"])
        ):
            matches.append(row)
    return matches


def _build_review_sheet(review_records: Sequence[Dict[str, str]]) -> bytes:
    worksheet = ET.Element(f"{{{NS_MAIN}}}worksheet")
    ET.SubElement(worksheet, f"{{{NS_MAIN}}}dimension", {"ref": f"A1:I{len(review_records) + 1}"})
    sheet_views = ET.SubElement(worksheet, f"{{{NS_MAIN}}}sheetViews")
    ET.SubElement(sheet_views, f"{{{NS_MAIN}}}sheetView", {"workbookViewId": "0"})
    ET.SubElement(worksheet, f"{{{NS_MAIN}}}sheetFormatPr", {"defaultRowHeight": "15"})
    sheet_data = ET.SubElement(worksheet, f"{{{NS_MAIN}}}sheetData")

    all_rows = [REVIEW_COLUMNS] + [[record.get(column, "") for column in REVIEW_COLUMNS] for record in review_records]
    for row_number, values in enumerate(all_rows, 1):
        row = ET.SubElement(sheet_data, f"{{{NS_MAIN}}}row", {"r": str(row_number)})
        for column_number, value in enumerate(values, 1):
            _append_inline_cell(row, column_number, row_number, value)

    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def _next_relationship_id(rels_root: ET.Element) -> str:
    ids = []
    for relationship in rels_root:
        rel_id = relationship.attrib.get("Id", "")
        if rel_id.startswith("rId") and rel_id[3:].isdigit():
            ids.append(int(rel_id[3:]))
    return f"rId{max(ids or [0]) + 1}"


def _add_review_sheet_to_workbook(data: Dict[str, bytes], sheet_count: int, review_records: Sequence[Dict[str, str]]) -> None:
    new_sheet_number = sheet_count + 1
    new_sheet_path = f"xl/worksheets/sheet{new_sheet_number}.xml"
    data[new_sheet_path] = _build_review_sheet(review_records)

    rels_root = ET.fromstring(data["xl/_rels/workbook.xml.rels"])
    new_rel_id = _next_relationship_id(rels_root)
    ET.SubElement(
        rels_root,
        f"{{{NS_PKG_REL}}}Relationship",
        {
            "Id": new_rel_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": f"worksheets/sheet{new_sheet_number}.xml",
        },
    )
    data["xl/_rels/workbook.xml.rels"] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    workbook_root = ET.fromstring(data["xl/workbook.xml"])
    sheets_element = next(
        element for element in workbook_root.iter() if element.tag.endswith("}sheets") or element.tag == "sheets"
    )
    max_sheet_id = max(
        int(sheet.attrib.get("sheetId", "0"))
        for sheet in sheets_element
        if sheet.tag.endswith("}sheet") or sheet.tag == "sheet"
    )
    ET.SubElement(
        sheets_element,
        f"{{{NS_MAIN}}}sheet",
        {"name": "Composition Review", "sheetId": str(max_sheet_id + 1), f"{{{NS_REL}}}id": new_rel_id},
    )
    data["xl/workbook.xml"] = ET.tostring(workbook_root, encoding="utf-8", xml_declaration=True)

    content_types_root = ET.fromstring(data["[Content_Types].xml"])
    ET.SubElement(
        content_types_root,
        f"{{{NS_CONTENT_TYPES}}}Override",
        {
            "PartName": f"/xl/worksheets/sheet{new_sheet_number}.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        },
    )
    data["[Content_Types].xml"] = ET.tostring(content_types_root, encoding="utf-8", xml_declaration=True)


def _write_zip(output_path: Path, original_names: Sequence[str], data: Dict[str, bytes]) -> None:
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
        for name in original_names:
            if name in data:
                output_zip.writestr(name, data[name])
        for name, content in data.items():
            if name not in original_names:
                output_zip.writestr(name, content)


def _group_report_rows(report_rows: Iterable[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in report_rows:
        grouped.setdefault(row["pesticide_category"], []).append(row)
    return grouped


def create_corrected_workbooks(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    source_files: Optional[Dict[str, Path]] = None,
    output_filenames: Optional[Dict[str, str]] = None,
) -> List[GenerationResult]:
    """Create corrected workbook copies and return one result per category."""
    source_files = source_files or SOURCE_FILES
    output_filenames = output_filenames or OUTPUT_FILENAMES
    report_rows = _read_report(report_path)
    grouped_rows = _group_report_rows(report_rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: List[GenerationResult] = []
    for category, category_rows in sorted(grouped_rows.items()):
        source_path = source_files.get(category)
        if source_path is None:
            raise ValueError(f"No source workbook configured for category: {category}")
        if not source_path.exists():
            raise FileNotFoundError(f"Source workbook not found: {source_path}")

        output_name = output_filenames.get(category)
        if not output_name:
            output_name = source_path.with_suffix("").name + "_corrected.xlsx"
        output_path = output_dir / output_name
        if output_path.resolve() == source_path.resolve():
            raise ValueError(f"Refusing to overwrite original workbook: {source_path}")

        shutil.copy2(source_path, output_path)
        with zipfile.ZipFile(source_path, "r") as source_zip:
            original_names = source_zip.namelist()
            workbook_data = {name: source_zip.read(name) for name in original_names}
            sheet_infos = _sheet_paths(source_zip)
            if not sheet_infos:
                raise ValueError(f"Workbook has no sheets: {source_path}")

            source_sheet_name = category_rows[0].get("source_sheet")
            matching_sheet = next((sheet for sheet in sheet_infos if sheet.name == source_sheet_name), sheet_infos[0])
            worksheet_root, worksheet_rows = _parse_worksheet_rows(source_zip, matching_sheet.path)

        header_row = _find_header_row(worksheet_rows)
        indexes = _header_indexes(header_row)
        composition_index = indexes["active_substances_raw"]
        original_max_column = max(
            max((max(row.cells) + 1 for row in worksheet_rows if row.cells), default=len(header_row.values)),
            len(header_row.values),
        )
        status_column = original_max_column + 1
        note_column = original_max_column + 2
        _append_inline_cell(header_row.element, status_column, header_row.number, "composition_review_status")
        _append_inline_cell(header_row.element, note_column, header_row.number, "composition_review_note")

        review_records: List[Dict[str, str]] = []
        changed_records = 0
        manual_records = 0
        unresolved_records = 0
        matched_excel_rows = 0

        for report_row in category_rows:
            matching_rows = _find_matching_rows(worksheet_rows, header_row, indexes, report_row)
            review_status = _review_status(report_row)
            row_changed = report_row.get("changed") == "yes"
            if row_changed:
                changed_records += 1
            if report_row.get("manual_review_required") == "yes":
                manual_records += 1
            if report_row.get("correction_type") == "unresolved_concentration":
                unresolved_records += 1

            source_row_numbers: List[str] = []
            for worksheet_row in matching_rows:
                source_row_numbers.append(str(worksheet_row.number))
                matched_excel_rows += 1
                if row_changed:
                    _set_cell_inline_string(worksheet_row.cells[composition_index], report_row["corrected_composition"])
                _append_inline_cell(worksheet_row.element, status_column, worksheet_row.number, review_status)
                _append_inline_cell(worksheet_row.element, note_column, worksheet_row.number, report_row["notes"])

            review_records.append(
                {
                    "source_row": ";".join(source_row_numbers) if source_row_numbers else "NOT_FOUND",
                    "product_name": report_row["product_name"],
                    "product_key": report_row["product_key"],
                    "original_composition": report_row["original_composition"],
                    "corrected_composition": report_row["corrected_composition"],
                    "action_taken": report_row["correction_type"],
                    "review_status": review_status,
                    "unresolved_fields": report_row["unresolved_fields"],
                    "notes": report_row["notes"] if source_row_numbers else report_row["notes"] + " MATCH NOT FOUND",
                }
            )

        workbook_data[matching_sheet.path] = ET.tostring(worksheet_root, encoding="utf-8", xml_declaration=True)
        _add_review_sheet_to_workbook(workbook_data, len(sheet_infos), review_records)
        _write_zip(output_path, original_names, workbook_data)

        with zipfile.ZipFile(output_path) as output_zip:
            bad_member = output_zip.testzip()
        if bad_member is not None:
            raise ValueError(f"Generated workbook is not a valid ZIP/XLSX file; bad member: {bad_member}")

        results.append(
            GenerationResult(
                output_path=output_path,
                records_reviewed=len(category_rows),
                records_changed=changed_records,
                manual_review_records=manual_records,
                unresolved_records=unresolved_records,
                matched_excel_rows=matched_excel_rows,
            )
        )

    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create corrected pesticide workbook copies locally.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated corrected XLSX files. Default: corrected_workbooks/",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Correction report CSV to apply. Default: backend/data/composition_excel_corrections_report.csv",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    results = create_corrected_workbooks(output_dir=args.output_dir, report_path=args.report)

    total_reviewed = sum(result.records_reviewed for result in results)
    total_changed = sum(result.records_changed for result in results)
    total_manual = sum(result.manual_review_records for result in results)
    total_unresolved = sum(result.unresolved_records for result in results)

    print("Corrected workbook generation complete.")
    print(f"Output directory: {args.output_dir}")
    for result in results:
        print(
            "- {name}: reviewed={reviewed}, changed={changed}, manual_review={manual}, "
            "unresolved_concentration={unresolved}, matched_excel_rows={matched}".format(
                name=result.output_path.name,
                reviewed=result.records_reviewed,
                changed=result.records_changed,
                manual=result.manual_review_records,
                unresolved=result.unresolved_records,
                matched=result.matched_excel_rows,
            )
        )
    print(
        "Totals: reviewed={reviewed}, changed={changed}, manual_review={manual}, "
        "unresolved_concentration={unresolved}".format(
            reviewed=total_reviewed,
            changed=total_changed,
            manual=total_manual,
            unresolved=total_unresolved,
        )
    )
    print("Original source workbooks were not overwritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
