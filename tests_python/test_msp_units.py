"""Layer B: focused unit tests for python/msp.py functions and boundaries.

    python3 -m unittest discover -s tests_python -v
"""
import gc
import io
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import msp  # noqa: E402


def raw(claim_id="T1", charges=100000, gross=100000, primary=10000, deductible=0,
        coinsurance=0, contract=None, full="N", mbi="1EG4TE5MK73", dos="20250315"):
    contract_field = "----------" if contract is None else f"{contract:010d}"
    return (claim_id.ljust(12) + f"{charges:010d}{gross:010d}{primary:010d}{deductible:010d}"
            f"{coinsurance:010d}" + contract_field + full + mbi + dos).encode("ascii")


REFERENCE = msp.CwfReference(
    {"1EG4TE5MK73": msp.Beneficiary(20200101, 99999999, None),
     "7WINDOW0001": msp.Beneficiary(20250201, 20250630, None),
     "7MSPWIN0001": msp.Beneficiary(20200101, 99999999, (20250301, 20250331))},
    frozenset({("7WINDOW0001", 20250315, 100000)}))
CWF_TEXT = ("B1EG4TE5MK732020010199999999----------------\n"
            "B7MSPWIN00012020010199999999202503012025033 1\n")


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
        self.assertEqual(c, msp.Claim("A_B-9", 1, 2, 3, 4, 5, 0, True, "1EG4TE5MK73", 20250315))
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
        b = msp.Batch(REFERENCE)
        rows = [msp.result_row(i + 1, b.process(r)) for i, r in enumerate([raw("P1"), raw("Z1", full="Y"), b"SHORT"])]
        self.assertEqual(rows, ["0000000001,P1,PAID,0000090000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000090000",
                                "0000000002,Z1,ZERO,0000000000,PAYMENT_IN_FULL,ACCEPTED,DISPOSITION_01,0000000000",
                                "0000000003,@0000000003,INVALID,0000000000,BAD_LENGTH,NOT_SENT,CLAIM_INVALID,0000000000"])
        self.assertEqual(b.totals_row(), "0000000003,0000000001,0000000001,0000000001,000000000090000,"
                                         "0000000002,0000000000,000000000090000")

    def test_rejected_claim_keeps_calculation_but_releases_nothing(self):
        b = msp.Batch(REFERENCE)
        result = b.process(raw("R1", mbi="7WINDOW0001", dos="20250701"))
        self.assertEqual((result.payment_cents, result.cwf, result.cwf_reason, result.released_cents),
                         (90000, "REJECTED", "NOT_ENTITLED", 0))
        self.assertEqual((b.payment_cents, b.released_cents, b.accepted, b.rejected), (90000, 0, 0, 1))

    def test_duplicate_identifiable_ids_are_fatal_but_reserved_ids_are_not(self):
        b = msp.Batch(REFERENCE)
        b.process(b"SHORT")
        b.process(b"SHORT")
        b.process(raw("D1"))
        with self.assertRaises(msp.FatalBatchError):
            b.process(raw("D1", full="?"))

    def test_record_limit(self):
        b = msp.Batch(REFERENCE)
        b.records = msp.MAX_RECORDS
        with self.assertRaises(msp.FatalBatchError):
            b.process(raw())

    def test_no_state_carries_between_records(self):
        b = msp.Batch(REFERENCE)
        self.assertEqual(b.process(raw("S1", contract=0, full="Q")).reason, "BAD_FLAG")
        self.assertEqual(b.process(raw("S2")).payment_cents, 90000)


