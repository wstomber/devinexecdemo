"""Focused tests for the Python MSP processor."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import msp


def make_record(
    claim_id="CLAIM",
    charges=1000,
    gross=1000,
    primary=0,
    deductible=0,
    coinsurance=0,
    contract=None,
    full="N",
):
    raw_id = claim_id.encode("ascii").ljust(12, b" ")
    amounts = [f"{value:010d}".encode("ascii") for value in
               (charges, gross, primary, deductible, coinsurance)]
    raw_contract = b"----------" if contract is None else f"{contract:010d}".encode("ascii")
    record = raw_id + b"".join(amounts) + raw_contract + full.encode("ascii")
    assert len(record) == 73, (len(record), record)
    return record


def with_field(record, start, value):
    width = 12 if start == 0 else 1 if start == 72 else 10
    return record[:start] + value + record[start + width:]


class RecordValidation(unittest.TestCase):
    def test_each_validation_reason(self):
        valid = make_record()
        cases = [
            (valid[:-1], "BAD_LENGTH", "@0000000001"),
            (with_field(valid, 0, b" " * 12), "BAD_ID", "@0000000001"),
            (with_field(valid, 12, b"+000000000"), "BAD_AMOUNT", "CLAIM"),
            (with_field(valid, 62, b"+000000000"), "BAD_AMOUNT", "CLAIM"),
            (make_record(charges=100, contract=101), "BAD_CONTRACT", "CLAIM"),
            (with_field(valid, 72, b"X"), "BAD_FLAG", "CLAIM"),
        ]
        for record, reason, claim_id in cases:
            with self.subTest(reason=reason):
                result = msp.validate(record, 1)
                self.assertIsInstance(result, msp.Rejection)
                self.assertEqual((result.reason, result.claim_id), (reason, claim_id))

    def test_precedence_is_length_id_amount_contract_flag(self):
        valid = make_record(charges=100, contract=101, full="X")
        self.assertEqual(msp.validate(valid[:-1], 8).reason, "BAD_LENGTH")
        bad_id = with_field(valid, 0, b" " * 12)
        self.assertEqual(msp.validate(bad_id, 8).reason, "BAD_ID")
        bad_amount = with_field(valid, 12, b"+000000000")
        self.assertEqual(msp.validate(bad_amount, 8).reason, "BAD_AMOUNT")
        self.assertEqual(msp.validate(valid, 8).reason, "BAD_CONTRACT")
        no_contract_error = with_field(valid, 62, b"----------")
        self.assertEqual(msp.validate(no_contract_error, 8).reason, "BAD_FLAG")

    def test_id_rules_and_provisional_identifier(self):
        self.assertEqual(msp.validate(b"x", 42).claim_id, "@0000000042")
        for claim_id in ("lower", "A B", "A!", " " * 12):
            with self.subTest(claim_id=claim_id):
                record = make_record(claim_id="CLAIM")
                if claim_id == " " * 12:
                    record = with_field(record, 0, b" " * 12)
                else:
                    record = with_field(record, 0, claim_id.encode("ascii").ljust(12, b" "))
                result = msp.validate(record, 3)
                self.assertEqual((result.reason, result.claim_id), ("BAD_ID", "@0000000003"))

        accepted = msp.validate(make_record(claim_id="AB_9-X"), 1)
        self.assertIsInstance(accepted, msp.Claim)
        self.assertEqual(accepted.claim_id, "AB_9-X")

    def test_ascii_digit_fields_reject_non_ascii_and_other_characters(self):
        valid = make_record()
        invalid_values = [
            b"+000000000",
            b" 000000000",
            b"_000000000",
            "٣".encode("utf-8") + b"0" * 8,
            "１".encode("utf-8") + b"0" * 7,
        ]
        for value in invalid_values:
            self.assertEqual(len(value), 10)
            with self.subTest(value=value):
                self.assertEqual(msp.validate(with_field(valid, 12, value), 1).reason, "BAD_AMOUNT")


class Framing(unittest.TestCase):
    def test_lf_crlf_final_partial_and_blank_lines(self):
        first = make_record(claim_id="ONE")
        second = make_record(claim_id="TWO")
        self.assertEqual(list(msp.frame_lines(first + b"\r\n" + second)), [first, second])
        self.assertEqual(list(msp.frame_lines(b"\n" + first + b"\n\n")), [b"", first, b""])
        self.assertEqual(list(msp.frame_lines(b"")), [])

    def test_line_size_limits_and_crlf_buffer_edge(self):
        self.assertEqual(list(msp.frame_lines(b"X" * 4096 + b"\n")), [b"X" * 4096])
        self.assertEqual(list(msp.frame_lines(b"X" * 4096 + b"\r\n")), [b"X" * 4096])
        for data in (b"X" * 4097 + b"\n", b"X" * 4097, b"X" * 4097 + b"\r\n"):
            with self.subTest(length=len(data)):
                with self.assertRaises(msp.FatalBatchError):
                    list(msp.frame_lines(data))


class PaymentCalculation(unittest.TestCase):
    def payment(self, **kwargs):
        claim = msp.validate(make_record(**kwargs), 1)
        self.assertIsInstance(claim, msp.Claim)
        return msp.calculate_payment(claim)

    def test_cms_example_3_and_no_contract(self):
        inputs = dict(charges=1500000, gross=1400000, primary=1250000, deductible=155600)
        self.assertEqual(self.payment(claim_id="CMS-EX3", contract=1300000, **inputs),
                         ("PAID", 50000, "SECONDARY_PAYABLE"))
        self.assertEqual(self.payment(claim_id="CMS-EX3", **inputs),
                         ("PAID", 150000, "SECONDARY_PAYABLE"))

    def test_each_limit_can_control_and_equal_limits(self):
        examples = [
            (dict(charges=1000, gross=1000, primary=800, deductible=100), 200),
            (dict(charges=1000, gross=1000, primary=100, deductible=800), 200),
            (dict(charges=500, gross=1000, primary=400, deductible=100, contract=500), 100),
            (dict(charges=500, gross=1000, primary=100, deductible=400, contract=500), 100),
            (dict(charges=1000, gross=1000, primary=500, deductible=500), 500),
        ]
        for fields, expected in examples:
            with self.subTest(fields=fields):
                self.assertEqual(self.payment(**fields), ("PAID", expected, "SECONDARY_PAYABLE"))

    def test_one_cent_boundaries_zero_precedence_and_max_values(self):
        self.assertEqual(self.payment(charges=100, gross=100, primary=99),
                         ("PAID", 1, "SECONDARY_PAYABLE"))
        self.assertEqual(self.payment(charges=100, gross=100, primary=100),
                         ("ZERO", 0, "PRIMARY_AT_CAP"))
        self.assertEqual(self.payment(charges=100, gross=100, deductible=99),
                         ("PAID", 1, "SECONDARY_PAYABLE"))
        self.assertEqual(self.payment(charges=100, gross=100, deductible=100),
                         ("ZERO", 0, "DEDUCTIONS_AT_CAP"))
        self.assertEqual(self.payment(charges=100, gross=100, primary=100,
                                      deductible=100, full="Y"),
                         ("ZERO", 0, "PAYMENT_IN_FULL"))
        self.assertEqual(self.payment(charges=9999999999, gross=9999999999),
                         ("PAID", 9999999999, "SECONDARY_PAYABLE"))
        self.assertEqual(self.payment(charges=9999999999, gross=9999999999,
                                      deductible=9999999999, coinsurance=9999999999),
                         ("ZERO", 0, "DEDUCTIONS_AT_CAP"))

    def test_zero_payment_branch_precedence(self):
        self.assertEqual(self.payment(charges=100, gross=100, primary=100, deductible=100),
                         ("ZERO", 0, "PRIMARY_AT_CAP"))
        self.assertEqual(self.payment(charges=0, gross=0, full="N"),
                         ("ZERO", 0, "PRIMARY_AT_CAP"))


class BatchProcessing(unittest.TestCase):
    def test_state_resets_and_duplicate_rejected_identifiers_are_fatal(self):
        first = make_record(claim_id="SAME", charges=100, gross=100, contract=50)
        rejected = with_field(make_record(claim_id="BAD"), 72, b"X")
        third = make_record(claim_id="THIRD", charges=100, gross=100)
        rows, totals = msp.process_batch(first + b"\n" + rejected + b"\n" + third)
        self.assertEqual([row[3] for row in rows], [50, 0, 100])
        self.assertEqual(totals, (3, 2, 0, 1, 150))

        with self.assertRaisesRegex(msp.FatalBatchError, "duplicate"):
            msp.process_batch(rejected + b"\n" + with_field(rejected, 72, b"Y"))
        duplicate = make_record(claim_id="SAME")
        with self.assertRaisesRegex(msp.FatalBatchError, "duplicate"):
            msp.process_batch(duplicate + b"\n" + duplicate)

    def test_record_limit_including_blank_records(self):
        self.assertEqual(msp.process_batch(b"\n" * 10000)[1][0], 10000)
        with self.assertRaisesRegex(msp.FatalBatchError, "10000"):
            msp.process_batch(b"\n" * 10001)

    def test_output_formatting_is_fixed_width(self):
        self.assertEqual(
            msp.format_result_row((2, "CMS-EX3", "PAID", 50000, "SECONDARY_PAYABLE")),
            "0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE",
        )
        self.assertEqual(msp.format_totals_row((30, 12, 9, 9, 10000450202)),
                         "0000000030,0000000012,0000000009,0000000009,000010000450202")

    def test_main_exit_codes_and_byte_outputs(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(msp.main([]), 2)
            self.assertEqual(msp.main(["one", "two"]), 2)
            self.assertEqual(msp.main(["one", "two", "three", "four"]), 2)
            self.assertEqual(msp.main(["same", "same", "other"]), 2)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path, output_path, totals_path = root / "input.dat", root / "results.csv", root / "totals.csv"
            input_path.write_bytes(make_record(claim_id="A") + b"\n")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(msp.main([str(input_path), str(output_path), str(totals_path)]), 0)
                self.assertEqual(msp.main([str(root / "missing"), str(output_path), str(totals_path)]), 2)
                self.assertEqual(msp.main([str(input_path), str(root / "no" / "out.csv"),
                                           str(totals_path)]), 2)
            self.assertEqual(output_path.read_bytes(),
                             b"record_no,claim_id,status,payment_cents,reason\n"
                             b"0000000001,A,PAID,0000001000,SECONDARY_PAYABLE\n")
            self.assertTrue(totals_path.read_bytes().endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
