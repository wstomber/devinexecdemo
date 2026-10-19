"""Run the hand-derived ledger (expectations.json) as one batch through MSP_COMMAND."""
import unittest

from common import ledger_cwf, load_ledger, record, run


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = load_ledger()
        cls.cases = cls.ledger["cases"]
        lines = [record(c, cls.ledger["defaults"]) for c in cls.cases]
        batch = "".join(line + "\n" for line in lines).encode("ascii")
        cls.exit, cls.rows, cls.totals, cls.stdout, _ = run(batch, ledger_cwf())

    def test_batch_succeeds_silently(self):
        self.assertEqual(self.exit, 0)
        self.assertEqual(self.stdout, b"")
        self.assertEqual(len(self.rows), len(self.cases))

    def test_every_case(self):
        sources = self.ledger["sources"]
        for number, (case, row) in enumerate(zip(self.cases, self.rows), 1):
            with self.subTest(case=case["id"]):
                self.assertTrue(case["source"] and case["arithmetic"] and case["kind"] in ("policy", "interface"))
                self.assertTrue(any(key in case["source"] for key in sources), case["source"])
                status, payment, reason, cwf, cwf_reason, released = case["expect"]
                claim_id = f"@{number:010d}" if case.get("provisional_id") else case["id"]
                self.assertEqual(row["record_no"], number)
                self.assertEqual((row["claim_id"], row["status"], row["payment_cents"], row["reason"],
                                  row["cwf"], row["cwf_reason"], row["released_cents"]),
                                 (claim_id, status, payment, reason, cwf, cwf_reason, released))

    def test_totals_reconcile_with_ledger(self):
        expected = {"records": len(self.cases), "paid": 0, "zero": 0, "invalid": 0, "payment_cents": 0,
                    "accepted": 0, "rejected": 0, "released_cents": 0}
        for case in self.cases:
            status, payment, _, cwf, _, released = case["expect"]
            expected[status.lower()] += 1
            if cwf != "NOT_SENT":
                expected[cwf.lower()] += 1
            expected["payment_cents"] += payment
            expected["released_cents"] += released
        self.assertEqual(self.totals, expected)

    def test_cms_ex3_headline(self):
        row = next(r for r in self.rows if r["claim_id"] == "CMS-EX3")
        self.assertEqual((row["payment_cents"], row["cwf"], row["released_cents"]), (50000, "ACCEPTED", 50000))
        counterfactual = next(r for r in self.rows if r["claim_id"] == "EX3-NO-OTAF")
        self.assertEqual(counterfactual["payment_cents"] - row["payment_cents"], 100000)


if __name__ == "__main__":
    unittest.main()
