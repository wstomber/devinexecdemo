"""Stage 2 independent tests: hand-derived ledger cases, run against MSP_COMMAND."""
import unittest

from support import LEDGER, case_line, run

RESULT_HEADER = ["record_no", "claim_id", "status", "payment_cents", "reason"]
TOTALS_HEADER = ["records", "paid", "zero", "invalid", "payment_cents"]
CASES = LEDGER["policy_cases"] + LEDGER["interface_cases"]


def expected_id(case, record_no):
    if case.get("provisional_id"):
        return "@%010d" % record_no
    return case.get("raw", {}).get("id", case["id"]).rstrip(" ")


class LedgerSelfConsistency(unittest.TestCase):
    """Checks the hand arithmetic is internally consistent (no program executed)."""

    def test_every_case_is_sourced_and_explained(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["source"])
                self.assertTrue(set(case["source"]) <= set(LEDGER["sources"]))
                self.assertTrue(case["arithmetic"])

    def test_recorded_limits_produce_expected_payment(self):
        for case in LEDGER["policy_cases"]:
            if case["limits"] is None:
                continue
            with self.subTest(case=case["id"]):
                c, g, p, d, k, a, _ = case["in"]
                b = c if a is None else a
                t = d + k
                self.assertEqual(case["limits"], [g - p, g - t, b - p, b - t])
                self.assertEqual(case["expect"][1], max(0, min(case["limits"])))


class PolicyLedgerAgainstProgram(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = b"".join(case_line(case) + b"\n" for case in CASES)
        cls.code, cls.rows, cls.totals, cls.stderr = run(data)

    def test_batch_succeeds(self):
        self.assertEqual(self.code, 0, self.stderr)
        self.assertEqual(self.rows[0], RESULT_HEADER)
        self.assertEqual(len(self.rows), len(CASES) + 1)

    def test_each_case(self):
        self.assertEqual(self.code, 0, self.stderr)
        for record_no, (case, row) in enumerate(zip(CASES, self.rows[1:]), start=1):
            with self.subTest(case=case["id"]):
                status, payment, reason = case["expect"]
                self.assertEqual(int(row[0]), record_no)
                self.assertEqual(row[1], expected_id(case, record_no))
                self.assertEqual(row[2], status)
                self.assertEqual(int(row[3]), payment)
                self.assertEqual(row[4], reason)

    def test_cms_ex3_is_500_dollars(self):
        index = [c["id"] for c in CASES].index("CMS-EX3")
        self.assertEqual(int(self.rows[index + 1][3]), 50000)

    def test_totals_reconcile_with_ledger(self):
        self.assertEqual(self.totals[0], TOTALS_HEADER)
        statuses = [c["expect"][0] for c in CASES]
        expected = [len(CASES), statuses.count("PAID"), statuses.count("ZERO"),
                    statuses.count("INVALID"), sum(c["expect"][1] for c in CASES)]
        self.assertEqual([int(v) for v in self.totals[1]], expected)


if __name__ == "__main__":
    unittest.main()