class CwfCheckTests(unittest.TestCase):
    def check(self, **kw):
        c = claim(**kw)
        r = msp.cwf_check(c, msp.calculate(c), REFERENCE)
        return r.cwf, r.cwf_reason, r.released_cents

    def test_entitlement_period_is_inclusive(self):
        for dos, expected in (("20250131", "NOT_ENTITLED"), ("20250201", "DISPOSITION_01"),
                              ("20250630", "DISPOSITION_01"), ("20250701", "NOT_ENTITLED")):
            with self.subTest(dos=dos):
                self.assertEqual(self.check(mbi="7WINDOW0001", dos=dos, charges=100001)[1], expected)

    def test_unknown_beneficiary_is_not_entitled(self):
        self.assertEqual(self.check(mbi="9NOTONFILE9"), ("REJECTED", "NOT_ENTITLED", 0))

    def test_duplicate_needs_same_beneficiary_date_and_charges(self):
        self.assertEqual(self.check(mbi="7WINDOW0001", dos="20250315")[1], "DUPLICATE")
        self.assertEqual(self.check(mbi="7WINDOW0001", dos="20250315", charges=100001)[1], "DISPOSITION_01")
        self.assertEqual(self.check(mbi="7WINDOW0001", dos="20250316")[1], "DISPOSITION_01")

    def test_msp_period_requires_a_primary_payment(self):
        self.assertEqual(self.check(mbi="7MSPWIN0001", primary=0), ("REJECTED", "MSP_PRIMARY_NOT_BILLED", 0))
        self.assertEqual(self.check(mbi="7MSPWIN0001", primary=1), ("ACCEPTED", "DISPOSITION_01", 99999))
        self.assertEqual(self.check(mbi="7MSPWIN0001", primary=0, dos="20250401"), ("ACCEPTED", "DISPOSITION_01", 100000))

    def test_cms_ex3_is_accepted_and_releases_500(self):
        self.assertEqual(self.check(mbi="7MSPWIN0001", charges=1500000, gross=1400000, primary=1250000,
                                    deductible=155600, contract=1300000), ("ACCEPTED", "DISPOSITION_01", 50000))

    def test_new_fields_validate_after_flag(self):
        record = raw()
        self.assertEqual(msp.validate(record[:73] + b"1eg4te5mk73" + record[84:], 1)[1].reason, "BAD_MBI")
        self.assertEqual(msp.validate(record[:84] + b"20251301", 1)[1].reason, "BAD_DATE")
        self.assertEqual(msp.validate(record[:84] + b"20250100", 1)[1].reason, "BAD_DATE")
        self.assertEqual(msp.validate(record[:72] + b"?" + b"!" * 19, 1)[1].reason, "BAD_FLAG")
        self.assertEqual(msp.validate(record, 1)[1], None)

    def test_load_cwf_reads_both_record_types_and_rejects_bad_ones(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cwf.dat"
            path.write_text("B1EG4TE5MK732020010199999999----------------\n"
                            "B7MSPWIN000120200101999999992025030120250331\n"
                            "H7MSPWIN0001202503150000100000\n")
            reference = msp.load_cwf(str(path))
            self.assertEqual(reference.beneficiaries["7MSPWIN0001"].msp_period, (20250301, 20250331))
            self.assertIsNone(reference.beneficiaries["1EG4TE5MK73"].msp_period)
            self.assertEqual(reference.history, frozenset({("7MSPWIN0001", 20250315, 100000)}))
            for bad in ("X1EG4TE5MK73\n", "B1EG4TE5MK7320200101\n", CWF_TEXT,
                        "H7MSPWIN0001202503150000100000 Z\n", "\n", "B" + "1" * 70 + "\n"):
                with self.subTest(bad=bad), self.assertRaises(msp.FatalBatchError):
                    path.write_text(bad)
                    msp.load_cwf(str(path))
            with self.assertRaises(msp.FatalBatchError):
                msp.load_cwf(str(Path(directory) / "absent.dat"))


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.p = Path(self.dir.name)
        (self.p / "in.dat").write_bytes(raw() + b"\n")
        (self.p / "cwf.dat").write_text("B1EG4TE5MK732020010199999999----------------\n")

    def paths(self, *names):
        return [str(self.p / n) for n in names]

    def test_success_writes_exact_files(self):
        self.assertEqual(msp.main(self.paths("in.dat", "cwf.dat", "r.csv", "t.csv")), 0)
        self.assertEqual((self.p / "r.csv").read_text(),
                         "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents\n"
                         "0000000001,T1,PAID,0000090000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000090000\n")
        self.assertEqual((self.p / "t.csv").read_text(),
                         "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents\n"
                         "0000000001,0000000001,0000000000,0000000000,000000000090000,0000000001,0000000000,000000000090000\n")

    def test_usage_and_failure_exit_2(self):
        self.assertEqual(msp.main(self.paths("in.dat", "cwf.dat", "r.csv")), 2)
        self.assertEqual(msp.main(self.paths("in.dat", "in.dat", "r.csv", "t.csv")), 2)
        self.assertEqual(msp.main(self.paths("in.dat", "absent-cwf.dat", "r.csv", "t.csv")), 2)
        self.assertEqual(msp.main(self.paths("in.dat", "cwf.dat", "r.csv", "r.csv")), 2)
        self.assertEqual(msp.main(self.paths("absent.dat", "cwf.dat", "r.csv", "t.csv")), 2)
        self.assertEqual(msp.main(self.paths("in.dat", "cwf.dat", "missing-dir/r.csv", "t.csv")), 2)

    def test_totals_open_failure_closes_results_handle(self):
        (self.p / "t-dir").mkdir()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            self.assertEqual(msp.main(self.paths("in.dat", "cwf.dat", "r.csv", "t-dir")), 2)
            gc.collect()
        self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])


if __name__ == "__main__":
    unittest.main()
