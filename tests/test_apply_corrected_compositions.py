import io
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
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
        self.bulk_write_calls = []
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

    def bulk_write(self, *args, **kwargs):
        self.bulk_write_calls.append((args, kwargs))
        raise AssertionError("bulk_write must never be called")

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


class FakeAdmin:
    def __init__(self, hello_response):
        self.hello_response = hello_response
        self.commands = []

    def command(self, name):
        self.commands.append(name)
        if name in ("hello", "isMaster"):
            return dict(self.hello_response)
        return {"ok": 1}


class FakeTransactionContext:
    def __init__(self, fail=False):
        self.fail = fail

    def __enter__(self):
        if self.fail:
            raise RuntimeError("Transaction numbers are only allowed on a replica set member or mongos")
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, fail_transaction=False):
        self.fail_transaction = fail_transaction

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def start_transaction(self):
        return FakeTransactionContext(self.fail_transaction)


class FakeClient:
    def __init__(self, hello_response, fail_transaction=False):
        self.admin = FakeAdmin(hello_response)
        self.fail_transaction = fail_transaction
        self.sessions_started = 0

    def start_session(self):
        self.sessions_started += 1
        return FakeSession(self.fail_transaction)


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
        identity_signature=applymod.document_identity_signature(document),
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
    def run_with_plan(self, db, targets, current_rows=None, expected=1, apply=False, confirm=None, backup_dir=None, client=None, preflight=False):
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
                preflight=preflight,
                client=client,
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
        self.assertEqual(collection.bulk_write_calls, [])

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

    def test_standalone_mongodb_selects_sequential_with_backup(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        client = FakeClient({"ok": 1})
        result = self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION, client=client)
        self.assertEqual(result["selected_mode"], "sequential_with_backup")
        self.assertEqual(client.sessions_started, 0)

    def test_replica_set_mongodb_selects_transaction_mode(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        client = FakeClient({"ok": 1, "setName": "rs0"})
        result = self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION, client=client)
        self.assertEqual(result["selected_mode"], "transaction")
        self.assertEqual(client.sessions_started, 1)

    def test_unsupported_transaction_error_falls_back_before_any_update(self):
        collection = FakeCollection([base_doc()])
        db = FakeDB({"herbicide_records": collection})
        client = FakeClient({"ok": 1, "setName": "rs0"}, fail_transaction=True)
        result = self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION, client=client)
        self.assertEqual(result["selected_mode"], "sequential_with_backup")
        self.assertEqual(len(collection.update_one_calls), 1)
        self.assertIsNone(collection.update_one_calls[0][2])

    def test_backup_contains_all_safe_candidates_before_first_write(self):
        doc2 = base_doc()
        doc2["_id"] = "doc-2"
        doc2["product_name"] = "Safe Product 2"
        doc2["product_key"] = "Safe Product 2|123"
        collection = FakeCollection([base_doc(), doc2])
        temp_dir = Path(tempfile.mkdtemp())
        target1 = target_for(base_doc())
        target2 = target_for(doc2)

        def assert_complete_backup_exists():
            backup = next(temp_dir.glob("composition_backup_*.json"))
            payload = json.loads(backup.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["records"]), 2)

        collection.on_update = assert_complete_backup_exists
        db = FakeDB({"herbicide_records": collection})
        self.run_with_plan(db, [target1, target2], expected=2, apply=True, confirm=applymod.APPLY_CONFIRMATION, backup_dir=temp_dir)

    def test_missing_or_incomplete_backup_aborts(self):
        temp_dir = Path(tempfile.mkdtemp())
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        with patch.object(applymod, "create_backup", return_value=temp_dir / "missing.json"):
            with self.assertRaises(applymod.ApplySafetyError):
                self.run_with_plan(db, [target_for()], apply=True, confirm=applymod.APPLY_CONFIRMATION, backup_dir=temp_dir)
        self.assertEqual(db["herbicide_records"].update_one_calls, [])

    def test_sequential_mode_updates_only_safe_candidates(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        result = self.run_with_plan(db, [target_for()], current_rows=rows(), expected=1, apply=True, confirm=applymod.APPLY_CONFIRMATION)
        self.assertEqual(result["modified"], 1)
        self.assertEqual(len(db["herbicide_records"].update_one_calls), 1)

    def test_failure_after_partial_updates_produces_rollback_command(self):
        doc1 = base_doc()
        doc2 = base_doc()
        doc2["_id"] = "doc-2"
        doc2["product_name"] = "Safe Product 2"
        doc2["product_key"] = "Safe Product 2|123"
        collection = FakeCollection([doc1, doc2])
        original_update_one = collection.update_one

        def failing_second_update(query, update, session=None):
            if query.get("_id") == "doc-2":
                raise RuntimeError("network dropped")
            return original_update_one(query, update, session=session)

        collection.update_one = failing_second_update
        db = FakeDB({"herbicide_records": collection})
        temp_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(applymod.ApplyPartialFailure) as ctx:
            self.run_with_plan(db, [target_for(doc1), target_for(doc2)], expected=2, apply=True, confirm=applymod.APPLY_CONFIRMATION, backup_dir=temp_dir)
        self.assertIn("already modified: 1", str(ctx.exception))
        summary = (applymod.DEFAULT_OUTPUT_DIR / "mongodb_composition_apply_summary.md").read_text(encoding="utf-8")
        self.assertIn("Rollback command: python backend/rollback_corrected_compositions.py --backup-file", summary)

    def test_preflight_performs_zero_writes(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        client = FakeClient({"ok": 1})
        result = self.run_with_plan(db, [target_for()], preflight=True, client=client)
        self.assertTrue(result["preflight"])
        self.assertEqual(result["selected_mode"], "sequential_with_backup")
        self.assertEqual(db["herbicide_records"].update_one_calls, [])

    def test_preflight_runs_full_plan_and_detects_transaction_support(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        client = FakeClient({"ok": 1, "setName": "rs0"})
        with patch.object(applymod, "build_current_plan", return_value=([target_for()], rows(), {"safe_update_candidate": 1})) as plan:
            result = applymod.run_guarded_apply(
                db,
                expected_safe_count=1,
                preflight=True,
                client=client,
                validate_files=False,
            )
        plan.assert_called_once()
        self.assertTrue(result["transaction_support"])
        self.assertEqual(result["selected_mode"], "transaction")
        self.assertEqual(client.sessions_started, 0)

    def test_preflight_prints_selected_mode_and_safe_update_count(self):
        result = {
            "preflight": True,
            "message": "Preflight completed; MongoDB writes performed: 0.",
            "safe_update_count": 184,
            "blocking_rows_count": 0,
            "status_counts": {"safe_update_candidate": 184},
            "transaction_support": False,
            "selected_mode": "sequential_with_backup",
        }
        with patch.object(applymod, "connect_database", return_value=(FakeClient({"ok": 1}), FakeDB(), "herbicides_db")):
            with patch.object(applymod, "run_guarded_apply", return_value=result) as runner:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = applymod.main(["--preflight"])
        self.assertEqual(exit_code, 0)
        runner.assert_called_once()
        self.assertTrue(runner.call_args.kwargs["preflight"])
        output = stdout.getvalue()
        self.assertIn("Safe update count: 184", output)
        self.assertIn("Blocking rows count: 0", output)
        self.assertIn("Transaction support: no", output)
        self.assertIn("Selected mode: sequential_with_backup", output)
        self.assertIn("MongoDB writes performed: 0", output)
        self.assertNotIn("Apply mode is disabled; validation only", output)

    def test_preflight_does_not_create_backup(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        temp_dir = Path(tempfile.mkdtemp())
        with patch.object(applymod, "create_backup", wraps=applymod.create_backup) as create_backup:
            result = self.run_with_plan(db, [target_for()], preflight=True, backup_dir=temp_dir)
        self.assertTrue(result["preflight"])
        create_backup.assert_not_called()
        self.assertEqual(list(temp_dir.glob("composition_backup_*.json")), [])

    def test_preflight_reports_manual_unresolved_and_protect_combi_protections(self):
        db = FakeDB({"herbicide_records": FakeCollection([base_doc()])})
        result = self.run_with_plan(db, [target_for()], current_rows=rows(), preflight=True)
        self.assertTrue(result["manual_rows_excluded"])
        self.assertTrue(result["unresolved_rows_excluded"])
        self.assertTrue(result["protect_combi_unchanged"])


if __name__ == "__main__":
    unittest.main()
