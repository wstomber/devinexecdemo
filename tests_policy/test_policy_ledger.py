"""Independent policy/interface ledger (tests_policy/expectations.json) run as one batch."""
import unittest

from msp_runner import case_bytes, load_ledger, run_batch


class PolicyLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = load_ledger()
        defaults = {"mbi": "7POLICY0001", "dos": "20250601"}
        cls.cases = cls.ledger["cases"]
        batch = b"".join(case_bytes(c, defaults) + b"\n" for c in cls.cases)
        cls.batch_run = run_batch(batch, cls.ledger["cwf_reference"]["lines"])

    def test_batch_succeeds(self):
        self.assertEqual(self.batch_run.returncode, 0, self.batch_run.stderr.decode(errors="replace"))
        self.assertEqual(self.batch_run.stdout, b"", "CSV must go only to files")

    def test_every_case(self):
        rows = self.batch_run.rows()
        self.assertEqual(len(rows), len(self.cases))
        for number, (case, row) in enumerate(zip(self.cases, rows), 1):
            expect = dict(case["expect"])
            if expect["claim_id"] == "PROVISIONAL":
                expect["claim_id"] = f"@{number:010d}"
            with self.subTest(case=case["id"], record=number):
                self.assertEqual(int(row["record_no"]), number)
                actual = {k: (int(v) if k.endswith("_cents") else v) for k, v in row.items() if k != "record_no"}
                self.assertEqual(actual, expect)

    def test_totals_reconcile_with_ledger(self):
        expected = {"records": len(self.cases), "paid": 0, "zero": 0, "invalid": 0,
                    "payment_cents": 0, "accepted": 0, "rejected": 0, "released_cents": 0}
        for case in self.cases:
            e = case["expect"]
            expected[e["status"].lower()] += 1
            if e["cwf"] != "NOT_SENT":
                expected[e["cwf"].lower()] += 1
            expected["payment_cents"] += e["payment_cents"]
            expected["released_cents"] += e["released_cents"]
        self.assertEqual(self.batch_run.totals(), expected)

    def test_cms_example_3_is_500_dollars_released(self):
        number = next(i for i, c in enumerate(self.cases, 1) if c["id"] == "CMS-EX3")
        row = self.batch_run.rows()[number - 1]
        self.assertEqual((row["claim_id"], row["status"], int(row["payment_cents"]), row["cwf"], int(row["released_cents"])),
                         ("CMS-EX3", "PAID", 50000, "ACCEPTED", 50000))

    def test_ledger_is_self_consistent(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["source"] and case["arithmetic"])
                self.assertIn(case["kind"], ("policy", "interface"))
                e = case["expect"]
                self.assertEqual(e["released_cents"], e["payment_cents"] if e["cwf"] == "ACCEPTED" else 0)
                self.assertEqual(e["status"] == "PAID", e["payment_cents"] > 0)


if __name__ == "__main__":
    unittest.main()
