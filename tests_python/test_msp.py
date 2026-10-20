"""Focused unit tests for python/msp.py functions and boundaries (Stage 3)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import msp  # noqa: E402


def record(claim_id=b"U1", charges=100000, gross=100000, primary=60000, deductible=0, coinsurance=0,
           contract=None, full=b"N", mbi=b"U1ENT000001", dos=b"20250315"):
    c = msp.ABSENT_CONTRACT if contract is None else b"%010d" % contract
    line = (claim_id.ljust(12) + b"%010d%010d%010d%010d%010d" % (charges, gross, primary, deductible, coinsurance)
            + c + full + mbi + dos)
    assert len(line) == 92
    return line


def patched(line, start, value):
    return line[:start] + value + line[start + len(value):]


REFERENCE = msp.parse_cwf(b"BU1ENT00000120200101" b"99999999" b"----------------\n"
                          b"BU2MSP00000120200101" b"99999999" b"2025030120250630\n"
                          b"HU1ENT000001202504100001500000\n")


def priced(**kwargs):
    claim = msp.validate_record(record(**kwargs), 1)
    assert claim.status == "VALID", claim.reason
    msp.calculate_payment(claim)
    return claim


class NumericTests(unittest.TestCase):
    def test_is_numeric_uses_explicit_ascii_digits(self):
        self.assertTrue(msp.is_numeric(b"0000000000"))
        for bad in (b"", b"+000000001", b" 000000001", b"0000_00001", "٠١٢".encode(), b"00000000.1", b"\x00" * 10):
            with self.subTest(bad=bad):
                self.assertFalse(msp.is_numeric(bad))

    def test_digits_value_is_exact_integer(self):
        self.assertEqual(msp.digits_value(b"9999999999"), 9_999_999_999)
        self.assertEqual(msp.digits_value(b"0000000001"), 1)
        self.assertIsInstance(msp.digits_value(b"0000155600"), int)


class ValidationTests(unittest.TestCase):
    def reason(self, line):
        return msp.validate_record(line, 7).reason

    def test_valid_record_parses_all_fields(self):
        claim = msp.validate_record(record(contract=90000, deductible=1, coinsurance=2), 1)
        self.assertEqual((claim.status, claim.claim_id, claim.contract, claim.deductible, claim.coinsurance,
                          claim.mbi, claim.dos), ("VALID", "U1", 90000, 1, 2, b"U1ENT000001", 20250315))

    def test_length_and_reserved_identity(self):
        for line in (b"", record()[:91], record() + b" "):
            claim = msp.validate_record(line, 42)
            self.assertEqual((claim.reason, claim.claim_id), ("BAD_LENGTH", "@0000000042"))

    def test_id_rules(self):
        for raw in (b" " * 12, b" X", b"A B", b"a", b"A.B", b"A@", b"A\x00", b"\xc3\x89"):
            with self.subTest(raw=raw):
                self.assertEqual(self.reason(patched(record(), 0, raw.ljust(12))), "BAD_ID")
        self.assertEqual(msp.validate_record(patched(record(), 0, b"AZ09-_AZ09-_"), 1).claim_id, "AZ09-_AZ09-_")

    def test_precedence_chain(self):
        line = record(contract=100001)
        line = patched(line, 72, b"?")
        line = patched(line, 73, b"bad")
        line = patched(line, 84, b"2025XX01")
        self.assertEqual(self.reason(line), "BAD_CONTRACT")
        self.assertEqual(self.reason(patched(line, 22, b"+")), "BAD_AMOUNT")
        self.assertEqual(self.reason(patched(patched(line, 22, b"+"), 0, b" " * 12)), "BAD_ID")
        ok_contract = patched(line, 62, msp.ABSENT_CONTRACT)
        self.assertEqual(self.reason(ok_contract), "BAD_FLAG")
        self.assertEqual(self.reason(patched(ok_contract, 72, b"N")), "BAD_MBI")
        self.assertEqual(self.reason(patched(patched(ok_contract, 72, b"N"), 73, b"U1ENT000001")), "BAD_DATE")

    def test_malformed_contract_is_bad_amount(self):
        for raw in (b"-----00000", b" " * 10, b"---------0"):
            self.assertEqual(self.reason(patched(record(), 62, raw)), "BAD_AMOUNT")

    def test_contract_equal_and_zero_allowed(self):
        self.assertEqual(msp.validate_record(record(contract=100000), 1).status, "VALID")
        self.assertEqual(msp.validate_record(record(contract=0), 1).contract, 0)

    def test_date_bounds(self):
        for dos in (b"20250001", b"20251301", b"20250100", b"20250132", b"2025013 ", b"        "):
            self.assertEqual(self.reason(record(dos=dos)), "BAD_DATE")
        for dos in (b"20250101", b"20251231", b"20250230", b"00000101"):
            self.assertEqual(msp.validate_record(record(dos=dos), 1).status, "VALID")


class PaymentTests(unittest.TestCase):
    def test_cms_ex3_and_counterfactual(self):
        args = dict(charges=1500000, gross=1400000, primary=1250000, deductible=155600)
        ex3 = priced(contract=1300000, **args)
        self.assertEqual((ex3.status, ex3.payment, ex3.reason), ("PAID", 50000, "SECONDARY_PAYABLE"))
        self.assertEqual(priced(**args).payment, 150000)
        self.assertEqual(priced(contract=1300000, full=b"Y", **args).reason, "PAYMENT_IN_FULL")

    def test_each_limit_controls(self):
        self.assertEqual(priced(charges=100000, gross=80000, primary=30000, deductible=10000).payment, 50000)
        self.assertEqual(priced(charges=100000, gross=80000, primary=5000, deductible=15000,
                                coinsurance=5000).payment, 60000)
        self.assertEqual(priced(charges=70000, gross=90000, primary=20000, deductible=10000).payment, 50000)
        self.assertEqual(priced(charges=70000, gross=90000, primary=5000, deductible=20000,
                                coinsurance=10000).payment, 40000)

    def test_one_cent_boundaries_and_zero_reasons(self):
        self.assertEqual(priced(primary=99999).payment, 1)
        self.assertEqual(priced(primary=100000).reason, "PRIMARY_AT_CAP")
        self.assertEqual(priced(primary=0, deductible=99999).payment, 1)
        self.assertEqual(priced(primary=0, deductible=100000).reason, "DEDUCTIONS_AT_CAP")
        self.assertEqual(priced(primary=100000, deductible=100000).reason, "PRIMARY_AT_CAP")
        self.assertEqual(priced(charges=0, gross=0, primary=0).reason, "PRIMARY_AT_CAP")
        self.assertEqual(priced(contract=0, primary=0).reason, "PRIMARY_AT_CAP")

    def test_maximums_have_no_overflow_or_float(self):
        top = 9_999_999_999
        claim = priced(charges=top, gross=top, primary=0)
        self.assertEqual(claim.payment, top)
        self.assertIsInstance(claim.payment, int)
        self.assertEqual(priced(charges=top, gross=top, primary=top - 1, deductible=top, coinsurance=top).reason,
                         "DEDUCTIONS_AT_CAP")


class CwfTests(unittest.TestCase):
    def checked(self, **kwargs):
        claim = priced(**kwargs)
        msp.cwf_check(claim, REFERENCE)
        return claim.cwf, claim.cwf_reason, claim.payment, claim.released

    def test_accepted_releases_payment(self):
        self.assertEqual(self.checked(), ("ACCEPTED", "DISPOSITION_01", 40000, 40000))

    def test_not_entitled_keeps_calculated_payment(self):
        self.assertEqual(self.checked(mbi=b"U9UNKNOWN99"), ("REJECTED", "NOT_ENTITLED", 40000, 0))
        self.assertEqual(self.checked(dos=b"20191231")[1], "NOT_ENTITLED")

    def test_duplicate_matches_history_exactly(self):
        dup = dict(charges=1500000, gross=1400000, primary=1000000, dos=b"20250410")
        self.assertEqual(self.checked(**dup)[1], "DUPLICATE")
        self.assertEqual(self.checked(**dict(dup, charges=1500001))[1], "DISPOSITION_01")
        self.assertEqual(self.checked(**dict(dup, dos=b"20250411"))[1], "DISPOSITION_01")

    def test_msp_primary_not_billed(self):
        msp_bene = dict(mbi=b"U2MSP000001", primary=0, deductible=10000)
        self.assertEqual(self.checked(dos=b"20250301", **msp_bene)[1], "MSP_PRIMARY_NOT_BILLED")
        self.assertEqual(self.checked(dos=b"20250630", **msp_bene)[1], "MSP_PRIMARY_NOT_BILLED")
        self.assertEqual(self.checked(dos=b"20250701", **msp_bene)[1], "DISPOSITION_01")
        self.assertEqual(self.checked(dos=b"20250415", **dict(msp_bene, primary=1))[1], "DISPOSITION_01")

    def test_zero_claim_is_checked(self):
        self.assertEqual(self.checked(full=b"Y"), ("ACCEPTED", "DISPOSITION_01", 0, 0))


class CwfParseTests(unittest.TestCase):
    B = b"BU1ENT0000012020010199999999----------------"

    def test_runtime_line_sequential_behaviour(self):
        self.assertEqual(len(msp.parse_cwf(self.B + b"\r\n").beneficiaries), 1)
        self.assertEqual(len(msp.parse_cwf(self.B).beneficiaries), 1)
        self.assertEqual(len(msp.parse_cwf(self.B + b" " * 30 + b"IGNORED\n").beneficiaries), 1)
        self.assertEqual(len(msp.parse_cwf(b"").beneficiaries), 0)

    def test_first_beneficiary_wins(self):
        other = b"BU1ENT0000012030010199999999----------------"
        self.assertEqual(msp.parse_cwf(self.B + b"\n" + other + b"\n").beneficiaries[b"U1ENT000001"].entitled_from,
                         20200101)

    def test_malformed_is_fatal(self):
        for bad in (b"", b"X" + self.B[1:], self.B[:40], self.B + b"Z", self.B[:28] + b"--------20251231",
                    self.B + b"\t", b"HU1ENT00000120250410000150000", b"B" + b" " * 11 + self.B[12:]):
            with self.subTest(bad=bad), self.assertRaises(msp.Fatal):
                msp.parse_cwf(self.B + b"\n" + bad + b"\n")
        with self.assertRaises(msp.Fatal):
            msp.parse_cwf(b"".join(b"B%011d2020010199999999----------------\n" % i for i in range(1001)))


class FramingTests(unittest.TestCase):
    def test_lf_crlf_and_final_line(self):
        self.assertEqual(list(msp.input_lines(b"a\r\nb\nc")), [b"a", b"b", b"c"])
        self.assertEqual(list(msp.input_lines(b"\n\n")), [b"", b""])
        self.assertEqual(list(msp.input_lines(b"a\r\r\n")), [b"a\r"])
        self.assertEqual(list(msp.input_lines(b"")), [])

    def test_transport_bound(self):
        self.assertEqual(len(next(msp.input_lines(b"X" * 4096 + b"\r\n"))), 4096)
        with self.assertRaises(msp.Fatal):
            list(msp.input_lines(b"X" * 4097))


class BatchTests(unittest.TestCase):
    def test_state_reset_after_rejected_record(self):
        batch = msp.Batch(REFERENCE)
        rejected = batch.process(patched(record(claim_id=b"R1", contract=1000), 72, b"?"))
        nxt = batch.process(record(claim_id=b"R2", primary=20000))
        self.assertEqual((rejected.reason, nxt.payment), ("BAD_FLAG", 80000))

    def test_duplicate_identifiable_id_is_fatal(self):
        batch = msp.Batch(REFERENCE)
        batch.process(patched(record(), 72, b"?"))
        with self.assertRaises(msp.Fatal):
            batch.process(record())

    def test_record_limit(self):
        batch = msp.Batch(REFERENCE)
        for _ in range(10000):
            batch.process(b"")
        with self.assertRaises(msp.Fatal):
            batch.process(b"")

    def test_csv_formatting(self):
        batch = msp.Batch(REFERENCE)
        claim = batch.process(record())
        self.assertEqual(msp.result_row(claim),
                         "0000000001,U1,PAID,0000040000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000040000\n")
        self.assertEqual(batch.totals_row(),
                         "0000000001,0000000001,0000000000,0000000000,000000000040000,0000000001,0000000000,"
                         "000000000040000\n")


class CliTests(unittest.TestCase):
    def test_usage_and_distinct_paths_exit_2(self):
        self.assertEqual(msp.run([]), 2)
        self.assertEqual(msp.run(["a", "b", "c", "c"]), 2)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p = [Path(d) / n for n in ("in", "cwf", "out", "tot")]
            p[0].write_bytes(record() + b"\n")
            p[1].write_bytes(b"BU1ENT0000012020010199999999----------------\n")
            done = subprocess.run([sys.executable, str(ROOT / "python/msp.py")] + [str(x) for x in p],
                                  capture_output=True)
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, b"", b""))
            self.assertTrue(p[2].read_text().startswith(msp.RESULT_HEADER + "\n0000000001,U1,PAID"))


if __name__ == "__main__":
    unittest.main()
