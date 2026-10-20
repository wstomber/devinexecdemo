"""Policy ledger tests (Stage 2). Expectations come only from expectations.json."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import LEDGER, RESULT_HEADER, TOTALS_HEADER, claim_line, parse, run_batch

CASES = LEDGER["cases"]


def expected_totals():
    t = {"records": len(CASES), "paid": 0, "zero": 0, "invalid": 0, "payment_cents": 0,
         "accepted": 0, "rejected": 0, "released_cents": 0}
    for c in CASES:
        _, status, pay, _, cwf, _, released = c["expect"]
        t[status.lower()] += 1
        t["payment_cents"] += pay
        t["released_cents"] += released
        if cwf != "NOT_SENT":
            t[cwf.lower()] += 1
    return t


class PolicyLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = "".join(claim_line(c) + "\n" for c in CASES).encode("ascii")
        cls.run_result = run_batch(data)

    def test_ledger_is_well_formed(self):
        self.assertEqual([c["record_no"] for c in CASES], list(range(1, len(CASES) + 1)))
        for c in CASES:
            self.assertIn(c["kind"], ("policy", "interface"), c["id"])
            self.assertTrue(c["source"] and all(s in LEDGER["sources"] for s in c["source"]), c["id"])
            self.assertTrue(c["arithmetic"], c["id"])
        self.assertEqual(len({c["id"] for c in CASES}), len(CASES))

    def test_exit_code_zero_and_no_stdout(self):
        self.assertEqual(self.run_result.returncode, 0, self.run_result.stderr)
        self.assertEqual(self.run_result.stdout, b"")

    def test_every_record_matches_ledger(self):
        header, rows, _, _ = parse(self.run_result)
        self.assertEqual(header, RESULT_HEADER)
        self.assertEqual(len(rows), len(CASES))
        for case, row in zip(CASES, rows):
            with self.subTest(case=case["id"]):
                self.assertEqual(len(row), 8)
                self.assertEqual(row[0], f"{case['record_no']:010d}")
                claim_id, status, pay, reason, cwf, cwf_reason, released = case["expect"]
                self.assertEqual(row[1:], [claim_id, status, f"{pay:010d}", reason, cwf, cwf_reason,
                                           f"{released:010d}"])

    def test_totals_reconcile_with_ledger(self):
        _, _, header, row = parse(self.run_result)
        self.assertEqual(header, TOTALS_HEADER)
        t = expected_totals()
        widths = {"payment_cents": 15, "released_cents": 15}
        self.assertEqual(row, [f"{t[k]:0{widths.get(k, 10)}d}" for k in TOTALS_HEADER.split(",")])

    def test_cms_ex3_headline(self):
        _, rows, _, _ = parse(self.run_result)
        ex3 = next(r for r in rows if r[1] == "CMS-EX3")
        self.assertEqual((ex3[2], int(ex3[3]), ex3[5], int(ex3[7])), ("PAID", 50000, "ACCEPTED", 50000))
        no_otaf = next(r for r in rows if r[1] == "EX3-NO-OTAF")
        self.assertEqual(int(no_otaf[3]) - int(ex3[3]), 100000)


if __name__ == "__main__":
    unittest.main()
