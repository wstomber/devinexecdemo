"""Devin's independently derived policy and interface tests (written before Python).

Runs the implementation named by MSP_COMMAND (default: build/msp-batch) against the
hand-derived ledger in expectations.json plus batch-level interface scenarios.
    python3 -m unittest discover -s tests_policy -v
    MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
"""
import csv
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from fixtures import case_record, serialize  # noqa: E402  (serializer only, no payment logic)

LEDGER = json.loads((Path(__file__).with_name("expectations.json")).read_text())
COMMAND = shlex.split(os.environ.get("MSP_COMMAND", str(ROOT / "build/msp-batch")))
VALID = {"charges": 100000, "gross": 100000, "primary": 10000, "deductible": 0,
         "coinsurance": 0, "contract": None, "full": "N"}


def claim(claim_id, **overrides):
    return serialize({"id": claim_id, **VALID, **overrides})


class Batch:
    def __init__(self, directory, content):
        self.input = Path(directory) / "input.dat"
        self.results = Path(directory) / "results.csv"
        self.totals = Path(directory) / "totals.csv"
        self.input.write_bytes(content if isinstance(content, bytes) else content.encode("ascii"))

    def run(self, *args):
        argv = list(args) or [str(self.input), str(self.results), str(self.totals)]
        return subprocess.run(COMMAND + argv, capture_output=True, timeout=60, check=False, cwd=ROOT)

    def rows(self):
        with self.results.open(newline="") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == ["record_no", "claim_id", "status", "payment_cents", "reason"]
            return [{"record_no": int(r["record_no"]), "claim_id": r["claim_id"], "status": r["status"],
                     "payment_cents": int(r["payment_cents"]), "reason": r["reason"]} for r in reader]

    def total(self):
        with self.totals.open(newline="") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == ["records", "paid", "zero", "invalid", "payment_cents"]
            (row,) = list(reader)
            return {k: int(v) for k, v in row.items()}


class PolicyLedgerTests(unittest.TestCase):
    """Layer A: hand-derived expectations, one subtest per stable claim ID."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        content = "".join(case_record(c) + "\n" for c in LEDGER["cases"])
        cls.batch = Batch(cls.temp.name, content)
        cls.completed = cls.batch.run()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_batch_succeeds(self):
        self.assertEqual(self.completed.returncode, 0, self.completed.stderr.decode())

    def test_every_case_matches_hand_derived_expectation(self):
        rows = {r["record_no"]: r for r in self.batch.rows()}
        self.assertEqual(sorted(rows), [c["record_no"] for c in LEDGER["cases"]])
        for case in LEDGER["cases"]:
            with self.subTest(case=case["claim_id"]):
                expected = {"record_no": case["record_no"], "claim_id": case["claim_id"], **case["expected"]}
                self.assertEqual(rows[case["record_no"]], expected, case.get("arithmetic"))

    def test_cms_ex3_pays_500_dollars_not_1500(self):
        rows = {r["claim_id"]: r for r in self.batch.rows()}
        self.assertEqual(rows["CMS-EX3"]["payment_cents"], 50000)
        self.assertEqual(rows["EX3-NO-OTAF"]["payment_cents"], 150000)
        self.assertEqual(rows["EX3-NO-OTAF"]["payment_cents"] - rows["CMS-EX3"]["payment_cents"], 100000)

    def test_totals_match_ledger_and_rows(self):
        expected = {k: v for k, v in LEDGER["totals"].items() if k != "arithmetic"}
        self.assertEqual(self.batch.total(), expected)
        rows = self.batch.rows()
        self.assertEqual(sum(r["payment_cents"] for r in rows), expected["payment_cents"])


class LedgerArithmeticAudit(unittest.TestCase):
    """Checks Devin's hand arithmetic for typos. Runs no executable; not evidence about COBOL or Python."""

    def test_stated_limits_follow_from_inputs_and_expected_payment_is_lowest(self):
        for case in LEDGER["cases"]:
            if "limits_cents" not in case:
                continue
            with self.subTest(case=case["claim_id"]):
                c = case["input"]
                basis = c["charges"] if c["contract"] is None else c["contract"]
                deductions = c["deductible"] + c["coinsurance"]
                self.assertEqual(case["limits_cents"], [c["gross"] - c["primary"], c["gross"] - deductions,
                                                        basis - c["primary"], basis - deductions])
                lowest = 0 if c["full"] == "Y" else max(0, min(case["limits_cents"]))
                self.assertEqual(case["expected"]["payment_cents"], lowest)

    def test_ledger_totals_follow_from_rows(self):
        statuses = [c["expected"]["status"] for c in LEDGER["cases"]]
        totals = LEDGER["totals"]
        self.assertEqual(totals["records"], len(statuses))
        for status in ("PAID", "ZERO", "INVALID"):
            self.assertEqual(totals[status.lower()], statuses.count(status))
        self.assertEqual(totals["payment_cents"], sum(c["expected"]["payment_cents"] for c in LEDGER["cases"]))


