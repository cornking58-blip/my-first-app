"""Create seed-treatment composition audit reports from seed_treatments_FINAL_v2.xlsx.

This reads the source workbook only; it never connects to or edits MongoDB.
"""
from __future__ import annotations

import csv
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "seed_treatments_FINAL_v2.xlsx"
OUT = ROOT / "backend" / "data"
SHEET_NAME = "seed_treatments_raw"
HEADER_ROW = 4
UNIT_RE = r"г/л|г/кг|%"


def _xlsx_text(path: Path, member: str) -> bytes:
    with zipfile.ZipFile(path) as zf:
        return zf.read(member)


def _shared_strings(path: Path) -> list[str]:
    try:
        data = _xlsx_text(path, "xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for si in root.findall("x:si", ns):
        strings.append("".join(t.text or "" for t in si.findall(".//x:t", ns)))
    return strings


def _sheet_path(path: Path, sheet_name: str) -> str:
    wb = ET.fromstring(_xlsx_text(path, "xl/workbook.xml"))
    rels = ET.fromstring(_xlsx_text(path, "xl/_rels/workbook.xml.rels"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    rid = None
    for sheet in wb.findall(".//x:sheet", ns):
        if sheet.attrib.get("name") == sheet_name:
            rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            break
    if not rid:
        raise RuntimeError(f"Sheet not found: {sheet_name}")
    for rel in rels.findall("r:Relationship", rel_ns):
        if rel.attrib.get("Id") == rid:
            target = rel.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise RuntimeError(f"Sheet relationship not found: {sheet_name}")


def _col(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_rows(path: Path, sheet_name: str) -> list[dict[str, str]]:
    shared = _shared_strings(path)
    sheet = ET.fromstring(_xlsx_text(path, _sheet_path(path, sheet_name)))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    header = []
    for row in sheet.findall(".//x:row", ns):
        row_num = int(float(row.attrib.get("r", "0")))
        values = {}
        for c in row.findall("x:c", ns):
            ref = c.attrib.get("r", "A1")
            v = c.find("x:v", ns)
            value = ""
            if c.attrib.get("t") == "inlineStr":
                value = "".join(t.text or "" for t in c.findall(".//x:t", ns))
            elif v is not None and v.text is not None:
                value = shared[int(v.text)] if c.attrib.get("t") == "s" else v.text
            values[_col(ref)] = value.strip()
        if row_num == HEADER_ROW:
            header = [values.get(i, "") for i in range(max(values.keys(), default=-1) + 1)]
        elif row_num > HEADER_ROW and header:
            record = {header[i]: values.get(i, "") for i in range(len(header)) if header[i]}
            if record.get("product_name"):
                record["_excel_row_number"] = str(row_num)
                rows.append(record)
    return rows


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()


def clean_name(product_name: str) -> str:
    def repl(m):
        inner = m.group(1)
        return "" if re.search(rf"\d+(?:[.,]\d+)?\s*(?:{UNIT_RE})", inner, re.I) and parse(inner) else m.group(0)
    return re.sub(r"\s+", " ", re.sub(r"\s*\(([^()]*)\)", repl, product_name)).strip(" ,;")


def composition_in_name(product_name: str) -> str:
    for inner in reversed(re.findall(r"\(([^()]*)\)", product_name or "")):
        if re.search(rf"\d+(?:[.,]\d+)?\s*(?:{UNIT_RE})", inner, re.I) and parse(inner):
            return f"({inner.strip()})"
    return ""


def dedupe(raw: str) -> tuple[str, bool]:
    text = norm(raw).strip()
    outer = text.startswith("(") and text.endswith(")")
    inner = text[1:-1].strip() if outer else text
    parts = [p.strip() for p in re.split(r"\s*\+\s*", inner) if p.strip()]
    seen, out, changed = set(), [], False
    for p in parts:
        k = p.casefold().replace("ё", "е")
        if k in seen:
            changed = True
            continue
        seen.add(k); out.append(p)
    if changed:
        s = " + ".join(out)
        return (f"({s})" if outer else s), True
    return text, False


def parse(raw: str) -> list[dict]:
    text, _ = dedupe(raw)
    text = text.strip().strip("()")
    out, seen = [], set()
    for part in re.split(r"\s*\+\s*", text):
        m = re.match(rf"(\d+(?:[.,]\d+)?)\s*({UNIT_RE})\s*(.+)", part.strip(), re.I)
        if not m:
            continue
        conc = float(m.group(1).replace(",", ".")); unit = m.group(2); name = m.group(3).strip()
        # Conservative special case: joined known Protect Combi fragment.
        names = [name]
        if re.fullmatch(r"Пираклостробин\s*-\s*протиоконазол", name, re.I):
            names = ["Пираклостробин", "протиоконазол"]
        for i, n in enumerate(names):
            item = (n.casefold().replace("ё", "е"), conc if i == 0 else None, unit if i == 0 else None)
            if item in seen:
                continue
            seen.add(item)
            out.append({"name": n, "concentration": item[1], "unit": item[2]})
    return out


def summary(subs: list[dict]) -> str:
    return "; ".join(f"{s['name']} — {str(s['concentration']).replace('.', ',') if s['concentration'] is not None else '—'} {s['unit'] or ''}".strip() for s in subs)


def main() -> None:
    rows = read_rows(WORKBOOK, SHEET_NAME)
    groups = defaultdict(list)
    audited = []
    for r in rows:
        groups[(r.get("product_key") or f"{r.get('product_name')}|{r.get('registration_number')}")].append(r)
    for r in rows:
        raw = norm(r.get("active_substances_raw"))
        in_name = composition_in_name(r.get("product_name", ""))
        raw_deduped, repeated = dedupe(raw)
        parsed_raw = parse(raw_deduped)
        parsed_name = parse(in_name)
        final_src = "active_substances_raw" if parsed_raw else ("product_name" if parsed_name else "")
        final = parsed_raw or parsed_name
        key_rows = groups[(r.get("product_key") or f"{r.get('product_name')}|{r.get('registration_number')}")]
        comp_keys = {summary(parse(dedupe(x.get('active_substances_raw',''))[0]) or parse(composition_in_name(x.get('product_name','')))) for x in key_rows if summary(parse(dedupe(x.get('active_substances_raw',''))[0]) or parse(composition_in_name(x.get('product_name',''))))}
        name_counts = Counter((s['name'].casefold().replace('ё','е'), s['concentration'], s['unit']) for s in final)
        manual = len(comp_keys) > 1 or not final
        audited.append({
            "row_number / record_id": r.get("_excel_row_number") or r.get("record_id"),
            "product_name": r.get("product_name", ""),
            "clean_product_name_candidate": clean_name(r.get("product_name", "")),
            "registration_number": r.get("registration_number", ""),
            "manufacturer": r.get("manufacturer", ""),
            "active_substances_raw": raw,
            "composition_found_in_product_name": in_name,
            "composition_found_in_active_substances_raw": raw if parsed_raw else "",
            "parsed_from_active_substances_raw_count": len(parsed_raw),
            "parsed_from_product_name_count": len(parsed_name),
            "final_selected_composition_source": final_src,
            "final_parsed_substance_count": len(final),
            "parsed_substances_summary": summary(final),
            "repeated_fragment_warning": "yes" if repeated else "",
            "duplicated_substance_warning": "yes" if any(c > 1 for c in name_counts.values()) else "",
            "empty_composition_warning": "yes" if not final else "",
            "product_name_contains_composition_warning": "yes" if in_name else "",
            "inconsistent_duplicate_rows_warning": "yes" if len(comp_keys) > 1 else "",
            "unresolved_concentration_warning": "yes" if any(s['concentration'] is None for s in final) else "",
            "safe_auto_fix_possible": "yes" if final and len(comp_keys) <= 1 else "",
            "manual_review_required": "yes" if manual else "",
            "suggested_action": "use explicit parsed composition; clean display title only" if final and not manual else "manual review",
            "notes": "source workbook audit; MongoDB was not changed",
        })
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "seed_treatment_full_composition_audit.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(audited[0].keys()))
        w.writeheader(); w.writerows(audited)
    counts = Counter()
    for a in audited:
        for k in ["product_name_contains_composition_warning","empty_composition_warning","repeated_fragment_warning","inconsistent_duplicate_rows_warning","safe_auto_fix_possible","manual_review_required"]:
            if a[k] == "yes": counts[k] += 1
    md = OUT / "seed_treatment_full_composition_audit.md"
    md.write_text("# Seed treatment full composition audit\n\n" + f"Workbook: `{WORKBOOK.name}`, sheet `{SHEET_NAME}`, header row {HEADER_ROW}.\n\n" + "\n".join(f"- {k}: {v}" for k,v in counts.items()) + "\n", encoding="utf-8")
    (OUT / "seed_treatment_full_composition_audit_summary.md").write_text(f"# Audit summary\n\nTotal seed-treatment records audited: {len(audited)}\n\n" + "\n".join(f"- {k}: {v}" for k,v in counts.items()) + "\n", encoding="utf-8")
    pc = next((a for a in audited if "Протект Комби" in a["product_name"]), None)
    tu = next((a for a in audited if "Туарег" in a["product_name"]), None)
    report = ["# Seed treatment full bugfix report", "", f"Total seed-treatment records audited: {len(audited)}", "", "## Issue counts"]
    report += [f"- {k}: {v}" for k,v in counts.items()]
    report += ["", "## Root cause", "Seed-treatment composition was sometimes repeated in active_substances_raw or embedded in product_name, while backend selection previously only trusted active_substances_raw and comparison used unsafe substring matching.", "", "## Протект Комби", f"- Before: repeated source fragments in active_substances_raw.", f"- After: {pc['parsed_substances_summary'] if pc else 'not found'}", "", "## Туарег", f"- Before: composition stored in product_name caused zero parsed active substances when active_substances_raw was empty.", f"- After display name: {tu['clean_product_name_candidate'] if tu else 'not found'}", f"- After composition: {tu['parsed_substances_summary'] if tu else 'not found'}", "", "MongoDB changed: no. Excel/import changed: no."]
    (OUT / "seed_treatment_full_bugfix_report.md").write_text("\n".join(report)+"\n", encoding="utf-8")

if __name__ == "__main__":
    main()
