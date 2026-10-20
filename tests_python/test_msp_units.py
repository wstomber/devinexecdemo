"""Focused unit tests for python/msp.py (function level)."""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
import msp  # noqa: E402


def raw(claim_id="U1", c=100000, g=80000, p=20000, d=10000, k=0, a=None, full="N",
        mbi="7UNITTEST01", dos="20250601"):
    text = claim_id.ljust(12) + "".join(f"{v:010d}" for v in (c, g, p, d, k))
    text += "----------" if a is None else f"{a:010d}"
    return (text + full + mbi + dos).encode("ascii")


def patched(offset, value, **kw):
    b = bytearray(raw(**kw)); b[offset:offset + len(value)] = value
    return bytes(b)


def validated(line, record_no=1):
    claim = msp.Claim(record_no)
    msp.validate(claim, line)
    return claim


def priced(**kw):
    claim = validated(raw(**kw))
    msp.calculate_payment(claim)
    return claim


class NumericTests(unittest.TestCase):
    def test_only_ascii_digits_are_numeric(self):
        self.assertTrue(msp.is_numeric(b"0123456789"))
        for value in (b"+000000001", b" 000000001", b"00000_0001", "000000000\u0661".encode(), b"", b"-000000001"):
            with self.subTest(value=value):
                self.assertFalse(msp.is_numeric(value))

    def test_python_int_would_accept_these(self):
        # Why int()/isdigit() are not used for validation.
        self.assertEqual(int(b" +1_0 "), 10)
        self.assertTrue("\u0661".isdigit())


class ValidationTests(unittest.TestCase):
    def test_reason_precedence(self):
        cases = [
            (raw()[:91], "BAD_LENGTH"),
            (b"", "BAD_LENGTH"),
            (patched(0, b"A B"), "BAD_ID"),
            (patched(0, b" AB"), "BAD_ID"),
            (patched(0, b"ab"), "BAD_ID"),
            (patched(12, b"+000000001"), "BAD_AMOUNT"),
            (patched(62, b"00000ABCDE"), "BAD_AMOUNT"),   # malformed contract is BAD_AMOUNT
            (raw(a=100001), "BAD_CONTRACT"),
            (patched(72, b"y"), "BAD_FLAG"),
            (patched(73, b"7unittest01"), "BAD_MBI"),
            (raw(dos="20251301"), "BAD_DATE"),
            (raw(dos="20250600"), "BAD_DATE"),
            (raw(dos="20250232"), "BAD_DATE"),
        ]
        for line, reason in cases:
            with self.subTest(reason=reason, line=line):
                claim = validated(line)
                self.assertEqual((claim.status, claim.reason), ("INVALID", reason))

    def test_calendar_is_not_checked(self):
        self.assertEqual(validated(raw(dos="20250231")).status, "VALID")

    def test_provisional_and_real_ids(self):
        self.assertEqual(validated(b"", 7).claim_id, "@0000000007")
        self.assertEqual(validated(patched(0, b"a"), 8).claim_id, "@0000000008")
        self.assertEqual(validated(patched(72, b"X", claim_id="KEEP-ID"), 9).claim_id, "KEEP-ID")
        self.assertEqual(validated(raw(claim_id="ABCDEFGHIJ_-")).claim_id, "ABCDEFGHIJ_-")

    def test_contract_equal_to_charges_is_valid(self):
        claim = validated(raw(a=100000))
        self.assertEqual((claim.status, claim.contract), ("VALID", 100000))