class BatchInterfaceTests(unittest.TestCase):
    """Layer A (interface): framing, identity, state, limits and fatal behavior from README.md."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def batch(self, content):
        return Batch(self.temp.name, content)

    def test_empty_input_is_zero_record_batch(self):
        b = self.batch("")
        self.assertEqual(b.run().returncode, 0)
        self.assertEqual(b.rows(), [])
        self.assertEqual(b.total(), {"records": 0, "paid": 0, "zero": 0, "invalid": 0, "payment_cents": 0})

    def test_crlf_and_missing_final_newline_match_lf(self):
        records = [claim("A1"), claim("A2", primary=0)]
        lf = self.batch("\n".join(records) + "\n")
        lf.run()
        expected = lf.rows()
        for content in ("\r\n".join(records) + "\r\n", "\n".join(records)):
            b = self.batch(content)
            self.assertEqual(b.run().returncode, 0)
            self.assertEqual(b.rows(), expected)
        self.assertEqual([r["payment_cents"] for r in expected], [90000, 100000])

    def test_duplicate_valid_id_is_fatal(self):
        completed = self.batch(claim("DUP") + "\n" + claim("DUP") + "\n").run()
        self.assertEqual(completed.returncode, 2)

    def test_duplicate_identifiable_rejected_id_is_fatal(self):
        bad_flag = claim("DUP")[:72] + "X"
        completed = self.batch(claim("DUP") + "\n" + bad_flag + "\n").run()
        self.assertEqual(completed.returncode, 2)

    def test_unidentifiable_rejections_never_collide(self):
        b = self.batch("SHORT\nSHORT\n" + " " * 73 + "\n")
        self.assertEqual(b.run().returncode, 0)
        self.assertEqual([r["claim_id"] for r in b.rows()], ["@0000000001", "@0000000002", "@0000000003"])
        self.assertEqual({r["reason"] for r in b.rows()}, {"BAD_LENGTH", "BAD_ID"})

    def test_state_resets_after_rejected_contract_and_payment_in_full(self):
        records = [claim("R1", contract=0)[:72] + "Q", claim("R2"),
                   claim("R3", full="Y"), claim("R4"),
                   claim("R5", contract=100001), claim("R6")]
        b = self.batch("\n".join(records) + "\n")
        self.assertEqual(b.run().returncode, 0)
        self.assertEqual([(r["status"], r["payment_cents"]) for r in b.rows()],
                         [("INVALID", 0), ("PAID", 90000), ("ZERO", 0), ("PAID", 90000),
                          ("INVALID", 0), ("PAID", 90000)])

    def test_line_of_4096_bytes_is_invalid_record_and_4097_is_fatal(self):
        b = self.batch("X" * 4096 + "\n" + claim("AFTER") + "\n")
        self.assertEqual(b.run().returncode, 0)
        self.assertEqual([r["reason"] for r in b.rows()], ["BAD_LENGTH", "SECONDARY_PAYABLE"])
        self.assertEqual(self.batch("X" * 4097 + "\n").run().returncode, 2)

    def test_10000_records_succeed_and_10001_is_fatal(self):
        records = [claim(f"N{i:05d}") for i in range(10000)]
        b = self.batch("\n".join(records) + "\n")
        self.assertEqual(b.run().returncode, 0)
        self.assertEqual(b.total(), {"records": 10000, "paid": 10000, "zero": 0, "invalid": 0,
                                     "payment_cents": 900000000})
        self.assertEqual(self.batch("\n".join(records + [claim("EXTRA")]) + "\n").run().returncode, 2)

    def test_usage_errors_exit_2(self):
        b = self.batch(claim("U1") + "\n")
        self.assertEqual(b.run(str(b.input), str(b.results)).returncode, 2)
        self.assertEqual(b.run(str(b.input), str(b.results), str(b.results)).returncode, 2)
        self.assertEqual(b.run(str(b.input), str(b.input), str(b.totals)).returncode, 2)

    def test_missing_input_exits_2(self):
        b = self.batch("")
        missing = str(Path(self.temp.name) / "absent.dat")
        self.assertEqual(b.run(missing, str(b.results), str(b.totals)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
