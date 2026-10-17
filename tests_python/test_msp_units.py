"""Layer B: focused unit tests for python/msp.py functions and boundaries.

    python3 -m unittest discover -s tests_python -v
"""
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import msp  # noqa: E402


def raw(claim_id="T1", charges=100000, gross=100000, primary=10000, deductible=0,
        coinsurance=0, contract=None, full="N"):
    contract_field = "----------" if contract is None else f"{contract:010d}"
    return (claim_id.ljust(12) + f"{charges:010d}{gross:010d}{primary:010d}{deductible:010d}"
            f"{coinsurance:010d}" + contract_field + full).encode("ascii")


def claim(**kw):
    parsed, rejected = msp.validate(raw(**kw), 1)
    assert rejected is None, rejected
    return parsed


class CalculateTests(unittest.TestCase):
    def test_cms_ex3_contract_replaces_charges_and_pays_500(self):
        ex3 = claim(claim_id="CMS-EX3", charges=1500000, gross=1400000, primary=1250000,
                    deductible=155600, contract=1300000)
        self.assertEqual(msp.charge_basis(ex3), 1300000)
        self.assertEqual(msp.payment_cap(ex3), 1300000)
        self.assertEqual(msp.calculate(ex3), msp.Result("CMS-EX3", "PAID", 50000, "SECONDARY_PAYABLE"))

    def test_cms_ex3_without_contract_would_pay_1500(self):
        no_otaf = claim(charges=1500000, gross=1400000, primary=1250000, deductible=155600)
        self.assertEqual(msp.charge_basis(no_otaf), 1500000)
        self.assertEqual(msp.calculate(no_otaf).payment_cents, 150000)

    def test_payment_cap_is_lower_of_gross_and_basis(self):
        self.assertEqual(msp.payment_cap(claim(charges=200000, gross=350000)), 200000)
        self.assertEqual(msp.payment_cap(claim(charges=500000, gross=300000)), 300000)
        self.assertEqual(msp.payment_cap(claim(charges=500000, gross=450000, contract=0)), 0)

    def test_larger_of_deductions_or_primary_is_subtracted(self):
        self.assertEqual(msp.calculate(claim(primary=30000, deductible=30001)).payment_cents, 69999)
        self.assertEqual(msp.calculate(claim(primary=30001, deductible=20000, coinsurance=10000)).payment_cents, 69999)

    def test_zero_reason_boundaries(self):
        cases = {
            "one cent under primary cap": (dict(primary=99999), ("PAID", 1, "SECONDARY_PAYABLE")),
            "primary at cap": (dict(primary=100000), ("ZERO", 0, "PRIMARY_AT_CAP")),
            "primary over cap": (dict(primary=100001), ("ZERO", 0, "PRIMARY_AT_CAP")),
            "deductions one cent under": (dict(primary=0, deductible=99999), ("PAID", 1, "SECONDARY_PAYABLE")),
            "deductions at cap": (dict(primary=0, deductible=60000, coinsurance=40000), ("ZERO", 0, "DEDUCTIONS_AT_CAP")),
            "full precedes primary": (dict(primary=200000, full="Y"), ("ZERO", 0, "PAYMENT_IN_FULL")),
            "primary precedes deductions": (dict(primary=100000, deductible=100000), ("ZERO", 0, "PRIMARY_AT_CAP")),
            "all zero": (dict(charges=0, gross=0, primary=0), ("ZERO", 0, "PRIMARY_AT_CAP")),
        }
        for name, (kw, expected) in cases.items():
            with self.subTest(name):
                r = msp.calculate(claim(**kw))
                self.assertEqual((r.status, r.payment_cents, r.reason), expected)

    def test_maximum_amounts_are_exact_integers(self):
        big = 9_999_999_999
        self.assertEqual(msp.calculate(claim(charges=big, gross=big, primary=0)).payment_cents, big)
        r = msp.calculate(claim(charges=big, gross=big, primary=0, deductible=big, coinsurance=big))
        self.assertEqual(r.reason, "DEDUCTIONS_AT_CAP")
        r = msp.calculate(claim(charges=big, gross=big, primary=big - 1, contract=big))
        self.assertIsInstance(r.payment_cents, int)
        self.assertEqual(r.payment_cents, 1)


