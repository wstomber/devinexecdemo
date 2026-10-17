"""Focused unit tests for python/msp.py functions and boundaries.

Expected payments are hand-worked (same notation as tests_policy/expectations.json).
CSV byte-format assertions characterize the observed COBOL format recorded in
evidence/live/baseline/ (Stage 1), labelled as such.
"""
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import msp  # noqa: E402

MAX = 9_999_999_999


def claim(charges=100000, gross=80000, primary=10000, deductible=0, coinsurance=0,
          contract=None, full=False, claim_id="T"):
    return msp.Claim(claim_id, charges, gross, primary, deductible, coinsurance, contract, full)


def record(claim_id="T", charges="0000100000", gross="0000080000", primary="0000010000",
           deductible="0000000000", coinsurance="0000000000", contract="----------", full="N"):
    return (claim_id.ljust(12) + charges + gross + primary + deductible + coinsurance
            + contract + full).encode("latin-1")


class IsNumeric(unittest.TestCase):
    def test_ascii_digits_only(self):
        self.assertTrue(msp.is_numeric(b"0000000000"))
        self.assertTrue(msp.is_numeric(b"9999999999"))
        for bad in (b" 000000001", b"+000000001", b"-000000001", b"00000_0001", b"0000000.01",
                    b"         ", b"\xb2000000000", "\u0661".encode() + b"00000000", b""):
            with self.subTest(bad=bad):
                self.assertFalse(msp.is_numeric(bad))

    def test_python_pitfalls_this_avoids(self):
        # These are why int()/str.isdigit() must not be used for validation.
        self.assertEqual(int("00000_0001"), 1)
        self.assertEqual(int(" +00000001"), 1)
        self.assertTrue("\u0661".isdigit())


class ValidId(unittest.TestCase):
    def test_valid(self):
        for raw in (b"CMS-EX3     ", b"ABCDEFGHIJ12", b"_           ", b"A-1_Z       "):
            self.assertTrue(msp.valid_id(raw), raw)

    def test_invalid(self):
        for raw in (b" " * 12, b" ABC        ", b"AB CD       ", b"cms-ex3     ", b"A.B         ",
                    b"@X          ", b"A\x00B        ", b"\xc1BC        "):
            self.assertFalse(msp.valid_id(raw), raw)


class ValidationPrecedence(unittest.TestCase):
    def reason(self, data):
        return msp.validate_record(data)[2]

    def test_each_reason_and_order(self):
        self.assertIsNone(self.reason(record()))
        self.assertEqual(self.reason(record()[:72]), "BAD_LENGTH")
        self.assertEqual(self.reason(b""), "BAD_LENGTH")
        self.assertEqual(self.reason(record("bad", charges="XXXXXXXXXX")[:72]), "BAD_LENGTH")
        self.assertEqual(self.reason(record("bad", charges="XXXXXXXXXX", full="Q")), "BAD_ID")
        self.assertEqual(self.reason(record(gross="ABCDEFGHIJ", contract="0000200000", full="Q")), "BAD_AMOUNT")
        self.assertEqual(self.reason(record(contract="---------0")), "BAD_AMOUNT")
        self.assertEqual(self.reason(record(contract="          ")), "BAD_AMOUNT")
        self.assertEqual(self.reason(record(contract="0000100001", full="Q")), "BAD_CONTRACT")
        self.assertEqual(self.reason(record(full="y")), "BAD_FLAG")
        self.assertEqual(self.reason(record(charges="0000100.00", full="Y")), "BAD_AMOUNT")

    def test_identity(self):
        self.assertIsNone(msp.validate_record(b"")[0])
        self.assertIsNone(msp.validate_record(record("bad"))[0])
        self.assertEqual(msp.validate_record(record("ID-9", full="X"))[0], "ID-9")

    def test_contract_equal_and_zero_are_valid(self):
        self.assertEqual(msp.validate_record(record(contract="0000100000"))[1].contract, 100000)
        self.assertEqual(msp.validate_record(record(contract="0000000000"))[1].contract, 0)
        self.assertIsNone(msp.validate_record(record())[1].contract)


