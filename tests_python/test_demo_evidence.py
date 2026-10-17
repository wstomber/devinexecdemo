"""The presentation app must never show missing, malformed, or mismatched evidence as a pass."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo"))
import evidence  # noqa: E402

HEADER = "record_no,claim_id,status,payment_cents,reason\n"
TOTALS = "records,paid,zero,invalid,payment_cents\n"


def write_batch(folder, cobol_rows, python_rows, cobol_total, python_total):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cobol-results.csv").write_text(HEADER + "".join(r + "\n" for r in cobol_rows))
    (folder / "python-results.csv").write_text(HEADER + "".join(r + "\n" for r in python_rows))
    (folder / "cobol-totals.csv").write_text(TOTALS + cobol_total + "\n")
    (folder / "python-totals.csv").write_text(TOTALS + python_total + "\n")


ROW = "0000000001,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE"
TOTAL = "0000000001,0000000001,0000000000,0000000000,000000000050000"


class ComparisonStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.report = self.tmp / "report.json"
        self.report.write_text(json.dumps({"result": "PASS"}))

    def status(self, folder, report=None):
        return evidence.comparison(folder, report, "TEST", "live")

    def test_identical_outputs_with_passing_verifier_pass(self):
        write_batch(self.tmp / "b", [ROW], [ROW], TOTAL, TOTAL)
        result = self.status(self.tmp / "b", self.report)
        self.assertEqual((result["status"], result["mismatches"], result["byte_identical"]), ("PASSED", 0, True))

    def test_one_cent_difference_fails(self):
        write_batch(self.tmp / "b", [ROW], [ROW.replace("0000050000", "0000050001")], TOTAL, TOTAL)
        result = self.status(self.tmp / "b", self.report)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["rows"][0][8], "MISMATCH")

    def test_missing_record_and_total_difference_fail(self):
        other = "0000000002,X2,ZERO,0000000000,PRIMARY_AT_CAP"
        write_batch(self.tmp / "b", [ROW, other], [ROW], TOTAL, TOTAL.replace("050000", "050001"))
        result = self.status(self.tmp / "b", self.report)
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("MISSING_IN_PYTHON", [r[8] for r in result["rows"]])
        self.assertFalse(result["totals_match"])

    def test_missing_outputs_are_not_run(self):
        self.assertEqual(self.status(self.tmp / "absent", self.report)["status"], "NOT_RUN")

    def test_missing_or_malformed_verifier_is_not_a_pass(self):
        write_batch(self.tmp / "b", [ROW], [ROW], TOTAL, TOTAL)
        self.assertEqual(self.status(self.tmp / "b", self.tmp / "none.json")["status"], "UNKNOWN")
        bad = self.tmp / "bad.json"
        bad.write_text("{not json")
        self.assertEqual(self.status(self.tmp / "b", bad)["status"], "UNKNOWN")

    def test_failing_verifier_fails_even_if_table_matches(self):
        write_batch(self.tmp / "b", [ROW], [ROW], TOTAL, TOTAL)
        self.report.write_text(json.dumps({"result": "FAIL"}))
        self.assertEqual(self.status(self.tmp / "b", self.report)["status"], "FAILED")

    def test_missing_column_is_unknown_not_a_crash(self):
        folder = self.tmp / "b"
        write_batch(folder, [ROW], [ROW], TOTAL, TOTAL)
        (folder / "python-results.csv").write_text("claim_id,status\nCMS-EX3,PAID\n")
        self.assertEqual(self.status(folder, self.report)["status"], "UNKNOWN")

    def test_both_programs_dropping_the_same_record_fails(self):
        folder = self.tmp / "b"
        write_batch(folder, [ROW], [ROW], TOTAL, TOTAL)
        (self.tmp / "in.dat").write_text("one\ntwo\n")
        (folder / "summary.json").write_text(json.dumps({"input": str(self.tmp / "in.dat")}))
        self.assertEqual(evidence.comparison(folder, None, "TEST", "saved")["status"], "FAILED")

    def test_no_verifier_and_no_input_is_unknown(self):
        write_batch(self.tmp / "b", [ROW], [ROW], TOTAL, TOTAL)
        self.assertEqual(evidence.comparison(self.tmp / "b", None, "TEST", "saved")["status"], "UNKNOWN")


class TestLogStatus(unittest.TestCase):
    def check(self, text, expected):
        path = Path(tempfile.mkdtemp()) / "log.txt"
        if text is not None:
            path.write_text(text)
        self.assertEqual(evidence.unittest_summary(path)["status"], expected)

    def test_states(self):
        self.check(None, "NOT_RUN")
        self.check("test_a (m.T) ... ok\n\nRan 1 test in 0.1s\n\nOK\n", "PASSED")
        self.check("test_a (m.T) ... FAIL\n\nRan 1 test in 0.1s\n\nFAILED (failures=1)\n", "FAILED")
        self.check("truncated output", "UNKNOWN")
        self.check("\nRan 0 tests in 0.000s\n\nOK\n", "UNKNOWN")


class SavedRehearsal(unittest.TestCase):
    def test_saved_evidence_is_read_and_cms_ex3_is_500(self):
        data = evidence.build()
        curated = data["saved"]["comparisons"]["curated"]
        self.assertEqual(curated["status"], "PASSED")
        row = next(r for r in curated["rows"] if r[1] == "CMS-EX3")
        self.assertEqual((row[4], row[5], row[8]), (50000, 50000, "MATCH"))


if __name__ == "__main__":
    unittest.main()