class ValidateTests(unittest.TestCase):
    def reason(self, record, record_no=7):
        parsed, rejected = msp.validate(record, record_no)
        return ("VALID", parsed.claim_id) if parsed else (rejected.reason, rejected.claim_id)

    def test_valid_record_parses_all_fields(self):
        c = claim(claim_id="A_B-9", charges=1, gross=2, primary=3, deductible=4, coinsurance=5, contract=0, full="Y")
        self.assertEqual(c, msp.Claim("A_B-9", 1, 2, 3, 4, 5, 0, True))
        self.assertIsNone(claim().contract)

    def test_length_and_identity(self):
        self.assertEqual(self.reason(raw()[:72]), ("BAD_LENGTH", "@0000000007"))
        self.assertEqual(self.reason(raw() + b"Z"), ("BAD_LENGTH", "@0000000007"))
        self.assertEqual(self.reason(b""), ("BAD_LENGTH", "@0000000007"))
        for bad_id in (b"lower       ", b"AB CD       ", b" ABC        ", b"            ", b"A\x00          ", b"\xc9T          "):
            with self.subTest(bad_id):
                self.assertEqual(self.reason(bad_id + raw()[12:]), ("BAD_ID", "@0000000007"))
        self.assertEqual(self.reason(b"ABCDEFGHIJ12" + raw()[12:]), ("VALID", "ABCDEFGHIJ12"))

    def test_numeric_class_matches_cobol(self):
        for bad in (b"          ", b"+000000001", b"-000000001", b"0000001.00", b"00000 0001", b"\xd9\xa0" + b"0" * 8):
            with self.subTest(bad):
                self.assertFalse(msp.is_numeric(bad))
        self.assertTrue(msp.is_numeric(b"0000000000"))
        self.assertEqual(self.reason(raw()[:22] + b"          " + raw()[32:]), ("BAD_AMOUNT", "T1"))
        self.assertEqual(self.reason(raw()[:62] + b"---------0" + raw()[72:]), ("BAD_AMOUNT", "T1"))

    def test_contract_range_and_flag(self):
        self.assertEqual(self.reason(raw(contract=100001)), ("BAD_CONTRACT", "T1"))
        self.assertEqual(self.reason(raw(contract=100000)), ("VALID", "T1"))
        for flag in ("y", " ", "?"):
            self.assertEqual(self.reason(raw(full=flag)), ("BAD_FLAG", "T1"))

    def test_rejection_precedence(self):
        self.assertEqual(self.reason(b"lower       " + raw()[12:72]), ("BAD_LENGTH", "@0000000007"))
        self.assertEqual(self.reason(b"lower       " + raw()[12:22] + b" " * 10 + raw()[32:]), ("BAD_ID", "@0000000007"))
        self.assertEqual(self.reason(raw(full="X")[:42] + b"00000000.1" + raw(full="X")[52:]), ("BAD_AMOUNT", "T1"))
        self.assertEqual(self.reason(raw(contract=100001, full="X")), ("BAD_CONTRACT", "T1"))


class FramingTests(unittest.TestCase):
    def records(self, data):
        return list(msp.read_records(io.BytesIO(data)))

    def test_lf_crlf_blank_and_final_line(self):
        self.assertEqual(self.records(b""), [])
        self.assertEqual(self.records(b"A\nB\r\n\nC"), [b"A", b"B", b"", b"C"])
        self.assertEqual(self.records(b"A\r\r\n"), [b"A\r"])
        self.assertEqual(self.records(b"A\r"), [b"A"])

    def test_transport_limit(self):
        self.assertEqual(self.records(b"X" * 4096 + b"\n"), [b"X" * 4096])
        self.assertEqual(self.records(b"X" * 4096 + b"\r\n"), [b"X" * 4096])
        for data in (b"X" * 4097 + b"\n", b"X" * 4097, b"X" * 5000 + b"\r\n"):
            with self.subTest(len(data)), self.assertRaises(msp.FatalBatchError):
                self.records(data)

    def test_line_spanning_read_chunks(self):
        data = (b"Y" * 70000 + b"\n")
        with self.assertRaises(msp.FatalBatchError):
            self.records(data)
        data = b"\n".join([b"Z" * 100] * 2000) + b"\n"
        self.assertEqual(len(self.records(data)), 2000)


class BatchTests(unittest.TestCase):
    def test_counts_totals_and_formatting(self):
        b = msp.Batch()
        rows = [msp.result_row(i + 1, b.process(r)) for i, r in enumerate([raw("P1"), raw("Z1", full="Y"), b"SHORT"])]
        self.assertEqual(rows, ["0000000001,P1,PAID,0000090000,SECONDARY_PAYABLE",
                                "0000000002,Z1,ZERO,0000000000,PAYMENT_IN_FULL",
                                "0000000003,@0000000003,INVALID,0000000000,BAD_LENGTH"])
        self.assertEqual(b.totals_row(), "0000000003,0000000001,0000000001,0000000001,000000000090000")

    def test_duplicate_identifiable_ids_are_fatal_but_reserved_ids_are_not(self):
        b = msp.Batch()
        b.process(b"SHORT")
        b.process(b"SHORT")
        b.process(raw("D1"))
        with self.assertRaises(msp.FatalBatchError):
            b.process(raw("D1", full="?"))

    def test_record_limit(self):
        b = msp.Batch()
        b.records = msp.MAX_RECORDS
        with self.assertRaises(msp.FatalBatchError):
            b.process(raw())

    def test_no_state_carries_between_records(self):
        b = msp.Batch()
        self.assertEqual(b.process(raw("S1", contract=0, full="Q")).reason, "BAD_FLAG")
        self.assertEqual(b.process(raw("S2")).payment_cents, 90000)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.p = Path(self.dir.name)
        (self.p / "in.dat").write_bytes(raw() + b"\n")

    def paths(self, *names):
        return [str(self.p / n) for n in names]

    def test_success_writes_exact_files(self):
        self.assertEqual(msp.main(self.paths("in.dat", "r.csv", "t.csv")), 0)
        self.assertEqual((self.p / "r.csv").read_text(),
                         "record_no,claim_id,status,payment_cents,reason\n0000000001,T1,PAID,0000090000,SECONDARY_PAYABLE\n")
        self.assertEqual((self.p / "t.csv").read_text(),
                         "records,paid,zero,invalid,payment_cents\n0000000001,0000000001,0000000000,0000000000,000000000090000\n")

    def test_usage_and_failure_exit_2(self):
        self.assertEqual(msp.main(self.paths("in.dat", "r.csv")), 2)
        self.assertEqual(msp.main(self.paths("in.dat", "r.csv", "r.csv")), 2)
        self.assertEqual(msp.main(self.paths("absent.dat", "r.csv", "t.csv")), 2)
        self.assertEqual(msp.main(self.paths("in.dat", "missing-dir/r.csv", "t.csv")), 2)


if __name__ == "__main__":
    unittest.main()