class CalculatePayment(unittest.TestCase):
    def test_cms_ex3_contract_branch(self):
        ex3 = claim(1500000, 1400000, 1250000, 155600, 0, contract=1300000, claim_id="CMS-EX3")
        self.assertEqual(msp.calculate_payment(ex3), ("PAID", "SECONDARY_PAYABLE", 50000))
        no_otaf = claim(1500000, 1400000, 1250000, 155600, 0)
        self.assertEqual(msp.calculate_payment(no_otaf), ("PAID", "SECONDARY_PAYABLE", 150000))
        accepted_in_full = claim(1500000, 1400000, 1250000, 155600, 0, contract=1300000, full=True)
        self.assertEqual(msp.calculate_payment(accepted_in_full), ("ZERO", "PAYMENT_IN_FULL", 0))

    def test_cms_ex1(self):
        self.assertEqual(msp.calculate_payment(claim(2500000, 2200000, 2050000, 155600)),
                         ("PAID", "SECONDARY_PAYABLE", 150000))

    def test_each_limit_controls(self):
        cases = {  # (C, G, P, D, K, A) -> cents
            (100000, 80000, 1000, 20000, 5000, None): 55000,   # G-T
            (100000, 80000, 30000, 10000, 0, None): 50000,     # G-P
            (60000, 80000, 10000, 5000, 0, None): 50000,       # C-P
            (60000, 80000, 2000, 7000, 3000, None): 50000,     # C-T
            (100000, 80000, 10000, 5000, 0, 60000): 50000,     # A-P
            (90000, 80000, 2000, 7000, 3000, 60000): 50000,    # A-T
        }
        for (c, g, p, d, k, a), cents in cases.items():
            with self.subTest(inputs=(c, g, p, d, k, a)):
                self.assertEqual(msp.calculate_payment(claim(c, g, p, d, k, a))[2], cents)

    def test_equal_limits(self):
        self.assertEqual(msp.calculate_payment(claim(80000, 80000, 15000, 15000))[2], 65000)
        self.assertEqual(msp.calculate_payment(claim(100000, 80000, 15000, 10000, 5000))[2], 65000)

    def test_one_cent_boundaries(self):
        self.assertEqual(msp.calculate_payment(claim(primary=79999)), ("PAID", "SECONDARY_PAYABLE", 1))
        self.assertEqual(msp.calculate_payment(claim(primary=80000)), ("ZERO", "PRIMARY_AT_CAP", 0))
        self.assertEqual(msp.calculate_payment(claim(primary=80001)), ("ZERO", "PRIMARY_AT_CAP", 0))
        self.assertEqual(msp.calculate_payment(claim(primary=0, deductible=70000, coinsurance=9999))[2], 1)
        self.assertEqual(msp.calculate_payment(claim(primary=0, deductible=40000, coinsurance=40000)),
                         ("ZERO", "DEDUCTIONS_AT_CAP", 0))
        self.assertEqual(msp.calculate_payment(claim(primary=15000, deductible=15001))[2], 64999)
        self.assertEqual(msp.calculate_payment(claim(100000, 120000, 10000, contract=99999))[2], 89999)

    def test_zero_reason_precedence(self):
        self.assertEqual(msp.calculate_payment(claim(0, 0, 0, 0, 0)), ("ZERO", "PRIMARY_AT_CAP", 0))
        self.assertEqual(msp.calculate_payment(claim(primary=90000, deductible=90000, full=True))[1], "PAYMENT_IN_FULL")
        self.assertEqual(msp.calculate_payment(claim(primary=80000, deductible=90000))[1], "PRIMARY_AT_CAP")
        self.assertEqual(msp.calculate_payment(claim(primary=0, contract=0))[1], "PRIMARY_AT_CAP")

    def test_maximums_are_exact_integers(self):
        self.assertEqual(msp.calculate_payment(claim(MAX, MAX, 0)), ("PAID", "SECONDARY_PAYABLE", MAX))
        self.assertEqual(msp.calculate_payment(claim(MAX, MAX, 1))[2], MAX - 1)
        self.assertEqual(msp.calculate_payment(claim(MAX, MAX, 0, MAX, MAX))[1], "DEDUCTIONS_AT_CAP")
        self.assertIsInstance(msp.calculate_payment(claim(MAX, MAX, 1))[2], int)