class PaymentTests(unittest.TestCase):
    def test_cms_example_3(self):
        claim = priced(c=1500000, g=1400000, p=1250000, d=155600, k=0, a=1300000)
        self.assertEqual((claim.status, claim.payment, claim.reason), ("PAID", 50000, "SECONDARY_PAYABLE"))
        self.assertEqual(priced(c=1500000, g=1400000, p=1250000, d=155600, k=0).payment, 150000)

    def test_zero_reason_precedence(self):
        self.assertEqual(priced(p=0, full="Y").reason, "PAYMENT_IN_FULL")
        self.assertEqual(priced(p=80000, d=90000).reason, "PRIMARY_AT_CAP")
        self.assertEqual(priced(p=79999, d=80000).reason, "DEDUCTIONS_AT_CAP")
        self.assertEqual(priced(p=79999, d=79998).payment, 1)

    def test_maximum_amounts_are_exact_integers(self):
        m = 9_999_999_999
        claim = priced(c=m, g=m, p=0, d=0, k=0)
        self.assertEqual(claim.payment, m)
        self.assertIsInstance(claim.payment, int)
        self.assertEqual(priced(c=m, g=m, p=1, d=m, k=m).reason, "DEDUCTIONS_AT_CAP")


class CwfTests(unittest.TestCase):
    BENE = [{"mbi": b"7UNITTEST01", "from": 20250101, "to": 20251231, "msp": (20250301, 20250331)}]

    def checked(self, history=frozenset(), **kw):
        claim = priced(**kw)
        msp.cwf_check(claim, self.BENE, set(history))
        return claim

    def test_outcomes(self):
        self.assertEqual(self.checked(dos="20241231").cwf_reason, "NOT_ENTITLED")
        self.assertEqual(self.checked(mbi="7UNKNOWN001").cwf_reason, "NOT_ENTITLED")
        dup = self.checked(history={(b"7UNITTEST01", 20250601, 100000)})
        self.assertEqual((dup.cwf_reason, dup.payment, dup.released), ("DUPLICATE", 60000, 0))
        self.assertEqual(self.checked(history={(b"7UNITTEST01", 20250601, 100001)}).cwf, "ACCEPTED")
        self.assertEqual(self.checked(p=0, dos="20250301").cwf_reason, "MSP_PRIMARY_NOT_BILLED")
        self.assertEqual(self.checked(p=0, dos="20250401").cwf, "ACCEPTED")
        self.assertEqual(self.checked(p=1, dos="20250331").cwf, "ACCEPTED")

    def test_zero_claim_is_checked_and_releases_zero(self):
        claim = self.checked(full="Y")
        self.assertEqual((claim.status, claim.cwf, claim.released), ("ZERO", "ACCEPTED", 0))


class FramingTests(unittest.TestCase):
    def lines(self, data):
        return list(msp.read_lines(io.BytesIO(data)))

    def test_line_endings(self):
        self.assertEqual(self.lines(b"a\r\nb\nc"), [b"a", b"b", b"c"])
        self.assertEqual(self.lines(b"a\r\r\n"), [b"a\r"])
        self.assertEqual(self.lines(b"\n\r"), [b"", b""])
        self.assertEqual(self.lines(b""), [])

    def test_line_limits(self):
        self.assertEqual(len(self.lines(b"x" * 4096 + b"\r\n")[0]), 4096)
        self.assertEqual(len(self.lines(b"x" * 4096 + b"\r")[0]), 4096)
        for data in (b"x" * 4097 + b"\n", b"x" * 4097, b"x" * 5000 + b"\n", b"x" * 4098):
            with self.subTest(length=len(data)):
                with self.assertRaises(msp.Fatal):
                    self.lines(data)


class CwfFileTests(unittest.TestCase):
    def test_line_sequential_reading(self):
        recs = list(msp.cwf_records(b"B1\r\nH2\r" + b"x" * 70 + b"\nZ"))
        self.assertEqual([r[:2] for r in recs], [b"B1", b"H2", b"Z "])
        self.assertTrue(all(len(r) == 64 for r in recs))
        self.assertEqual(list(msp.cwf_records(b"")), [])

    def test_paths_like_cobol(self):
        self.assertEqual(msp.cobol_path("a  "), "a")
        self.assertEqual(len(msp.cobol_path("p" * 2000)), 1024)


if __name__ == "__main__":
    unittest.main()
