"""Guarded updater for approved MongoDB composition corrections.

Default mode is validation-only and never writes. Live writes require both --apply and
an exact confirmation phrase. The updater reruns the same row-level matching used by
backend/dry_run_corrected_compositions.py, accepts only safe_update_candidate rows,
backs up every target document before the first write, and updates only approved
composition-related fields with optimistic concurrency checks.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dry_run_corrected_compositions import (
    CATEGORY_CONFIG,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_CORRECTION_REPORT,
    build_corrected_rows,
    classify_corrected_row,
    find_mongo_matches,
    normalize_text,
    parsed_metadata,
)

DEFAULT_DRY_RUN_REPORT = DEFAULT_OUTPUT_DIR / "mongodb_composition_dry_run_report.csv"
DEFAULT_BACKUP_DIR = REPO_ROOT / "mongodb_backups"
EXPECTED_DATABASE_NAME = "herbicides_db"
DEFAULT_EXPECTED_SAFE_COUNT = 184
APPLY_CONFIRMATION = "APPLY_184_APPROVED_COMPOSITION_UPDATES"
PROTECTED_PRODUCT_FRAGMENT = "протект комби"
REQUIRED_COLLECTIONS = tuple(config["collection"] for config in CATEGORY_CONFIG.values())
BLOCKING_STATUSES = {
    "ambiguous_mongo_match",
    "true_duplicate_mongo_records",
    "mongo_record_not_found",
}
NEVER_UPDATE_STATUSES = {
    "manual_review_skip",
    "unresolved_concentration_skip",
    "mongo_record_not_found",
    "ambiguous_mongo_match",
    "true_duplicate_mongo_records",
    "source_row_not_changed",
    "exact_match_no_change",
}
ALLOWED_UPDATE_FIELDS = {
    "active_substances_raw",
    "active_substances",
    "composition",
    "composition_warnings",
    "has_composition_warning",
}
FORBIDDEN_WRITE_METHODS = {
    "delete_one",
    "delete_many",
    "insert_one",
    "insert_many",
    "replace_one",
    "update_many",
    "drop",
}
REPORT_COLUMNS = [
    "collection",
    "product_name",
    "row_identity_signature",
    "match_status",
    "action",
    "matched_count",
    "modified_count",
    "message",
]


class ApplySafetyError(RuntimeError):
    """Raised when the guarded updater refuses to continue."""


@dataclass
class ApplyTarget:
    collection_name: str
    document_id: Any
    row: Dict[str, str]
    original_document: Dict[str, Any]
    update_fields: Dict[str, Any]
    identity_signature: str
    dry_run_composition: str


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    """Serialize MongoDB values without losing ObjectId type information."""
    if hasattr(value, "binary") and value.__class__.__name__ == "ObjectId":
        return {"$oid": str(value)}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return {"$repr": str(value), "$type": value.__class__.__name__}


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def validate_input_files(input_dir: Path, dry_run_report: Path, correction_report: Path) -> None:
    if not input_dir.exists() or not input_dir.is_dir():
        raise ApplySafetyError(f"Corrected workbook directory is missing: {input_dir}")
    if not dry_run_report.exists():
        raise ApplySafetyError(f"Dry-run report is missing: {dry_run_report}")
    if not correction_report.exists():
        raise ApplySafetyError(f"Correction report is missing: {correction_report}")

    report_mtime = dry_run_report.stat().st_mtime
    stale_sources = [correction_report]
    for config in CATEGORY_CONFIG.values():
        workbook = input_dir / config["workbook"]
        if not workbook.exists():
            raise ApplySafetyError(f"Corrected workbook is missing: {workbook}")
        stale_sources.append(workbook)
    newer = [str(path) for path in stale_sources if path.stat().st_mtime > report_mtime]
    if newer:
        raise ApplySafetyError(
            "Dry-run report is stale; rerun backend/dry_run_corrected_compositions.py first. "
            f"Newer input(s): {', '.join(newer)}"
        )


def connect_database(mongo_uri_env: str, expected_db_name: str) -> Tuple[Any, Any, str]:
    mongo_uri = os.environ.get(mongo_uri_env)
    if not mongo_uri:
        raise ApplySafetyError(f"MongoDB URI environment variable {mongo_uri_env} is missing.")
    db_name = os.environ.get("DB_NAME", expected_db_name)
    if db_name != expected_db_name:
        raise ApplySafetyError(f"Unexpected database name {db_name!r}; expected {expected_db_name!r}.")
    from pymongo import MongoClient  # type: ignore
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client, client[db_name], db_name


def validate_database(db: Any, expected_db_name: str) -> None:
    db_name = getattr(db, "name", expected_db_name)
    if db_name != expected_db_name:
        raise ApplySafetyError(f"Unexpected database name {db_name!r}; expected {expected_db_name!r}.")
    existing = set(db.list_collection_names())
    missing = [name for name in REQUIRED_COLLECTIONS if name not in existing]
    if missing:
        raise ApplySafetyError(f"Required MongoDB collection(s) missing: {', '.join(missing)}")


def collection_counts(db: Any) -> Dict[str, int]:
    return {name: int(db[name].count_documents({})) for name in REQUIRED_COLLECTIONS}


def validate_no_forbidden_collection_methods_called(db: Any) -> None:
    for name in REQUIRED_COLLECTIONS:
        collection = db[name]
        for method in FORBIDDEN_WRITE_METHODS:
            calls = getattr(collection, f"{method}_calls", None)
            if calls:
                raise ApplySafetyError(f"Forbidden MongoDB method was called: {name}.{method}")


def make_update_fields(document: Dict[str, Any], corrected_composition: str, parser_type: str) -> Dict[str, Any]:
    metadata = parsed_metadata(corrected_composition, parser_type)
    update_fields: Dict[str, Any] = {"active_substances_raw": metadata["active_substances_raw"]}
    if "active_substances" in document:
        update_fields["active_substances"] = metadata["active_substances"]
    if "composition" in document:
        update_fields["composition"] = corrected_composition
    if "composition_warnings" in document:
        update_fields["composition_warnings"] = metadata["composition_warnings"]
    if "has_composition_warning" in document:
        update_fields["has_composition_warning"] = metadata["has_composition_warning"]
    forbidden = set(update_fields) - ALLOWED_UPDATE_FIELDS
    if forbidden:
        raise ApplySafetyError(f"Internal error: forbidden update field(s): {', '.join(sorted(forbidden))}")
    return update_fields


def changed_keys(before: Dict[str, Any], after_fields: Dict[str, Any]) -> List[str]:
    return [key for key, value in after_fields.items() if before.get(key) != value]


def _row_key(row: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    return (
        row.get("pesticide_category", ""),
        row.get("product_name", ""),
        row.get("product_key", ""),
        row.get("source_row", ""),
        row.get("row_identity_signature", ""),
    )


def validate_saved_report_matches_current(saved_rows: Sequence[Dict[str, str]], current_rows: Sequence[Dict[str, str]]) -> None:
    saved = {_row_key(row): row.get("match_status", "") for row in saved_rows}
    current = {_row_key(row): row.get("match_status", "") for row in current_rows}
    if saved != current:
        raise ApplySafetyError("Dry-run report is stale or differs from freshly validated matching results.")


def build_current_plan(db: Any, input_dir: Path, expected_safe_count: int, dry_run_report: Path) -> Tuple[List[ApplyTarget], List[Dict[str, str]], Dict[str, int]]:
    saved_rows = load_csv_rows(dry_run_report)
    corrected_rows = build_corrected_rows(input_dir=input_dir)
    current_rows: List[Dict[str, str]] = []
    targets: List[ApplyTarget] = []

    for corrected in corrected_rows:
        config = CATEGORY_CONFIG[corrected.category]
        collection_name = config["collection"]
        collection = db[collection_name]
        row = classify_corrected_row(collection, corrected)
        current_rows.append(row)
        if row["match_status"] != "safe_update_candidate":
            continue
        if normalize_text(row["product_name"]).find(PROTECTED_PRODUCT_FRAGMENT) != -1:
            raise ApplySafetyError("Protected product Протект Комби was classified as safe_update_candidate; aborting.")
        match_result = find_mongo_matches(collection, corrected)
        if len(match_result.matches) != 1:
            raise ApplySafetyError(f"Safe row no longer has exactly one match: {row['product_name']}")
        document = dict(match_result.matches[0])
        update_fields = make_update_fields(document, corrected.corrected_composition, config["parser_type"])
        if not changed_keys(document, update_fields):
            raise ApplySafetyError(f"Safe row has no real composition field changes: {row['product_name']}")
        targets.append(ApplyTarget(
            collection_name=collection_name,
            document_id=document.get("_id"),
            row=row,
            original_document=document,
            update_fields=update_fields,
            identity_signature=row["row_identity_signature"],
            dry_run_composition=row["current_mongo_composition"],
        ))

    validate_saved_report_matches_current(saved_rows, current_rows)
    counts = Counter(row["match_status"] for row in current_rows)
    if counts.get("safe_update_candidate", 0) != expected_safe_count:
        raise ApplySafetyError(
            f"Safe-update count mismatch: current={counts.get('safe_update_candidate', 0)}, expected={expected_safe_count}."
        )
    blocking = {status: counts.get(status, 0) for status in BLOCKING_STATUSES if counts.get(status, 0)}
    if blocking:
        raise ApplySafetyError(f"Blocking dry-run statuses are present: {blocking}")
    for row in current_rows:
        if row["match_status"] in NEVER_UPDATE_STATUSES and row.get("safe_to_update") == "yes":
            raise ApplySafetyError(f"Unsafe row is marked safe: {row['product_name']} / {row['match_status']}")
    if len(targets) != expected_safe_count:
        raise ApplySafetyError(f"Prepared target count mismatch: targets={len(targets)}, expected={expected_safe_count}")
    return targets, current_rows, dict(counts)


def create_backup(targets: Sequence[ApplyTarget], backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"composition_backup_{stamp}.json"
    payload = {
        "created_at": utc_timestamp(),
        "purpose": "mongodb composition apply backup",
        "allowed_fields": sorted(ALLOWED_UPDATE_FIELDS),
        "records": [
            {
                "collection": target.collection_name,
                "_id": json_safe(target.document_id),
                "original_id_serialized": str(target.document_id),
                "timestamp": utc_timestamp(),
                "update_identity_signature": target.identity_signature,
                "dry_run_composition": target.dry_run_composition,
                "planned_update_fields": sorted(target.update_fields),
                "original_document": json_safe(target.original_document),
            }
            for target in targets
        ],
    }
    backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return backup_path


def supports_transactions(client: Any) -> bool:
    if client is None or not hasattr(client, "start_session"):
        return False
    try:
        with client.start_session() as session:
            with session.start_transaction():
                return True
    except Exception:
        return False


def verify_target_unchanged(collection: Any, target: ApplyTarget) -> Dict[str, Any]:
    current = collection.find_one({"_id": target.document_id})
    if not current:
        raise ApplySafetyError(f"Target document disappeared before update: {target.collection_name}/{target.document_id}")
    if current.get("active_substances_raw", "") != target.dry_run_composition:
        raise ApplySafetyError(
            f"Changed-since-dry-run composition detected for {target.collection_name}/{target.document_id}; aborting."
        )
    for field in ("product_key", "product_name", "registration_number", "crop", "target_object", "rate_raw", "application_method"):
        if current.get(field) != target.original_document.get(field):
            raise ApplySafetyError(f"Changed-since-dry-run identity field {field} for {target.collection_name}/{target.document_id}")
    return current


def apply_targets(db: Any, targets: Sequence[ApplyTarget], session: Any = None) -> List[Dict[str, str]]:
    report_rows: List[Dict[str, str]] = []
    for target in targets:
        collection = db[target.collection_name]
        before = verify_target_unchanged(collection, target)
        unrelated_before = {k: json_safe(v) for k, v in before.items() if k not in ALLOWED_UPDATE_FIELDS}
        result = collection.update_one(
            {"_id": target.document_id, "active_substances_raw": target.dry_run_composition},
            {"$set": target.update_fields},
            session=session,
        )
        if result.matched_count != 1 or result.modified_count not in (0, 1):
            raise ApplySafetyError(
                f"Unexpected update result for {target.collection_name}/{target.document_id}: "
                f"matched={result.matched_count}, modified={result.modified_count}"
            )
        after = collection.find_one({"_id": target.document_id})
        if not after:
            raise ApplySafetyError(f"Target document disappeared after update: {target.collection_name}/{target.document_id}")
        unrelated_after = {k: json_safe(v) for k, v in after.items() if k not in ALLOWED_UPDATE_FIELDS}
        if unrelated_before != unrelated_after:
            raise ApplySafetyError(f"Unrelated field changed for {target.collection_name}/{target.document_id}; aborting.")
        report_rows.append({
            "collection": target.collection_name,
            "product_name": target.row["product_name"],
            "row_identity_signature": target.identity_signature,
            "match_status": target.row["match_status"],
            "action": "updated" if result.modified_count == 1 else "unchanged",
            "matched_count": str(result.matched_count),
            "modified_count": str(result.modified_count),
            "message": "composition fields applied",
        })
    return report_rows


def verify_after_apply(db: Any, targets: Sequence[ApplyTarget], before_counts: Dict[str, int], current_rows: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    after_counts = collection_counts(db)
    if before_counts != after_counts:
        raise ApplySafetyError(f"MongoDB document counts changed: before={before_counts}, after={after_counts}")
    protected_rows = [row for row in current_rows if PROTECTED_PRODUCT_FRAGMENT in normalize_text(row.get("product_name"))]
    for row in protected_rows:
        if row.get("match_status") != "unresolved_concentration_skip" or row.get("safe_to_update") != "no":
            raise ApplySafetyError("Протект Комби protection check failed.")
    for target in targets:
        doc = db[target.collection_name].find_one({"_id": target.document_id})
        if not doc:
            raise ApplySafetyError(f"Updated document missing: {target.collection_name}/{target.document_id}")
        for field, value in target.update_fields.items():
            if doc.get(field) != value:
                raise ApplySafetyError(f"Corrected field {field} did not match MongoDB after apply.")
        for field, value in target.original_document.items():
            if field not in ALLOWED_UPDATE_FIELDS and doc.get(field) != value:
                raise ApplySafetyError(f"Unrelated field {field} changed after apply.")
    return {"before_counts": before_counts, "after_counts": after_counts, "protect_combi_unchanged": bool(protected_rows)}


def write_apply_outputs(report_rows: Sequence[Dict[str, str]], summary: Dict[str, Any], output_dir: Path) -> Tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "mongodb_composition_apply_report.csv"
    summary_path = output_dir / "mongodb_composition_apply_summary.md"
    with report_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(report_rows)
    lines = [
        "# MongoDB composition apply summary",
        "",
        f"Generated at: {utc_timestamp()}",
        f"Expected safe updates: {summary['expected_safe_count']}",
        f"Attempted: {summary['attempted']}",
        f"Matched: {summary['matched']}",
        f"Modified: {summary['modified']}",
        f"Unchanged: {summary['unchanged']}",
        f"Skipped: {summary['skipped']}",
        f"Failed: {summary['failed']}",
        f"Collections affected: {', '.join(summary['collections_affected']) or 'none'}",
        f"Backup file path: {summary['backup_file']}",
        f"Transaction mode: {summary['transaction_mode']}",
        f"Протект Комби unchanged confirmation: {summary['protect_combi_unchanged']}",
        "Document counts before and after:",
        f"- Before: {summary['before_counts']}",
        f"- After: {summary['after_counts']}",
        f"Rollback command: python backend/rollback_corrected_compositions.py --backup-file {summary['backup_file']} --apply --confirm ROLLBACK_COMPOSITION_UPDATES",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path, summary_path


def run_guarded_apply(
    db: Any,
    *,
    client: Any = None,
    input_dir: Path = DEFAULT_INPUT_DIR,
    dry_run_report: Path = DEFAULT_DRY_RUN_REPORT,
    correction_report: Path = DEFAULT_CORRECTION_REPORT,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    expected_safe_count: int = DEFAULT_EXPECTED_SAFE_COUNT,
    apply: bool = False,
    confirm: Optional[str] = None,
    validate_files: bool = True,
) -> Dict[str, Any]:
    if validate_files:
        validate_input_files(input_dir, dry_run_report, correction_report)
    validate_database(db, EXPECTED_DATABASE_NAME)
    before_counts = collection_counts(db)
    targets, current_rows, status_counts = build_current_plan(db, input_dir, expected_safe_count, dry_run_report)

    if not apply:
        return {
            "apply_enabled": False,
            "message": "Apply mode is disabled; validation only; MongoDB writes performed: 0.",
            "expected_safe_count": expected_safe_count,
            "attempted": 0,
            "status_counts": status_counts,
        }
    if confirm != APPLY_CONFIRMATION:
        return {
            "apply_enabled": False,
            "message": "Wrong or missing confirmation; MongoDB writes performed: 0.",
            "expected_safe_count": expected_safe_count,
            "attempted": 0,
            "status_counts": status_counts,
        }

    backup_file = create_backup(targets, backup_dir)
    transaction_mode = "transaction" if supports_transactions(client) else "sequential_with_rollback_file"
    if transaction_mode == "transaction" and client is not None:
        with client.start_session() as session:
            with session.start_transaction():
                report_rows = apply_targets(db, targets, session=session)
    else:
        report_rows = apply_targets(db, targets)
    validate_no_forbidden_collection_methods_called(db)
    verification = verify_after_apply(db, targets, before_counts, current_rows)
    modified = sum(int(row["modified_count"]) for row in report_rows)
    matched = sum(int(row["matched_count"]) for row in report_rows)
    summary = {
        "apply_enabled": True,
        "expected_safe_count": expected_safe_count,
        "attempted": len(targets),
        "matched": matched,
        "modified": modified,
        "unchanged": len(targets) - modified,
        "skipped": len(current_rows) - len(targets),
        "failed": 0,
        "collections_affected": sorted({target.collection_name for target in targets}),
        "backup_file": str(backup_file),
        "transaction_mode": transaction_mode,
        "status_counts": status_counts,
        **verification,
    }
    write_apply_outputs(report_rows, summary, DEFAULT_OUTPUT_DIR)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guardedly apply approved MongoDB composition corrections.")
    parser.add_argument("--apply", action="store_true", help="Enable live writes. Without this flag the script validates only.")
    parser.add_argument("--confirm", help=f"Required confirmation text for live writes: {APPLY_CONFIRMATION}")
    parser.add_argument("--expected-safe-count", type=int, default=DEFAULT_EXPECTED_SAFE_COUNT, help="Expected number of safe-update rows.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory with corrected workbooks.")
    parser.add_argument("--dry-run-report", type=Path, default=DEFAULT_DRY_RUN_REPORT, help="Successful dry-run CSV report.")
    parser.add_argument("--correction-report", type=Path, default=DEFAULT_CORRECTION_REPORT, help="Correction source CSV report.")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR, help="Directory for JSON backups.")
    parser.add_argument("--mongo-uri-env", default="MONGO_URL", help="Environment variable that contains the MongoDB URI.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    print("MongoDB composition guarded updater starting.")
    print(f"Apply mode enabled: {args.apply}")
    print(f"Mongo URI env var: {args.mongo_uri_env} (value hidden)")
    if not args.apply:
        print("Apply mode is disabled; validation only; MongoDB writes performed: 0.")
    try:
        client, db, _db_name = connect_database(args.mongo_uri_env, EXPECTED_DATABASE_NAME)
        result = run_guarded_apply(
            db,
            client=client,
            input_dir=args.input_dir,
            dry_run_report=args.dry_run_report,
            correction_report=args.correction_report,
            backup_dir=args.backup_dir,
            expected_safe_count=args.expected_safe_count,
            apply=args.apply,
            confirm=args.confirm,
        )
    except Exception as exc:
        print(f"Guarded updater refused to continue: {exc}", file=sys.stderr)
        return 2
    print(result["message"] if "message" in result else "Apply completed and verified.")
    if result.get("apply_enabled"):
        print(f"Backup file: {result['backup_file']}")
        print(f"Transaction mode: {result['transaction_mode']}")
        print(f"Modified documents: {result['modified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
