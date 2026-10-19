import unittest

from msp_harness import (
    RESULTS_HEADER,
    TOTALS_HEADER,
    build_case_record,
    claim_record,
    cwf_file,
    expected_row,
    load_ledger,
    run,
)


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = load_ledger()
        cls.defaults = cls.ledger.get("defaults", {})
        cls.cases = cls.ledger["cases"]
        cls.records = [build_case_record(case, cls.defaults) for case in cls.cases]
        cls.cwf_bytes = cwf_file(cls.ledger["cwf_reference"])

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def assert_case_row(self, actual, expected):
        self.assertEqual(int(actual["record_no"]), expected["record_no"])
        self.assertEqual(actual["claim_id"], expected["claim_id"])
        self.assertEqual(actual["status"], expected["status"])
        self.assertEqual(int(actual["payment_cents"]), expected["payment_cents"])
        self.assertEqual(actual["reason"], expected["reason"])
        self.assertEqual(actual["cwf"], expected["cwf"])
        self.assertEqual(actual["cwf_reason"], expected["cwf_reason"])
        self.assertEqual(int(actual["released_cents"]), expected["released_cents"])

    def assert_headers(self, result):
        self.assertIsNotNone(result.raw_results)
        self.assertIsNotNone(result.raw_totals)
        self.assertEqual(result.raw_results.splitlines()[0], RESULTS_HEADER)
        self.assertEqual(result.raw_totals.splitlines()[0], TOTALS_HEADER)

    def test_ledger_batch(self):
        result = run(
            ("\n".join(self.records) + "\n").encode("ascii"),
            self.cwf_bytes,
        )
        self.assert_success(result)
        self.assert_headers(result)
        self.assertIsNotNone(result.results)
        self.assertEqual(len(result.results), len(self.cases))
        for index, (case, actual) in enumerate(zip(self.cases, result.results), 1):
            with self.subTest(case=case["id"]):
                self.assert_case_row(actual, expected_row(case, index))

        expected_rows = [
            expected_row(case, index)
            for index, case in enumerate(self.cases, 1)
        ]
        expected_totals = {
            "records": len(expected_rows),
            "paid": sum(row["status"] == "PAID" for row in expected_rows),
            "zero": sum(row["status"] == "ZERO" for row in expected_rows),
            "invalid": sum(row["status"] == "INVALID" for row in expected_rows),
            "payment_cents": sum(row["payment_cents"] for row in expected_rows),
            "accepted": sum(row["cwf"] == "ACCEPTED" for row in expected_rows),
            "rejected": sum(row["cwf"] == "REJECTED" for row in expected_rows),
            "released_cents": sum(
                row["released_cents"] for row in expected_rows
            ),
        }
        self.assertIsNotNone(result.totals)
        for field, value in expected_totals.items():
            with self.subTest(total=field):
                self.assertEqual(int(result.totals[field]), value)

    def test_each_case_alone(self):
        for case, record in zip(self.cases, self.records):
            with self.subTest(case=case["id"]):
                result = run((record + "\n").encode("ascii"), self.cwf_bytes)
                self.assert_success(result)
                self.assert_headers(result)
                self.assertIsNotNone(result.results)
                self.assertEqual(len(result.results), 1)
                self.assert_case_row(result.results[0], expected_row(case, 1))

    def test_ledger_integrity(self):
        case_ids = [case["id"] for case in self.cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        valid_statuses = {"PAID", "ZERO", "INVALID"}
        invalid_reasons = {
            "BAD_LENGTH",
            "BAD_ID",
            "BAD_AMOUNT",
            "BAD_CONTRACT",
            "BAD_FLAG",
            "BAD_MBI",
            "BAD_DATE",
        }
        zero_reasons = {
            "PAYMENT_IN_FULL",
            "PRIMARY_AT_CAP",
            "DEDUCTIONS_AT_CAP",
        }
        rejected_reasons = {
            "NOT_ENTITLED",
            "DUPLICATE",
            "MSP_PRIMARY_NOT_BILLED",
        }

        for case, record in zip(self.cases, self.records):
            with self.subTest(case=case["id"]):
                self.assertTrue(case["source"].strip())
                self.assertTrue(case["arithmetic"].strip())
                self.assertIn(case["category"], {"policy", "interface"})
                record.encode("ascii")
                if "input" in case and case["expected"]["reason"] != "BAD_LENGTH":
                    self.assertEqual(len(record), 92)

                expected = case["expected"]
                status = expected["status"]
                payment = expected["payment_cents"]
                released = expected["released_cents"]
                self.assertIn(status, valid_statuses)
                self.assertGreaterEqual(payment, 0)
                self.assertEqual(status == "PAID", payment > 0)
                if expected["cwf"] == "ACCEPTED":
                    self.assertEqual(released, payment)
                else:
                    self.assertEqual(released, 0)

                if status == "INVALID":
                    self.assertIn(expected["reason"], invalid_reasons)
                    self.assertEqual(expected["cwf"], "NOT_SENT")
                    self.assertEqual(expected["cwf_reason"], "CLAIM_INVALID")
                else:
                    self.assertIn(expected["cwf"], {"ACCEPTED", "REJECTED"})
                    if status == "ZERO":
                        self.assertIn(expected["reason"], zero_reasons)
                    else:
                        self.assertEqual(expected["reason"], "SECONDARY_PAYABLE")
                    if expected["cwf"] == "ACCEPTED":
                        self.assertEqual(expected["cwf_reason"], "DISPOSITION_01")
                    else:
                        self.assertIn(expected["cwf_reason"], rejected_reasons)

    def test_output_widths(self):
        record = claim_record(
            "T0000000001",
            charges=10000,
            gross=10000,
            primary=2000,
            deductible=1000,
            coinsurance=500,
            contract=None,
            full="N",
            mbi="P1MEDPRIM01",
            dos="20250610",
        )
        result = run(
            (record + "\n").encode("ascii"),
            cwf_file(
                {
                    "beneficiaries": [
                        {
                            "mbi": "P1MEDPRIM01",
                            "entitled_from": "20200101",
                            "entitled_to": "99999999",
                        }
                    ],
                    "history": [],
                }
            ),
        )
        self.assert_success(result)
        self.assertIsNotNone(result.raw_results)
        self.assertIsNotNone(result.raw_totals)
        result_lines = result.raw_results.splitlines()
        totals_lines = result.raw_totals.splitlines()
        self.assertEqual(result_lines[0], RESULTS_HEADER)
        self.assertEqual(totals_lines[0], TOTALS_HEADER)
        result_fields = result_lines[1].split(",")
        self.assertEqual(len(result_fields[0]), 10)
        self.assertEqual(len(result_fields[3]), 10)
        self.assertEqual(len(result_fields[7]), 10)
        totals_fields = totals_lines[1].split(",")
        for index in (0, 1, 2, 3, 5, 6):
            self.assertEqual(len(totals_fields[index]), 10)
        for index in (4, 7):
            self.assertEqual(len(totals_fields[index]), 15)


if __name__ == "__main__":
    unittest.main()