class Framing(unittest.TestCase):
    def records(self, data, chunk=65536):
        return list(msp.iter_records(io.BytesIO(data), chunk))

    def test_lf_crlf_eof(self):
        self.assertEqual(self.records(b"a\nb\r\nc"), [b"a", b"b", b"c"])
        self.assertEqual(self.records(b""), [])
        self.assertEqual(self.records(b"\n"), [b""])
        self.assertEqual(self.records(b"a\r\r\n"), [b"a\r"])
        self.assertEqual(self.records(b"a\n\r"), [b"a", b""])

    def test_line_limit_across_chunk_boundaries(self):
        for chunk in (1, 7, 4096, 65536):
            with self.subTest(chunk=chunk):
                self.assertEqual(len(self.records(b"x" * 4096 + b"\r\n", chunk)[0]), 4096)
                with self.assertRaises(msp.FatalBatchError):
                    self.records(b"x" * 4097 + b"\n", chunk)
                with self.assertRaises(msp.FatalBatchError):
                    self.records(b"x" * 4097, chunk)


class BatchState(unittest.TestCase):
    def run_batch(self, data):
        out = io.StringIO()
        totals = msp.run_batch(io.BytesIO(data), out)
        return out.getvalue().splitlines(), totals

    def test_state_reset_after_rejected_contract(self):
        data = record("R1", contract="0000020000", full="X") + b"\n" + record("R2") + b"\n"
        rows, totals = self.run_batch(data)
        self.assertEqual(rows[1:], ["0000000001,R1,INVALID,0000000000,BAD_FLAG",
                                    "0000000002,R2,PAID,0000070000,SECONDARY_PAYABLE"])
        self.assertEqual(totals, {"records": 2, "paid": 1, "zero": 0, "invalid": 1, "payment_cents": 70000})

    def test_duplicates(self):
        with self.assertRaises(msp.FatalBatchError):
            self.run_batch(record("D", full="X") + b"\n" + record("D") + b"\n")
        rows, _ = self.run_batch(b"\n\n")
        self.assertEqual(rows[1:], ["0000000001,@0000000001,INVALID,0000000000,BAD_LENGTH",
                                    "0000000002,@0000000002,INVALID,0000000000,BAD_LENGTH"])

    def test_record_limit(self):
        data = b"".join(record(f"N{i}") + b"\n" for i in range(10000))
        self.assertEqual(self.run_batch(data)[1]["records"], 10000)
        with self.assertRaises(msp.FatalBatchError):
            self.run_batch(data + b"\n")


class Formatting(unittest.TestCase):
    """Characterizes the observed COBOL CSV format (evidence/live/baseline/curated-*.csv)."""

    def test_result_row(self):
        row = msp.format_result(2, msp.Outcome("CMS-EX3", "PAID", "SECONDARY_PAYABLE", 50000))
        self.assertEqual(row, "0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE")
        self.assertIn(row, (ROOT / "evidence/live/baseline/curated-results.csv").read_text().splitlines())

    def test_totals_row(self):
        self.assertEqual(msp.format_totals({"records": 30, "paid": 12, "zero": 9, "invalid": 9,
                                            "payment_cents": 10000450202}),
                         "0000000030,0000000012,0000000009,0000000009,000010000450202")
        self.assertEqual(msp.format_totals({"records": 10000, "paid": 10000, "zero": 0, "invalid": 0,
                                            "payment_cents": 99_999_999_990_000})[-15:], "099999999990000")


class Cli(unittest.TestCase):
    def test_usage_and_distinct_paths(self):
        self.assertEqual(msp.main([]), 2)
        self.assertEqual(msp.main(["a", "b"]), 2)
        self.assertEqual(msp.main(["a", "a", "b"]), 2)

    def test_end_to_end_and_fatal_exit(self):
        with tempfile.TemporaryDirectory() as d:
            src, out, tot = (str(Path(d) / n) for n in ("in.dat", "o.csv", "t.csv"))
            Path(src).write_bytes(record("A") + b"\r\n")
            self.assertEqual(msp.main([src, out, tot]), 0)
            self.assertEqual(Path(tot).read_text(), "records,paid,zero,invalid,payment_cents\n"
                             "0000000001,0000000001,0000000000,0000000000,000000000070000\n")
            Path(src).write_bytes(record("A") + b"\n" + record("A") + b"\n")
            self.assertEqual(msp.main([src, out, tot]), 2)
            self.assertEqual(msp.main([str(Path(d) / "missing"), out, tot]), 2)


if __name__ == "__main__":
    unittest.main()
