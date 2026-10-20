"""Batch/transport interface tests derived from README.md (demo interface, not CMS policy)."""
import unittest
from pathlib import Path

from msp_runner import run_batch

CWF = ["B7POLICY00012024010199999999----------------"]


def record(claim_id, charges=100000, gross=80000, primary=20000, deductible=10000, coinsurance=0,
           contract=None, full="N", mbi="7POLICY0001", dos="20250601"):
    text = claim_id.ljust(12) + "".join(f"{v:010d}" for v in (charges, gross, primary, deductible, coinsurance))
    text += "----------" if contract is None else f"{contract:010d}"
    return (text + full + mbi + dos).encode("ascii")


GOOD = [record("B1"), record("B2", primary=0), record("B3", full="Y")]
# Hand-derived (README formula): B1 60,000 PAID; B2 70,000 PAID; B3 0 PAYMENT_IN_FULL.
GOOD_SUMMARY = [("B1", "PAID", 60000, "SECONDARY_PAYABLE"), ("B2", "PAID", 70000, "SECONDARY_PAYABLE"),
                ("B3", "ZERO", 0, "PAYMENT_IN_FULL")]


def summary(run):
    return [(r["claim_id"], r["status"], int(r["payment_cents"]), r["reason"]) for r in run.rows()]


class FramingTests(unittest.TestCase):
    def assertOk(self, run):
        self.assertEqual(run.returncode, 0, run.stderr.decode(errors="replace"))

    def assertFatal(self, run):
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, b"", "diagnostics go to stderr only")

    def test_lf_crlf_and_missing_final_newline_agree(self):
        lf = run_batch(b"\n".join(GOOD) + b"\n", CWF)
        crlf = run_batch(b"\r\n".join(GOOD) + b"\r\n", CWF)
        no_final = run_batch(b"\n".join(GOOD), CWF)
        crlf_no_final = run_batch(b"\r\n".join(GOOD), CWF)
        for run in (lf, crlf, no_final, crlf_no_final):
            self.assertOk(run)
            self.assertEqual(summary(run), GOOD_SUMMARY)
            self.assertEqual(run.totals(), {"records": 3, "paid": 2, "zero": 1, "invalid": 0,
                                            "payment_cents": 130000, "accepted": 3, "rejected": 0,
                                            "released_cents": 130000})

    def test_empty_input_is_zero_record_batch(self):
        run = run_batch(b"", CWF)
        self.assertOk(run)
        self.assertEqual(run.rows(), [])
        self.assertEqual(run.totals(), dict.fromkeys(["records", "paid", "zero", "invalid", "payment_cents",
                                                      "accepted", "rejected", "released_cents"], 0))

    def test_blank_lines_are_records_not_eof(self):
        run = run_batch(GOOD[0] + b"\n\n\r\n" + GOOD[1] + b"\n", CWF)
        self.assertOk(run)
        self.assertEqual([(r["claim_id"], r["reason"]) for r in run.rows()],
                         [("B1", "SECONDARY_PAYABLE"), ("@0000000002", "BAD_LENGTH"),
                          ("@0000000003", "BAD_LENGTH"), ("B2", "SECONDARY_PAYABLE")])

    def test_only_one_cr_is_removed(self):
        run = run_batch(GOOD[0] + b"\r\r\n", CWF)
        self.assertOk(run)
        self.assertEqual(run.rows()[0]["reason"], "BAD_LENGTH")

    def test_4096_byte_line_is_one_invalid_record(self):
        for ending in (b"\n", b"\r\n"):
            with self.subTest(ending=ending):
                run = run_batch(GOOD[0] + b"\n" + b"X" * 4096 + ending + GOOD[1] + b"\n", CWF)
                self.assertOk(run)
                self.assertEqual([r["reason"] for r in run.rows()], ["SECONDARY_PAYABLE", "BAD_LENGTH", "SECONDARY_PAYABLE"])

    def test_4096_byte_last_line_without_newline(self):
        run = run_batch(GOOD[0] + b"\n" + b"X" * 4096, CWF)
        self.assertOk(run)
        self.assertEqual(len(run.rows()), 2)

    def test_4097_byte_line_is_fatal(self):
        for ending in (b"\n", b"\r\n", b""):
            with self.subTest(ending=ending):
                self.assertFatal(run_batch(GOOD[0] + b"\n" + b"X" * 4097 + ending, CWF))

    def test_10000_records_with_maximum_total(self):
        max_pay = 9_999_999_999
        lines = [record(f"M{i:05d}", max_pay, max_pay, 0, 0, 0) for i in range(10000)]
        run = run_batch(b"\n".join(lines) + b"\n", CWF, timeout=120)
        self.assertOk(run)
        # README: maximum sum 99,999,999,990,000 cents fits the 15-digit total.
        self.assertEqual(run.totals(), {"records": 10000, "paid": 10000, "zero": 0, "invalid": 0,
                                        "payment_cents": 99_999_999_990_000, "accepted": 10000, "rejected": 0,
                                        "released_cents": 99_999_999_990_000})

    def test_10001_records_is_fatal_even_if_last_is_invalid(self):
        lines = [record(f"N{i:05d}") for i in range(10000)]
        self.assertFatal(run_batch(b"\n".join(lines + [record("N10000")]) + b"\n", CWF, timeout=120))
        self.assertFatal(run_batch(b"\n".join(lines) + b"\n\n", CWF, timeout=120))


