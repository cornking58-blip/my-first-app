import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import apply_corrected_compositions as applymod
from backend import rollback_corrected_compositions as rollbackmod


class FakeResult:
    def __init__(self, matched_count, modified_count):
        self.matched_count = matched_count
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, docs):
        self.docs = {doc["_id"]: dict(doc) for doc in docs}
        self.update_one_calls = []
        self.update_many_calls = []
        self.delete_one_calls = []
        self.delete_many_calls = []
        self.insert_one_calls = []
        self.insert_many_calls = []
        self.replace_one_calls = []
        self.drop_calls = []
        self.on_update = None

    def count_documents(self, _query):
        return len(self.docs)

    def find_one(self, query):
        doc = self.docs.get(query.get("_id"))
        return dict(doc) if doc else None

    def update_one(self, query, update, session=None):
        if self.on_update:
            self.on_update()
        self.update_one_calls.append((query, update, session))
        doc = self.docs.get(query.get("_id"))
        if not doc:
            return FakeResult(0, 0)
        for key, value in query.items():
            if doc.get(key) != value:
                return FakeResult(0, 0)
        modified = 0
        for key, value in update.get("$set", {}).items():
            if doc.get(key) != value:
                modified = 1
            doc[key] = value
        return FakeResult(1, modified)

    def update_many(self, *args, **kwargs):
        self.update_many_calls.append((args, kwargs))
        raise AssertionError("update_many must never be called")

    def delete_one(self, *args, **kwargs):
        self.delete_one_calls.append((args, kwargs))
        raise AssertionError("delete_one must never be called")

    def delete_many(self, *args, **kwargs):
        self.delete_many_calls.append((args, kwargs))
        raise AssertionError("delete_many must never be called")

    def insert_one(self, *args, **kwargs):
        self.insert_one_calls.append((args, kwargs))
        raise AssertionError("insert_one must never be called")

    def insert_many(self, *args, **kwargs):
        self.insert_many_calls.append((args, kwargs))
        raise AssertionError("insert_many must never be called")

    def replace_one(self, *args, **kwargs):
        self.replace_one_calls.append((args, kwargs))
        raise AssertionError("replace_one must never be called")

    def drop(self, *args, **kwargs):
        self.drop_calls.append((args, kwargs))
        raise AssertionError("drop must never be called")


class FakeDB:
    name = "herbicides_db"

    def __init__(self, collections=None):
        self.collections = collections or {}
        for name in applymod.REQUIRED_COLLECTIONS:
            self.collections.setdefault(name, FakeCollection([]))

    def __getitem__(self, name):
        return self.collections[name]

    def list_collection_names(self):
        return list(self.collections)


def base_doc():
    return {
        "_id": "doc-1",
        "product_name": "Safe Product",
        "product_key": "Safe Product|123",
        "registration_number": "123",
        "crop": "crop",
        "target_object": "target",
        "rate_raw": "1 л/га",
        "application_method": "spray",
        "active_substances_raw": "old substance, 10 г/л",
        "active_substances": [{"name": "old substance", "concentration": "10 г/л"}],
        "composition": "old substance, 10 г/л",
        "composition_warnings": [],
        "has_composition_warning": False,
        "manufacturer": "Do not change",
        "rate_raw_extra": {"nested": [1, 2, 3]},
    }


def target_for(doc=None, collection="herbicide_records"):
    document = dict(doc or base_doc())
    update_fields = applymod.make_update_fields(document, "new substance, 20 г/л", "herbicide")
    return applymod.ApplyTarget(
        collection_name=collection,
        document_id=document["_id"],
        row={"product_name": document["product_name"], "match_status": "safe_update_candidate"},
        original_document=document,
        update_fields=update_fields,
        identity_signature="sig-1",
        dry_run_composition=document["active_substances_raw"],
    )


def rows(extra=None):
    data = [
        {"product_name": "Safe Product", "match_status": "safe_update_candidate", "safe_to_update": "yes"},
        {"product_name": "Manual Product", "match_status": "manual_review_skip", "safe_to_update": "no"},
        {"product_name": "Unresolved Product", "match_status": "unresolved_concentration_skip", "safe_to_update": "no"},
        {"product_name": "Протект Комби", "match_status": "unresolved_concentration_skip", "safe_to_update": "no"},
    ]
    if extra:
        data.extend(extra)
    return data


