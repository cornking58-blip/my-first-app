import unittest

from backend.dry_run_corrected_compositions import (
    CorrectedRow,
    DryRunWriteBlocked,
    SafeMongoCollection,
    classify_corrected_row,
)


class FakeCollection:
    def __init__(self, records):
        self.records = records
        self.write_calls = []

    def find(self, query):
        def matches(record):
            return all(record.get(key) == value for key, value in query.items())
        return [record for record in self.records if matches(record)]

    def update_one(self, *args, **kwargs):
        self.write_calls.append((args, kwargs))
        raise AssertionError("underlying update_one should not be called through guard")


class DryRunCorrectedCompositionTests(unittest.TestCase):
    def corrected(self, **overrides):
        data = dict(
            category="herbicides",
            corrected_source_file="herbicides_raw_FINAL_checked_corrected.xlsx",
            source_sheet="herbicides_raw",
            source_row="10",
            product_name="Тест",
            product_key="Тест|123",
            slug_product_key="тест-123",
            registration_number="123",
            record_id=None,
            crop="Пшеница",
            target_object="Сорные растения",
            rate_raw="1,0 л/га",
            application_method="Опрыскивание",
            manufacturer="Завод",
            formulation="КЭ",
            original_composition="(100 г/л вещество)",
            corrected_composition="(100 г/л вещество)",
            report_status="eligible",
            report_notes="",
        )
        data.update(overrides)
        return CorrectedRow(**data)

    def record(self, **overrides):
        data = dict(
            _id="0123456789abcdef",
            product_name="Тест",
            product_key="Тест|123",
            registration_number="123",
            record_id=None,
            crop="Пшеница",
            target_object="Сорные растения",
            rate_raw="1,0 л/га",
            application_method="Опрыскивание",
            manufacturer="Завод",
            formulation="КЭ",
            active_substances_raw="(100 г/л вещество)",
        )
        data.update(overrides)
        return data

    def test_exact_single_match_no_change(self):
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([self.record()])), self.corrected())
        self.assertEqual(result["match_status"], "exact_match_no_change")
        self.assertEqual(result["safe_to_update"], "no")
        self.assertEqual(result["mongo_record_id_masked"], "0123…cdef")

    def test_one_safe_composition_change(self):
        corrected = self.corrected(corrected_composition="(150 г/л вещество)")
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([self.record()])), corrected)
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["safe_to_update"], "yes")
        self.assertIn("active_substances_raw", result["fields_that_would_change"])

    def test_ambiguous_duplicate_matches(self):
        records = [self.record(_id="aaaaaaaaaaaa", active_substances_raw="(90 г/л вещество)"), self.record(_id="bbbbbbbbbbbb", active_substances_raw="(200 г/л вещество)")]
        result = classify_corrected_row(SafeMongoCollection(FakeCollection(records)), self.corrected(corrected_composition="(150 г/л вещество)"))
        self.assertEqual(result["match_status"], "ambiguous_mongo_match")
        self.assertEqual(result["safe_to_update"], "no")

    def test_true_duplicate_mongo_records_same_identity(self):
        records = [self.record(_id="aaaaaaaaaaaa"), self.record(_id="bbbbbbbbbbbb")]
        result = classify_corrected_row(SafeMongoCollection(FakeCollection(records)), self.corrected(corrected_composition="(150 г/л вещество)"))
        self.assertEqual(result["match_status"], "true_duplicate_mongo_records")
        self.assertEqual(result["safe_to_update"], "no")


    def test_same_product_different_crop_matches_correct_crop_row(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", crop="Ячмень"),
            self.record(_id="bbbbbbbbbbbb", crop="Пшеница"),
        ]
        result = classify_corrected_row(SafeMongoCollection(FakeCollection(records)), self.corrected(corrected_composition="(150 г/л вещество)"))
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["mongo_record_id_masked"], "bbbb…bbbb")
        self.assertEqual(result["match_strategy"], "level_2_product_key_application_identity")

    def test_same_product_same_crop_different_target_matches_correct_target_row(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", target_object="Болезни"),
            self.record(_id="bbbbbbbbbbbb", target_object="Сорные растения"),
        ]
        result = classify_corrected_row(SafeMongoCollection(FakeCollection(records)), self.corrected(corrected_composition="(150 г/л вещество)"))
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["mongo_record_id_masked"], "bbbb…bbbb")

    def test_same_product_same_crop_target_different_rate_matches_correct_rate_row(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", rate_raw="2,0 л/га"),
            self.record(_id="bbbbbbbbbbbb", rate_raw="1,0 л/га"),
        ]
        result = classify_corrected_row(SafeMongoCollection(FakeCollection(records)), self.corrected(corrected_composition="(150 г/л вещество)"))
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["mongo_record_id_masked"], "bbbb…bbbb")

    def test_same_product_same_crop_target_rate_different_method_matches_correct_method_row(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", application_method="Протравливание"),
            self.record(_id="bbbbbbbbbbbb", application_method="Опрыскивание"),
        ]
        result = classify_corrected_row(SafeMongoCollection(FakeCollection(records)), self.corrected(corrected_composition="(150 г/л вещество)"))
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["mongo_record_id_masked"], "bbbb…bbbb")

    def test_record_id_match_has_highest_priority(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", record_id="1", crop="Ячмень"),
            self.record(_id="bbbbbbbbbbbb", record_id="2", crop="Пшеница"),
        ]
        result = classify_corrected_row(
            SafeMongoCollection(FakeCollection(records)),
            self.corrected(record_id="1", corrected_composition="(150 г/л вещество)"),
        )
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["mongo_record_id_masked"], "aaaa…aaaa")
        self.assertEqual(result["match_strategy"], "level_1_record_id")

    def test_numeric_record_id_matches_excel_text_record_id(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", record_id=1, crop="Ячмень"),
            self.record(_id="bbbbbbbbbbbb", record_id=2, crop="Пшеница"),
        ]
        result = classify_corrected_row(
            SafeMongoCollection(FakeCollection(records)),
            self.corrected(record_id="1.0", corrected_composition="(150 г/л вещество)"),
        )
        self.assertEqual(result["match_status"], "safe_update_candidate")
        self.assertEqual(result["mongo_record_id_masked"], "aaaa…aaaa")
        self.assertEqual(result["match_strategy"], "level_1_record_id")

    def test_product_name_only_matching_is_disabled(self):
        corrected = self.corrected(
            product_key="Тест|",
            registration_number=None,
            crop=None,
            target_object=None,
            rate_raw=None,
            application_method=None,
        )
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([self.record(product_key="Тест|")])), corrected)
        self.assertEqual(result["match_status"], "mongo_record_not_found")
        self.assertIn("product-name-only", result["ambiguity_reason"])

    def test_ambiguous_rows_remain_ambiguous_after_narrowing(self):
        records = [
            self.record(_id="aaaaaaaaaaaa", manufacturer="Завод А"),
            self.record(_id="bbbbbbbbbbbb", manufacturer="Завод Б"),
        ]
        result = classify_corrected_row(
            SafeMongoCollection(FakeCollection(records)),
            self.corrected(manufacturer=None, corrected_composition="(150 г/л вещество)"),
        )
        self.assertEqual(result["match_status"], "ambiguous_mongo_match")
        self.assertEqual(result["safe_to_update"], "no")

    def test_missing_mongo_record(self):
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([])), self.corrected())
        self.assertEqual(result["match_status"], "mongo_record_not_found")
        self.assertEqual(result["safe_to_update"], "no")

    def test_manual_review_row_skipped(self):
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([self.record()])), self.corrected(report_status="manual_review_skip"))
        self.assertEqual(result["match_status"], "manual_review_skip")
        self.assertEqual(result["safe_to_update"], "no")

    def test_unresolved_concentration_row_skipped(self):
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([self.record()])), self.corrected(report_status="unresolved_concentration_skip"))
        self.assertEqual(result["match_status"], "unresolved_concentration_skip")
        self.assertEqual(result["safe_to_update"], "no")

    def test_unrelated_field_difference_does_not_become_update(self):
        result = classify_corrected_row(
            SafeMongoCollection(FakeCollection([self.record(formulation="ВДГ")])),
            self.corrected(corrected_composition="(150 г/л вещество)"),
        )
        self.assertEqual(result["match_status"], "ambiguous_mongo_match")
        self.assertIn("formulation", result["skip_reason"])
        self.assertEqual(result["safe_to_update"], "no")

    def test_no_write_methods_called_guard_blocks_writes(self):
        guarded = SafeMongoCollection(FakeCollection([self.record()]))
        with self.assertRaises(DryRunWriteBlocked):
            guarded.update_one({"product_key": "Тест|123"}, {"$set": {"active_substances_raw": "x"}})
        self.assertEqual(guarded.write_attempts, ["update_one"])

    def test_protect_combi_not_updated_with_invented_prothioconazole_concentration(self):
        corrected = self.corrected(
            category="seed-treatments",
            corrected_source_file="seed_treatments_FINAL_v2_corrected.xlsx",
            source_sheet="seed_treatments_raw",
            product_name="Протект Комби",
            product_key="Протект Комби|321",
            slug_product_key="протект-комби-321",
            original_composition="(100 г/л тебуконазол + протиоконазол)",
            corrected_composition="(100 г/л тебуконазол + протиоконазол)",
            report_status="unresolved_concentration_skip",
        )
        mongo_record = self.record(
            product_name="Протект Комби",
            product_key="Протект Комби|321",
            registration_number="123",
            active_substances_raw="(100 г/л тебуконазол + протиоконазол)",
        )
        result = classify_corrected_row(SafeMongoCollection(FakeCollection([mongo_record])), corrected)
        self.assertEqual(result["match_status"], "unresolved_concentration_skip")
        self.assertEqual(result["safe_to_update"], "no")
        self.assertNotEqual(result["match_status"], "safe_update_candidate")


if __name__ == "__main__":
    unittest.main()
