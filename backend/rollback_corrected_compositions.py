"""Rollback composition updates from a guarded apply backup file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from apply_corrected_compositions import (
    ALLOWED_UPDATE_FIELDS,
    ApplySafetyError,
    EXPECTED_DATABASE_NAME,
    REQUIRED_COLLECTIONS,
    collection_counts,
    connect_database,
    validate_database,
)

ROLLBACK_CONFIRMATION = "ROLLBACK_COMPOSITION_UPDATES"


def load_backup(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise ApplySafetyError(f"Backup file is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApplySafetyError(f"Backup file is malformed JSON: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ApplySafetyError("Backup file is malformed: expected top-level records list.")
    for index, record in enumerate(payload["records"], start=1):
        if not isinstance(record, dict):
            raise ApplySafetyError(f"Backup record #{index} is malformed.")
        if record.get("collection") not in REQUIRED_COLLECTIONS:
            raise ApplySafetyError(f"Backup record #{index} has unexpected collection: {record.get('collection')!r}")
        if "original_document" not in record or not isinstance(record["original_document"], dict):
            raise ApplySafetyError(f"Backup record #{index} is missing full original_document.")
    return payload


def decode_mongo_value(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"$oid"}:
        from bson import ObjectId  # type: ignore
        return ObjectId(value["$oid"])
    if isinstance(value, dict):
        return {key: decode_mongo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_mongo_value(item) for item in value]
    return value


def original_id(original_document: Dict[str, Any], record: Dict[str, Any]) -> Any:
    return decode_mongo_value(original_document.get("_id", record.get("_id")))


def restore_fields(original_document: Dict[str, Any], planned_update_fields: Any = None) -> Dict[str, Any]:
    if planned_update_fields is None:
        candidate_fields = ALLOWED_UPDATE_FIELDS
    else:
        if not isinstance(planned_update_fields, list):
            raise ApplySafetyError("Backup record planned_update_fields must be a list when present.")
        candidate_fields = set(planned_update_fields)
    forbidden = set(candidate_fields) - ALLOWED_UPDATE_FIELDS
    if forbidden:
        raise ApplySafetyError(f"Backup asks rollback to restore forbidden field(s): {', '.join(sorted(forbidden))}")
    return {field: decode_mongo_value(original_document.get(field)) for field in candidate_fields if field in original_document}


def run_rollback(db: Any, backup_file: Path, *, apply: bool = False, confirm: Optional[str] = None) -> Dict[str, Any]:
    validate_database(db, EXPECTED_DATABASE_NAME)
    payload = load_backup(backup_file)
    before_counts = collection_counts(db)
    if not apply:
        return {
            "apply_enabled": False,
            "message": "Rollback apply mode is disabled; MongoDB writes performed: 0.",
            "mongodb_writes_performed_before_failure": 0,
            "records": len(payload["records"]),
        }
    if confirm != ROLLBACK_CONFIRMATION:
        return {
            "apply_enabled": False,
            "message": "Wrong or missing rollback confirmation; MongoDB writes performed: 0.",
            "mongodb_writes_performed_before_failure": 0,
            "records": len(payload["records"]),
        }

    matched = 0
    modified = 0
    for record in payload["records"]:
        collection_name = record["collection"]
        original_document = record["original_document"]
        doc_id = original_id(original_document, record)
        if doc_id is None:
            raise ApplySafetyError(f"Backup record for {collection_name} has no _id.")
        fields = restore_fields(original_document, record.get("planned_update_fields"))
        collection = db[collection_name]
        result = collection.update_one({"_id": doc_id}, {"$set": fields})
        if result.matched_count != 1 or result.modified_count not in (0, 1):
            raise ApplySafetyError(
                f"Unexpected rollback result for {collection_name}/{doc_id}: "
                f"matched={result.matched_count}, modified={result.modified_count}"
            )
        matched += result.matched_count
        modified += result.modified_count
    after_counts = collection_counts(db)
    if before_counts != after_counts:
        raise ApplySafetyError(f"MongoDB document counts changed during rollback: before={before_counts}, after={after_counts}")
    return {
        "apply_enabled": True,
        "records": len(payload["records"]),
        "matched": matched,
        "modified": modified,
        "mongodb_writes_performed_before_failure": 0,
        "before_counts": before_counts,
        "after_counts": after_counts,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rollback guarded MongoDB composition updates from a JSON backup.")
    parser.add_argument("--backup-file", type=Path, required=True, help="Backup JSON created by apply_corrected_compositions.py.")
    parser.add_argument("--apply", action="store_true", help="Enable live rollback writes.")
    parser.add_argument("--confirm", help=f"Required confirmation text: {ROLLBACK_CONFIRMATION}")
    parser.add_argument("--mongo-uri-env", default="MONGO_URL", help="Environment variable that contains the MongoDB URI.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    print("MongoDB composition rollback starting.")
    if not args.apply:
        print("Rollback apply mode is disabled; MongoDB writes performed: 0.")
    try:
        _client, db, _db_name = connect_database(args.mongo_uri_env, EXPECTED_DATABASE_NAME)
        result = run_rollback(db, args.backup_file, apply=args.apply, confirm=args.confirm)
    except Exception as exc:
        print(f"Rollback refused to continue: {exc}", file=sys.stderr)
        return 2
    print(result.get("message", "Rollback completed and verified."))
    if result.get("apply_enabled"):
        print(f"Restored records: {result['records']}")
        print(f"Modified documents: {result['modified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