class ApplyCorrectedCompositionsTests(unittest.TestCase):
    def run_with_plan(self, db, targets, current_rows=None, expected=1, apply=False, confirm=None, backup_dir=None):
        current_rows = current_rows if current_rows is not None else rows()
        counts = {"safe_update_candidate": len(targets)}
        with patch.object(applymod, "build_current_plan", return_value=(targets, current_rows, counts)):
            return applymod.run_guarded_apply(
                db,
                input_dir=Path("unused"),
                dry_run_report=Path("unused.csv"),
                correction_report=Path("unused-report.csv"),
                backup_dir=backup_dir or Path(tempfile.mkdtemp()),
                expected_safe_count=expected,
                apply=apply,
                confirm=confirm,
                validate_files=False,
            )

    def test_default_mode_performs_zero_writes(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        result = self.run_with_plan(db, [target_for()], apply=False)
        self.assertFalse(result["apply_enabled"])
        self.assertEqual(db["herbicide_records"].update_one_calls, [])

    def test_wrong_confirmation_performs_zero_writes(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        result = self.run_with_plan(db, [target_for()], apply=True, confirm="WRONG")
        self.assertFalse(result["apply_enabled"])
        self.assertEqual(db["herbicide_records"].update_one_calls, [])

    def test_expected_count_mismatch_aborts(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        with patch.object(applymod, "build_current_plan", side_effect=applymod.ApplySafetyError("Safe-update count mismatch")):
            with self.assertRaises(applymod.ApplySafetyError):
                applymod.run_guarded_apply(db, expected_safe_count=184, validate_files=False)

    def test_safe_update_candidate_updates_exactly_one_document(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        result = self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION)
        self.assertTrue(result["apply_enabled"])
        self.assertEqual(len(db["herbicide_records"].update_one_calls), 1)
        self.assertEqual(result["matched"], 1)

    def test_manual_review_row_is_never_updated(self):
        db = FakeDB()
        result = self.run_with_plan(db, [], current_rows=rows(), expected=0, apply=True, confirm=applymod.APPLY_CONFIRMATION)
        self.assertEqual(result["attempted"], 0)
        self.assertEqual(db["herbicide_records"].update_one_calls, [])

    def test_unresolved_concentration_row_is_never_updated(self):
        db = FakeDB()
        result = self.run_with_plan(db, [], current_rows=rows(), expected=0, apply=True, confirm=applymod.APPLY_CONFIRMATION)
        self.assertEqual(result["attempted"], 0)
        self.assertEqual(db["fungicide_records"].update_one_calls, [])

    def test_protect_combi_is_never_updated(self):
        db = FakeDB()
        result = self.run_with_plan(db, [], current_rows=rows(), expected=0, apply=True, confirm=applymod.APPLY_CONFIRMATION)
        self.assertTrue(result["protect_combi_unchanged"])
        self.assertEqual(db["seed_treatment_records"].update_one_calls, [])

    def test_ambiguous_match_aborts(self):
        db = FakeDB()
        with patch.object(applymod, "build_current_plan", side_effect=applymod.ApplySafetyError("ambiguous")):
            with self.assertRaises(applymod.ApplySafetyError):
                applymod.run_guarded_apply(db, validate_files=False)

    def test_missing_record_aborts(self):
        db = FakeDB()
        with patch.object(applymod, "build_current_plan", side_effect=applymod.ApplySafetyError("not found")):
            with self.assertRaises(applymod.ApplySafetyError):
                applymod.run_guarded_apply(db, validate_files=False)

    def test_changed_since_dry_run_record_aborts(self):
        changed = base_doc()
        changed["active_substances_raw"] = "someone changed this"
        db = FakeDB({"herbicide_records": FakeCollection([changed])})
        with self.assertRaises(applymod.ApplySafetyError):
            self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION)

    def test_backup_is_created_before_first_write(self):
        temp_dir = Path(tempfile.mkdtemp())
        collection = FakeCollection([base_doc()])
        collection.on_update = lambda: self.assertTrue(list(temp_dir.glob("composition_backup_*.json")))
        db = FakeDB({"herbicide_records": collection})
        self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION, backup_dir=temp_dir)

    def test_backup_contains_full_original_document(self):
        temp_dir = Path(tempfile.mkdtemp())
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION, backup_dir=temp_dir)
        backup = next(temp_dir.glob("composition_backup_*.json"))
        payload = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual(payload["records"][0]["original_document"]["manufacturer"], "Do not change")

    def test_only_allowed_composition_fields_change(self):
        original = base_doc()
        db = FakeDB({"herbicide_records": FakeCollection([original])})
        self.run_with_plan(db, [target_for(original)], apply=True, confirm=applymod.APPLY_CONFIRMATION)
        updated = db["herbicide_records"].docs["doc-1"]
        changed = {key for key in updated if updated.get(key) != original.get(key)}
        self.assertTrue(changed <= applymod.ALLOWED_UPDATE_FIELDS)

    def test_unrelated_fields_remain_value_equivalent(self):
        original = base_doc()
        db = FakeDB({"herbicide_records": FakeCollection([original])})
        self.run_with_plan(db, [target_for(original)], apply=True, confirm=applymod.APPLY_CONFIRMATION)
        updated = db["herbicide_records"].docs["doc-1"]
        self.assertEqual(updated["manufacturer"], original["manufacturer"])
        self.assertEqual(updated["rate_raw_extra"], original["rate_raw_extra"])

    def test_update_many_delete_insert_replace_are_never_called(self):
        collection = FakeCollection([base_doc()])
        db = FakeDB({"herbicide_records": collection})
        self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION)
        self.assertEqual(collection.update_many_calls, [])
        self.assertEqual(collection.delete_one_calls, [])
        self.assertEqual(collection.delete_many_calls, [])
        self.assertEqual(collection.insert_one_calls, [])
        self.assertEqual(collection.insert_many_calls, [])
        self.assertEqual(collection.replace_one_calls, [])

    def test_rollback_restores_original_composition_fields(self):
        temp_dir = Path(tempfile.mkdtemp())
        original = base_doc()
        collection = FakeCollection([original])
        db = FakeDB({"herbicide_records": collection})
        self.run_with_plan(db, [target_for(original)], apply=True, confirm=applymod.APPLY_CONFIRMATION, backup_dir=temp_dir)
        self.assertEqual(collection.docs["doc-1"]["active_substances_raw"], "new substance, 20 г/л")
        backup = next(temp_dir.glob("composition_backup_*.json"))
        result = rollbackmod.run_rollback(db, backup, apply=True, confirm=rollbackmod.ROLLBACK_CONFIRMATION)
        self.assertTrue(result["apply_enabled"])
        self.assertEqual(collection.docs["doc-1"]["active_substances_raw"], original["active_substances_raw"])

    def test_mongodb_document_counts_remain_unchanged(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        before = applymod.collection_counts(db)
        self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION)
        after = applymod.collection_counts(db)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
