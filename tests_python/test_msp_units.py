"""Focused unit tests for python/msp.py functions and boundaries (Stage 3)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import msp  # noqa: E402


def line(claim_id="UNIT", c=10000, g=10000, p=0, d=0, k=0, a=None, full="N", mbi="7ACTIVE0001", dos="20240615"):
    contract = "-" * 10 if a is None else f"{a:010d}"
    return (claim_id.ljust(12) + "".join(f"{v:010d}" for v in (c, g, p, d, k)) + contract
            + full + mbi + dos).encode("ascii")


def validated(raw):
    claim = msp.Claim(7)
    msp.validate(claim, raw)
    return claim


def paid(**kw):
    claim = validated(line(**kw))
    assert claim.status == "VALID", claim.reason
    msp.calculate_payment(claim)
    return claim.status, claim.payment, claim.reason


class DigitTests(unittest.TestCase):
    def test_only_ascii_digits_are_numeric(self):
        self.assertTrue(msp.is_digits(b"0123456789"))
        for bad in (b"", b"+000000001", b" 000000001", b"0000_00001", b"00000000.1",
                    "٠١٢٣٤٥٦٧٨٩".encode(), b"\t000000001", b"\x00000000001"):
            with self.subTest(bad=bad):
                self.assertFalse(msp.is_digits(bad))

    def test_to_int_is_exact(self):
        self.assertEqual(msp.to_int(b"9999999999"), 9_999_999_999)
        self.assertEqual(msp.to_int(b"0000000001"), 1)
        self.assertIsInstance(msp.to_int(b"0000000001"), int)


class ValidationTests(unittest.TestCase):
    def test_valid_record_parses_exact_fields(self):
        claim = validated(line("CMS-EX3", 1500000, 1400000, 1250000, 155600, 0, 1300000, mbi="7EX3BENE001", dos="20250315"))
        self.assertEqual((claim.status, claim.claim_id, claim.charges, claim.contract, claim.dos),
                         ("VALID", "CMS-EX3", 1500000, 1300000, 20250315))

    def test_length(self):
        for raw in (b"", line()[:-1], line() + b"X", b" " * 4096):
            self.assertEqual((validated(raw).reason, validated(raw).claim_id), ("BAD_LENGTH", "@0000000007"))

    def test_ids(self):
        for good in ("A", "ABCDEFGHIJKL", "A-B_9"):
            self.assertEqual(validated(line(good)).status, "VALID", good)
        for bad in (" " * 12, " LEAD", "EMB SP", "lower", "AT@", "É"):
            raw = bad.encode("utf-8").ljust(12)[:12] + line()[12:]
            claim = validated(raw)
            self.assertEqual((claim.reason, claim.claim_id), ("BAD_ID", "@0000000007"), bad)

    def test_precedence_chain(self):
        base = bytearray(line(a=999, c=100, g=100))
        base[72:73] = b"?"
        base[73:84] = b"bad mbi    "
        base[84:92] = b"XXXXXXXX"
        self.assertEqual(validated(bytes(base)).reason, "BAD_CONTRACT")
        base[12:22] = b"         1"
        self.assertEqual(validated(bytes(base)).reason, "BAD_AMOUNT")
        ok_contract = bytearray(line(a=50, c=100, g=100))
        ok_contract[72:73], ok_contract[73:84], ok_contract[84:92] = b"?", b"bad mbi    ", b"XXXXXXXX"
        self.assertEqual(validated(bytes(ok_contract)).reason, "BAD_FLAG")
        ok_contract[72:73] = b"N"
        self.assertEqual(validated(bytes(ok_contract)).reason, "BAD_MBI")
        ok_contract[73:84] = b"7ACTIVE0001"
        self.assertEqual(validated(bytes(ok_contract)).reason, "BAD_DATE")

    def test_malformed_contract_is_bad_amount(self):
        for contract in (b"---------0", b"          ", b"+000000001"):
            raw = line()[:62] + contract + line()[72:]
            self.assertEqual(validated(raw).reason, "BAD_AMOUNT")

    def test_contract_range(self):
        self.assertEqual(validated(line(c=100, a=100)).status, "VALID")
        self.assertEqual(validated(line(c=100, a=101)).reason, "BAD_CONTRACT")
        self.assertEqual(validated(line(c=100, a=0)).contract, 0)

    def test_dates(self):
        for good in ("20240101", "20241231", "20250230", "00000101"):
            self.assertEqual(validated(line(dos=good)).status, "VALID", good)
        for bad in ("20240001", "20241301", "20240100", "20240132", "2024-1-1"):
            self.assertEqual(validated(line(dos=bad)).reason, "BAD_DATE", bad)

    def test_fresh_claim_has_no_leftover_contract(self):
        first = validated(line("ONE", a=5, full="?"))
        self.assertEqual((first.reason, first.contract), ("BAD_FLAG", 5))
        self.assertIsNone(validated(line("TWO")).contract)


class PaymentTests(unittest.TestCase):
    def test_cms_ex3_and_counterfactual(self):
        ex3 = dict(c=1500000, g=1400000, p=1250000, d=155600, k=0)
        self.assertEqual(paid(a=1300000, **ex3), ("PAID", 50000, "SECONDARY_PAYABLE"))
        self.assertEqual(paid(**ex3), ("PAID", 150000, "SECONDARY_PAYABLE"))

    def test_cms_ex1(self):
        self.assertEqual(paid(c=2500000, g=2200000, p=2050000, d=155600), ("PAID", 150000, "SECONDARY_PAYABLE"))

    def test_each_limit_controls(self):
        self.assertEqual(paid(c=100000, g=50000, p=20000, d=5000)[1], 30000)            # G-P
        self.assertEqual(paid(c=100000, g=50000, p=5000, d=15000, k=5000)[1], 30000)    # G-T
        self.assertEqual(paid(c=100000, g=90000, p=30000, d=1000, a=40000)[1], 10000)  # B-P
        self.assertEqual(paid(c=100000, g=90000, p=1000, d=20000, k=5000, a=40000)[1], 15000)  # B-T

    def test_one_cent_boundaries(self):
        self.assertEqual(paid(c=100000, g=70000, p=69999), ("PAID", 1, "SECONDARY_PAYABLE"))
        self.assertEqual(paid(c=100000, g=70000, p=70000), ("ZERO", 0, "PRIMARY_AT_CAP"))
        self.assertEqual(paid(c=100000, g=70000, d=50000, k=19999), ("PAID", 1, "SECONDARY_PAYABLE"))
        self.assertEqual(paid(c=100000, g=70000, d=50000, k=20000), ("ZERO", 0, "DEDUCTIONS_AT_CAP"))

    def test_zero_reason_precedence(self):
        self.assertEqual(paid(c=0, g=0, full="Y"), ("ZERO", 0, "PAYMENT_IN_FULL"))
        self.assertEqual(paid(c=1000, g=1000, p=1000, d=1000), ("ZERO", 0, "PRIMARY_AT_CAP"))
        self.assertEqual(paid(c=0, g=0), ("ZERO", 0, "PRIMARY_AT_CAP"))
        self.assertEqual(paid(c=100, g=100, a=0), ("ZERO", 0, "PRIMARY_AT_CAP"))

    def test_maxima(self):
        m = 9_999_999_999
        self.assertEqual(paid(c=m, g=m)[1], m)
        self.assertEqual(paid(c=m, g=m, d=m, k=m), ("ZERO", 0, "DEDUCTIONS_AT_CAP"))
        self.assertEqual(paid(c=m, g=m, p=1, a=m)[1], m - 1)


class CwfTests(unittest.TestCase):
    def reference(self, *records):
        ref = msp.CwfReference()
        for text in records:
            ref.add(text.encode().ljust(64))
        return ref

    def check(self, ref, **kw):
        claim = validated(line(**kw))
        msp.calculate_payment(claim)
        msp.cwf_check(claim, ref)
        return claim.cwf, claim.cwf_reason, claim.payment, claim.released

    def test_order_and_boundaries(self):
        ref = self.reference("B7WINDOW00012023010120241231" + "-" * 16,
                             "B7MSPWIN00012020010199999999" + "2024030120240831",
                             "H7MSPWIN0001202403010000000100")
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7WINDOW0001", dos="20221231")[:2], ("REJECTED", "NOT_ENTITLED"))
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7WINDOW0001", dos="20230101")[0], "ACCEPTED")
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7WINDOW0001", dos="20241231")[0], "ACCEPTED")
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7NOTFILE001")[:2], ("REJECTED", "NOT_ENTITLED"))
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7MSPWIN0001", dos="20240301")[1], "DUPLICATE")
        self.assertEqual(self.check(ref, c=101, g=100, mbi="7MSPWIN0001", dos="20240301")[1], "MSP_PRIMARY_NOT_BILLED")
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7MSPWIN0001", dos="20240831")[1], "MSP_PRIMARY_NOT_BILLED")
        self.assertEqual(self.check(ref, c=100, g=100, mbi="7MSPWIN0001", dos="20240901")[0], "ACCEPTED")
        self.assertEqual(self.check(ref, c=100, g=100, p=1, mbi="7MSPWIN0001", dos="20240601"),
                         ("ACCEPTED", "DISPOSITION_01", 99, 99))

    def test_rejection_keeps_calculated_payment(self):
        ref = self.reference()
        self.assertEqual(self.check(ref, c=1500000, g=1400000, p=1250000, d=155600, a=1300000),
                         ("REJECTED", "NOT_ENTITLED", 50000, 0))

    def test_first_beneficiary_wins(self):
        ref = self.reference("B7ACTIVE00012026010199999999" + "-" * 16, "B7ACTIVE00012020010199999999" + "-" * 16)
        self.assertEqual(self.check(ref)[1], "NOT_ENTITLED")

    def test_malformed_records_and_limits(self):
        good = "B7ACTIVE00012020010199999999" + "-" * 16
        for bad in ("X" + good[1:], good + "Z", good[:28] + "-" * 8 + "20241231", "B" + " " * 11 + good[12:],
                    "H7ACTIVE000120240101000000000X", "H7ACTIVE0001202401010000000001 Z", ""):
            with self.subTest(bad=bad), self.assertRaises(msp.Fatal):
                self.reference(bad)
        ref = msp.CwfReference()
        for n in range(1000):
            ref.add(f"B9{n:010d}2020010199999999{'-' * 16}".encode().ljust(64))
        with self.assertRaises(msp.Fatal):
            ref.add(good.encode().ljust(64))

    def test_line_reader_matches_gnucobol(self):
        lines = list(msp.cwf_lines([b"AB\r\nC\rD\n", b"\n", b"x" * 70 + b"\n", b"\r"]))
        self.assertEqual([l.rstrip(b" ") for l in lines], [b"AB", b"CD", b"", b"x" * 64])
        self.assertEqual(list(msp.cwf_lines([b"tail"])), [b"tail".ljust(64)])
        self.assertTrue(all(len(l) == 64 for l in lines))


class FramingTests(unittest.TestCase):
    def frame(self, *chunks):
        return list(msp.input_lines(chunks))

    def test_lines(self):
        self.assertEqual(self.frame(b"a\nb\r\nc"), [b"a", b"b", b"c"])
        self.assertEqual(self.frame(b"\n\r\n"), [b"", b""])
        self.assertEqual(self.frame(b"a\r\r\n"), [b"a\r"])
        self.assertEqual(self.frame(b"a\n\r"), [b"a", b""])
        self.assertEqual(self.frame(b""), [])
        self.assertEqual(self.frame(b"ab", b"c\n", b"d"), [b"abc", b"d"])

    def test_transport_bound(self):
        self.assertEqual(len(self.frame(b"x" * 4096 + b"\r\n")[0]), 4096)
        self.assertEqual(len(self.frame(b"x" * 4096 + b"\r")[0]), 4096)
        for data in (b"x" * 4097 + b"\n", b"x" * 4097, b"x" * 4097 + b"\r\n", b"x" * 9000):
            with self.assertRaises(msp.Fatal):
                self.frame(data[:5000], data[5000:])


class BatchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.d = Path(temp.name)
        (self.d / "cwf.dat").write_text("B7ACTIVE00012021060199999999" + "-" * 16 + "\n")

    def batch(self, data):
        (self.d / "in.dat").write_bytes(data)
        code = msp.run([str(self.d / n) for n in ("in.dat", "cwf.dat", "o.csv", "t.csv")])
        return code, (self.d / "o.csv").read_text() if code == 0 else None, \
            (self.d / "t.csv").read_text() if code == 0 else None

    def test_exact_csv_format(self):
        code, results, totals = self.batch(line("CMS-EX3", 1500000, 1400000, 1250000, 155600, 0, 1300000) + b"\nX\n")
        self.assertEqual(code, 0)
        self.assertEqual(results.splitlines(), [
            msp.RESULT_HEADER,
            "0000000001,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000",
            "0000000002,@0000000002,INVALID,0000000000,BAD_LENGTH,NOT_SENT,CLAIM_INVALID,0000000000"])
        self.assertEqual(totals, msp.TOTAL_HEADER + "\n0000000002,0000000001,0000000000,0000000001,"
                                                    "000000000050000,0000000001,0000000000,000000000050000\n")

    def test_maximum_totals_width(self):
        data = b"".join(line(f"M{n}", c=9_999_999_999, g=9_999_999_999) + b"\n" for n in range(10000))
        code, _, totals = self.batch(data)
        self.assertEqual(code, 0)
        self.assertIn(",099999999990000,", totals)

    def test_fatal_paths(self):
        self.assertEqual(self.batch(line("A") + b"\n" + line("A") + b"\n")[0], 2)
        self.assertEqual(self.batch(b"X\n" * 10001)[0], 2)
        self.assertEqual(msp.run(["a", "b", "c"]), 2)
        self.assertEqual(msp.run(["a", "b", "o", "o "]), 2)

    def test_path_name_matches_cobol_field(self):
        self.assertEqual(msp.path_name("o.csv  "), b"o.csv")
        self.assertEqual(msp.path_name("x" * 2000), b"x" * 1024)

    def test_cli_exit_codes_and_silence(self):
        (self.d / "in.dat").write_bytes(line() + b"\n")
        cmd = [sys.executable, str(ROOT / "python/msp.py")]
        ok = subprocess.run(cmd + [str(self.d / n) for n in ("in.dat", "cwf.dat", "o.csv", "t.csv")], capture_output=True)
        self.assertEqual((ok.returncode, ok.stdout), (0, b""))
        bad = subprocess.run(cmd + ["only-one"], capture_output=True)
        self.assertEqual(bad.returncode, 2)
        self.assertIn(b"usage", bad.stderr)

    def test_no_float_in_source(self):
        source = (ROOT / "python/msp.py").read_text()
        self.assertNotIn("float", source.replace("no float anywhere", ""))
        self.assertNotIn("isdigit", source.replace("not str.isdigit", ""))


if __name__ == "__main__":
    unittest.main()
