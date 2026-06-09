import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from backend.create_corrected_workbooks import create_corrected_workbooks

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _inline_cell(column, row, value):
    return (
        f'<c r="{column}{row}" t="inlineStr"><is><t>{value}</t></is></c>'
    )


def _row(row_number, values):
    cells = []
    for index, value in enumerate(values):
        column = chr(ord("A") + index)
        cells.append(_inline_cell(column, row_number, value))
    return f'<row r="{row_number}">' + "".join(cells) + "</row>"


def _write_minimal_xlsx(path: Path, sheet_name: str) -> None:
    worksheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {title}
    {header}
    {data}
    {other}
  </sheetData>
</worksheet>
""".format(
        title=_row(1, ["Test workbook"]),
        header=_row(
            4,
            [
                "record_id",
                "product_name",
                "formulation",
                "active_substances_raw",
                "manufacturer",
                "registration_number",
                "notes",
            ],
        ),
        data=_row(
            5,
            [
                "1",
                "Тест Продукт",
                "КС",
                "(10 г/л A + 10 г/л A)",
                "Тест Производитель",
                "123-03-1",
                "do not change",
            ],
        ),
        other=_row(
            6,
            [
                "2",
                "Другой Продукт",
                "КС",
                "(5 г/л B)",
                "Другой Производитель",
                "999-03-1",
                "keep me",
            ],
        ),
    )
    workbook = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">
  <sheets>
    <sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("[Content_Types].xml", content_types)
        workbook_zip.writestr("_rels/.rels", root_rels)
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", rels)
        workbook_zip.writestr("xl/worksheets/sheet1.xml", worksheet)


def _write_report(path: Path) -> None:
    columns = [
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
    ]
    with path.open("w", encoding="utf-8", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "pesticide_category": "herbicides",
                "source_file": "herbicides_raw_FINAL_checked.xlsx",
                "source_sheet": "test_raw",
                "source_row": "5",
                "product_name": "Тест Продукт",
                "product_key": "тест-продукт-123-03-1",
                "original_composition": "(10 г/л A + 10 г/л A)",
                "corrected_composition": "(10 г/л A)",
                "correction_type": "safe_deduplication",
                "changed": "yes",
                "manual_review_required": "no",
                "unresolved_fields": "",
                "notes": "Removed exact duplicate in test fixture.",
            }
        )


def _sheet_names(xlsx_path: Path):
    with zipfile.ZipFile(xlsx_path) as workbook_zip:
        workbook_root = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
    return [
        sheet.attrib["name"]
        for sheet in workbook_root.iter()
        if sheet.tag.endswith("}sheet") or sheet.tag == "sheet"
    ]


def _worksheet_values(xlsx_path: Path, sheet_path: str):
    with zipfile.ZipFile(xlsx_path) as workbook_zip:
        root = ET.fromstring(workbook_zip.read(sheet_path))
    rows = {}
    for row in root.iter():
        if not row.tag.endswith("}row") and row.tag != "row":
            continue
        row_number = int(row.attrib["r"])
        values = {}
        for cell in row:
            if not cell.tag.endswith("}c") and cell.tag != "c":
                continue
            reference = cell.attrib["r"]
            text = "".join(cell.itertext())
            values[reference] = text
        rows[row_number] = values
    return rows


class CreateCorrectedWorkbooksTest(unittest.TestCase):
    def test_generates_corrected_copy_without_changing_original_cells(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_dir = Path(temporary_directory)
            source_path = temp_dir / "source.xlsx"
            report_path = temp_dir / "report.csv"
            output_dir = temp_dir / "out"
            _write_minimal_xlsx(source_path, "test_raw")
            _write_report(report_path)

            original_bytes = source_path.read_bytes()
            results = create_corrected_workbooks(
                output_dir=output_dir,
                report_path=report_path,
                source_files={"herbicides": source_path},
                output_filenames={"herbicides": "herbicides_raw_FINAL_checked_corrected.xlsx"},
            )

            output_path = output_dir / "herbicides_raw_FINAL_checked_corrected.xlsx"
            self.assertEqual(source_path.read_bytes(), original_bytes)
            self.assertTrue(output_path.exists())
            self.assertEqual(results[0].records_reviewed, 1)
            self.assertEqual(results[0].records_changed, 1)
            self.assertEqual(_sheet_names(output_path), ["test_raw", "Composition Review"])

            main_rows = _worksheet_values(output_path, "xl/worksheets/sheet1.xml")
            self.assertEqual(main_rows[5]["D5"], "(10 г/л A)")
            self.assertEqual(main_rows[5]["E5"], "Тест Производитель")
            self.assertEqual(main_rows[5]["F5"], "123-03-1")
            self.assertEqual(main_rows[5]["G5"], "do not change")
            self.assertEqual(main_rows[6]["D6"], "(5 г/л B)")
            self.assertEqual(main_rows[4]["H4"], "composition_review_status")
            self.assertEqual(main_rows[4]["I4"], "composition_review_note")
            self.assertEqual(main_rows[5]["H5"], "corrected_automatically")

            review_rows = _worksheet_values(output_path, "xl/worksheets/sheet2.xml")
            self.assertEqual(review_rows[1]["A1"], "source_row")
            self.assertEqual(review_rows[2]["B2"], "Тест Продукт")
            self.assertEqual(review_rows[2]["E2"], "(10 г/л A)")


if __name__ == "__main__":
    unittest.main()