class DuplicateIdTests(unittest.TestCase):
    def test_duplicate_valid_ids_are_fatal(self):
        self.assertEqual(run_batch(record("DUP") + b"\n" + record("DUP", charges=1) + b"\n", CWF).returncode, 2)

    def test_duplicate_with_rejected_identifiable_record_is_fatal(self):
        bad_amount = bytearray(record("DUP")); bad_amount[12:22] = b"ABCDEFGHIJ"
        bad_flag = bytearray(record("DUP")); bad_flag[72:73] = b"X"
        self.assertEqual(run_batch(record("DUP") + b"\n" + bytes(bad_amount) + b"\n", CWF).returncode, 2)
        self.assertEqual(run_batch(bytes(bad_flag) + b"\n" + record("DUP") + b"\n", CWF).returncode, 2)

    def test_provisional_ids_never_collide(self):
        run = run_batch(b"DUP\nDUP\n" + record("dup") + b"\n" + record("dup") + b"\n", CWF)
        self.assertEqual(run.returncode, 0)
        self.assertEqual([r["claim_id"] for r in run.rows()],
                         ["@0000000001", "@0000000002", "@0000000003", "@0000000004"])
        self.assertEqual([r["reason"] for r in run.rows()], ["BAD_LENGTH", "BAD_LENGTH", "BAD_ID", "BAD_ID"])


class CwfFileTests(unittest.TestCase):
    def test_missing_cwf_file_is_fatal(self):
        self.assertEqual(run_batch(GOOD[0] + b"\n", None).returncode, 2)

    def test_empty_cwf_file_means_nobody_entitled(self):
        run = run_batch(GOOD[0] + b"\n", [])
        self.assertEqual(run.returncode, 0)
        r = run.rows()[0]
        self.assertEqual((r["status"], int(r["payment_cents"]), r["cwf"], r["cwf_reason"], int(r["released_cents"])),
                         ("PAID", 60000, "REJECTED", "NOT_ENTITLED", 0))

    def test_malformed_cwf_records_are_fatal(self):
        bad = {
            "unknown type": "X7POLICY00012024010199999999----------------",
            "blank line": "",
            "B entitlement not numeric": "B7POLICY0001202401019999999X----------------",
            "B half MSP period": "B7POLICY000120240101999999992025010--------",
            "B MSP not numeric": "B7POLICY00012024010199999999--------20251231",
            "B blank MBI": "B           2024010199999999----------------",
            "B extra byte": "B7POLICY00012024010199999999----------------X",
            "H charges not numeric": "H7POLICY000120250601000010000X",
            "H date not numeric": "H7POLICY00012025060X0000100000",
            "H extra byte": "H7POLICY0001202506010000100000X",
            "H blank MBI": "H           202506010000100000",
        }
        for name, line in bad.items():
            with self.subTest(name):
                self.assertEqual(run_batch(GOOD[0] + b"\n", CWF + [line]).returncode, 2)

    def test_reference_record_limits(self):
        b = [f"B{i:011d}2024010199999999----------------" for i in range(1000)]
        h = [f"H{i:011d}202506010000000001" for i in range(1000)]
        self.assertEqual(run_batch(GOOD[0] + b"\n", b + h).returncode, 0)
        self.assertEqual(run_batch(GOOD[0] + b"\n", b + ["B99999999999" + "2024010199999999----------------"]).returncode, 2)
        self.assertEqual(run_batch(GOOD[0] + b"\n", h + ["H99999999999202506010000000001"]).returncode, 2)


class UsageTests(unittest.TestCase):
    def test_wrong_argument_counts(self):
        for count in (0, 3, 5):
            with self.subTest(count=count):
                run = run_batch(GOOD[0] + b"\n", CWF, extra_args=lambda d: [str(d / f"a{i}") for i in range(count)])
                self.assertEqual(run.returncode, 2)
                self.assertEqual(run.stdout, b"")

    def test_identical_paths(self):
        pairs = [(0, 2), (0, 3), (2, 3), (1, 0), (1, 2), (1, 3)]
        for a, b in pairs:
            with self.subTest(pair=(a, b)):
                def args(d, a=a, b=b):
                    paths = [str(d / "in.dat"), str(d / "cwf.dat"), str(d / "results.csv"), str(d / "totals.csv")]
                    paths[b] = paths[a]
                    return paths
                self.assertEqual(run_batch(GOOD[0] + b"\n", CWF, extra_args=args).returncode, 2)

    def test_missing_input_and_unwritable_output(self):
        self.assertEqual(run_batch(None, CWF).returncode, 2)
        run = run_batch(GOOD[0] + b"\n", CWF, extra_args=lambda d: [str(d / "in.dat"), str(d / "cwf.dat"),
                                                                     str(d / "no" / "r.csv"), str(d / "t.csv")])
        self.assertEqual(run.returncode, 2)


if __name__ == "__main__":
    unittest.main()
