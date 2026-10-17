"""Independent policy/interface ledger tests. Select the program with MSP_COMMAND."""
import unittest

from msp_runner import LEDGER, batch_bytes, build_record, run_batch

CASES = LEDGER["policy_cases"] + LEDGER["interface_cases"]


def limits_from_input(claim):
    """Hand arithmetic check of the ledger's own limit list (labels [G-T, G-P, B-P, B-T])."""
    c, g, p = claim["charges"], claim["gross"], claim["primary"]
    t = claim["deductible"] + claim["coinsurance"]
    b = claim["contract"] if claim["contract"] is not None else c
    return [g - t, g - p, b - p, b - t]


def expected_claim_id(spec, record_no):
    wanted = spec["expected"].get("claim_id")
    if wanted == "@":
        return f"@{record_no:010d}"
    return wanted if wanted else spec["input"]["id"]


class LedgerIntegrity(unittest.TestCase):
    def test_every_case_is_sourced_and_unique(self):
        names = [c["case"] for c in CASES] + [s["case"] for s in LEDGER["sequences"]]
        self.assertEqual(len(names), len(set(names)))
        for case in CASES:
            self.assertTrue(case["source"], case["case"])
            self.assertTrue(case["arithmetic"], case["case"])
            for ref in case["source"]:
                self.assertIn(ref, LEDGER["sources"], case["case"])
            build_record(case)

    def test_policy_and_interface_cases_are_separated(self):
        for case in LEDGER["policy_cases"]:
            self.assertTrue(any(s.startswith("S40") for s in case["source"]), case["case"])
        for case in LEDGER["interface_cases"]:
            self.assertTrue(set(case["source"]) & {"README", "RULES-DEMO"}, case["case"])

    def test_hand_arithmetic_is_internally_consistent(self):
        """Re-add the hand-written limit lists; catches ledger typos, not program behavior."""
        specs = CASES + [r for s in LEDGER["sequences"] for r in s["records"]]
        for spec in specs:
            if spec.get("limits") is None:
                continue
            claim, exp = spec["input"], spec["expected"]
            self.assertEqual(spec["limits"], limits_from_input(claim), spec)
            self.assertEqual(exp["payment_cents"], max(0, min(spec["limits"])), spec)
            self.assertEqual(exp["status"] == "PAID", exp["payment_cents"] > 0, spec)

    def test_cms_ex3_is_500_dollars(self):
        ex3 = next(c for c in CASES if c["case"] == "CMS-EX3")
        self.assertEqual(ex3["expected"]["payment_cents"], 50000)
        no_otaf = next(c for c in CASES if c["case"] == "EX3-NO-OTAF")
        self.assertEqual(no_otaf["expected"]["payment_cents"], 150000)


class LedgerAgainstProgram(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch = run_batch(batch_bytes(CASES))

    def test_exit_zero(self):
        self.assertEqual(self.batch.returncode, 0, self.batch.stderr)

    def test_each_case(self):
        rows = self.batch.rows()
        self.assertEqual(len(rows), len(CASES))
        for number, (case, row) in enumerate(zip(CASES, rows), 1):
            with self.subTest(case=case["case"]):
                exp = case["expected"]
                self.assertEqual(row["record_no"], number)
                self.assertEqual(row["claim_id"], expected_claim_id(case, number))
                self.assertEqual((row["status"], row["reason"], row["payment_cents"]),
                                 (exp["status"], exp["reason"], exp["payment_cents"]))

    def test_totals_reconcile_with_ledger(self):
        expected = {"records": len(CASES), "paid": 0, "zero": 0, "invalid": 0,
                    "payment_cents": sum(c["expected"]["payment_cents"] for c in CASES)}
        for case in CASES:
            expected[case["expected"]["status"].lower()] += 1
        self.assertEqual(self.batch.totals(), expected)

    def test_each_case_alone(self):
        """Same answer when a record is the only one in its batch (no neighbour effects)."""
        for case in CASES:
            with self.subTest(case=case["case"]):
                run = run_batch(batch_bytes([case]))
                self.assertEqual(run.returncode, 0, run.stderr)
                (row,) = run.rows()
                exp = case["expected"]
                self.assertEqual(row["claim_id"], expected_claim_id(case, 1))
                self.assertEqual((row["status"], row["reason"], row["payment_cents"]),
                                 (exp["status"], exp["reason"], exp["payment_cents"]))


class StateResetSequences(unittest.TestCase):
    def test_sequences(self):
        for sequence in LEDGER["sequences"]:
            with self.subTest(case=sequence["case"]):
                run = run_batch(batch_bytes(sequence["records"]))
                self.assertEqual(run.returncode, 0, run.stderr)
                rows = run.rows()
                self.assertEqual(len(rows), len(sequence["records"]))
                for number, (spec, row) in enumerate(zip(sequence["records"], rows), 1):
                    exp = spec["expected"]
                    self.assertEqual(row["record_no"], number)
                    self.assertEqual(row["claim_id"], exp.get("claim_id") or spec["input"]["id"])
                    self.assertEqual((row["status"], row["reason"], row["payment_cents"]),
                                     (exp["status"], exp["reason"], exp["payment_cents"]))


if __name__ == "__main__":
    unittest.main()
