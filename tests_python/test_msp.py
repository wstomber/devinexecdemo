import dataclasses
import unittest

from python.msp import (
    Beneficiary,
    CwfError,
    CwfReference,
    History,
    InputLineError,
    ascii_digits,
    calculate_payment,
    check_cwf,
    frame_input,
    parse_cwf,
    validate_claim,
    valid_claim_id,
)


MBI = b"P1MEDPRIM01"
DOS = b"20250610"


def claim_record(
    claim_id=b"CLAIM0000001",
    charges=10000,
    gross=10000,
    primary=2000,
    deductible=1000,
    coinsurance=500,
    contract=None,
    full=b"N",
    mbi=MBI,
    dos=DOS,
):
    if isinstance(claim_id, str):
        claim_id = claim_id.encode("ascii")
    contract_field = (
        b"----------" if contract is None else f"{contract:010d}".encode("ascii")
    )
    return (
        claim_id.ljust(12)
        + f"{charges:010d}".encode("ascii")
        + f"{gross:010d}".encode("ascii")
        + f"{primary:010d}".encode("ascii")
        + f"{deductible:010d}".encode("ascii")
        + f"{coinsurance:010d}".encode("ascii")
        + contract_field
        + full
        + mbi
        + dos
    )


def b_record(
    mbi=MBI,
    entitled_from=b"20200101",
    entitled_to=b"99999999",
    msp_from=None,
    msp_to=None,
):
    msp = (
        b"-" * 16
        if msp_from is None
        else msp_from + msp_to
    )
    return b"B" + mbi + entitled_from + entitled_to + msp


def h_record(mbi=MBI, dos=DOS, charges=10000):
    return b"H" + mbi + dos + f"{charges:010d}".encode("ascii")


def valid_claim(**kwargs):
    raw = claim_record(**kwargs)
    return validate_claim(raw, len(raw))


def priced_claim(**kwargs):
    claim = valid_claim(**kwargs)
    status, reason, payment = calculate_payment(claim)
    return dataclasses.replace(claim, status=status, reason=reason, payment=payment)


class AsciiAndIdTests(unittest.TestCase):
    def test_ascii_digits_rejects_non_ascii_and_non_digits(self):
        self.assertTrue(ascii_digits(b"0123456789"))
        self.assertFalse(ascii_digits(b""))
        for value in (
            b"+",
            b" ",
            b"_",
            b".",
            b"\x00",
            "٣".encode("utf-8"),
            "３".encode("utf-8"),
        ):
            with self.subTest(value=value):
                self.assertFalse(ascii_digits(value))

    def test_claim_id_rules(self):
        for value in (
            b"ABC123-_    ",
            b"ABCDEFGHIJKL",
            b"123456789012",
        ):
            with self.subTest(value=value):
                self.assertTrue(valid_claim_id(value))
        for value in (
            b" " * 12,
            b" lower      ",
            b"LEAD SPACE  ",
            b"EMBED DED   ",
            b"ID@         ",
            b"ID.PLUS     ",
            b"ID\x00        ",
        ):
            with self.subTest(value=value):
                self.assertFalse(valid_claim_id(value))


class ValidationTests(unittest.TestCase):
    def test_validation_precedence(self):
        base = claim_record()
        tests = (
            (
                b"lowercase  +" + b"+" + base[13:91],
                "BAD_LENGTH",
                b"@0000000001 ",
            ),
            (
                b"lowercase  +" + b"+" + base[13:],
                "BAD_ID",
                b"@0000000001 ",
            ),
            (
                base[:12]
                + b"+"
                + base[13:62]
                + b"0000010001"
                + b"X"
                + base[73:],
                "BAD_AMOUNT",
                b"CLAIM0000001",
            ),
            (
                base[:62]
                + b"0000010001"
                + b"X"
                + b"!" * 11
                + b"notadate",
                "BAD_CONTRACT",
                b"CLAIM0000001",
            ),
            (
                base[:72] + b"X" + b"!" * 11 + b"notadate",
                "BAD_FLAG",
                b"CLAIM0000001",
            ),
            (
                base[:73] + b"bad-mbi-123" + b"notadate",
                "BAD_MBI",
                b"CLAIM0000001",
            ),
            (
                base[:84] + b"20251399",
                "BAD_DATE",
                b"CLAIM0000001",
            ),
        )
        for raw, reason, claim_id in tests:
            with self.subTest(reason=reason):
                result = validate_claim(raw, len(raw))
                self.assertEqual(result.status, "INVALID")
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.claim_id, claim_id)

    def test_each_amount_field_requires_ascii_digits(self):
        base = claim_record()
        for offset in (12, 22, 32, 42, 52, 62):
            raw = base[:offset] + b"+000000000" + base[offset + 10 :]
            with self.subTest(offset=offset):
                self.assertEqual(validate_claim(raw, len(raw)).reason, "BAD_AMOUNT")

    def test_contract_flag_mbi_and_date_rules(self):
        raw = claim_record(contract=10001)
        self.assertEqual(validate_claim(raw, len(raw)).reason, "BAD_CONTRACT")

        raw = claim_record(full=b"X")
        self.assertEqual(validate_claim(raw, len(raw)).reason, "BAD_FLAG")

        raw = claim_record(mbi=b"2BAD-MBI   ")
        self.assertEqual(validate_claim(raw, len(raw)).reason, "BAD_MBI")

        for dos in (b"20250001", b"20251301", b"20250600", b"20250632", b"20250A10"):
            with self.subTest(dos=dos):
                raw = claim_record(dos=dos)
                self.assertEqual(validate_claim(raw, len(raw)).reason, "BAD_DATE")
        self.assertEqual(
            validate_claim(claim_record(dos=b"20250631"), 92).status,
            "VALID",
        )


class PaymentTests(unittest.TestCase):
    def test_payment_branches(self):
        cases = (
            (
                {"full": b"Y"},
                ("ZERO", "PAYMENT_IN_FULL", 0),
            ),
            (
                {"primary": 10000},
                ("ZERO", "PRIMARY_AT_CAP", 0),
            ),
            (
                {"deductible": 6000, "coinsurance": 4000, "primary": 0},
                ("ZERO", "DEDUCTIONS_AT_CAP", 0),
            ),
            (
                {"primary": 2000, "deductible": 1000, "coinsurance": 500},
                ("PAID", "SECONDARY_PAYABLE", 8000),
            ),
        )
        for fields, expected in cases:
            with self.subTest(fields=fields):
                self.assertEqual(calculate_payment(valid_claim(**fields)), expected)

    def test_contract_basis_and_cms_example_3(self):
        example = valid_claim(
            charges=1500000,
            gross=1400000,
            primary=1250000,
            deductible=155600,
            coinsurance=0,
            contract=1300000,
        )
        self.assertEqual(
            calculate_payment(example),
            ("PAID", "SECONDARY_PAYABLE", 50000),
        )
        without_otaf = valid_claim(
            charges=1500000,
            gross=1400000,
            primary=1250000,
            deductible=155600,
            coinsurance=0,
        )
        self.assertEqual(
            calculate_payment(without_otaf),
            ("PAID", "SECONDARY_PAYABLE", 150000),
        )


class CwfTests(unittest.TestCase):
    def test_cwf_parser_records_and_boundaries(self):
        data = (
            b_record()
            + b"\n"
            + h_record()
        )
        reference = parse_cwf(data)
        self.assertEqual(len(reference.beneficiaries), 1)
        self.assertEqual(len(reference.history), 1)

        padded = parse_cwf((b_record() + b" " * 20 + b"\n"))
        self.assertEqual(len(padded.beneficiaries), 1)
        self.assertEqual(parse_cwf(b""), CwfReference((), ()))
        self.assertEqual(parse_cwf(b_record()), parse_cwf(b_record() + b"\n"))

        with self.assertRaises(CwfError):
            parse_cwf(b"\n")
        with self.assertRaises(CwfError):
            parse_cwf(b"X" + b" " * 63 + b"\n")
        with self.assertRaises(CwfError):
            parse_cwf(b_record()[:28] + b"\n")

    def test_cwf_reader_drops_cr_truncates_and_pads(self):
        record = b_record()
        self.assertEqual(parse_cwf(record[:3] + b"\r" + record[3:]), parse_cwf(record))
        self.assertEqual(
            parse_cwf(record + b" " * 20 + b"X" * 29 + b"\xff"),
            parse_cwf(record),
        )
        with self.assertRaises(CwfError):
            parse_cwf(record[:20] + b"\t" + record[21:])
        with self.assertRaises(CwfError):
            parse_cwf(record[:12] + b"\x00" + record[13:])
        with self.assertRaises(CwfError):
            parse_cwf(record[:12] + b"\xff" + record[13:])
        with self.assertRaises(CwfError):
            parse_cwf(b"\x0c" + record)

    def test_cwf_record_limits(self):
        beneficiary = b_record() + b"\n"
        history = h_record() + b"\n"
        self.assertEqual(len(parse_cwf(beneficiary * 1000).beneficiaries), 1000)
        self.assertEqual(len(parse_cwf(history * 1000).history), 1000)
        with self.assertRaises(CwfError):
            parse_cwf(beneficiary * 1001)
        with self.assertRaises(CwfError):
            parse_cwf(history * 1001)

    def test_cwf_order_and_entitlement_boundaries(self):
        claim = priced_claim(primary=0)
        no_beneficiary = CwfReference((), (History(MBI, DOS, b"0000010000"),))
        self.assertEqual(check_cwf(claim, no_beneficiary)[:2], ("REJECTED", "NOT_ENTITLED"))

        outside = CwfReference(
            (Beneficiary(MBI, b"20250611", b"20250630", DOS, DOS),),
            (History(MBI, DOS, b"0000010000"),),
        )
        self.assertEqual(check_cwf(claim, outside)[:2], ("REJECTED", "NOT_ENTITLED"))

        duplicate_before_msp = CwfReference(
            (Beneficiary(MBI, b"20250610", b"20250610", DOS, DOS),),
            (History(MBI, DOS, b"0000010000"),),
        )
        self.assertEqual(
            check_cwf(claim, duplicate_before_msp)[:2],
            ("REJECTED", "DUPLICATE"),
        )

        msp_inclusive = CwfReference(
            (Beneficiary(MBI, DOS, DOS, DOS, DOS),),
            (),
        )
        self.assertEqual(
            check_cwf(claim, msp_inclusive)[:2],
            ("REJECTED", "MSP_PRIMARY_NOT_BILLED"),
        )

        outside_msp = CwfReference(
            (Beneficiary(MBI, DOS, DOS, b"20250611", b"20250612"),),
            (),
        )
        self.assertEqual(
            check_cwf(claim, outside_msp),
            ("ACCEPTED", "DISPOSITION_01", claim.payment),
        )

        accepted_boundary = CwfReference(
            (Beneficiary(MBI, DOS, DOS, None, None),),
            (),
        )
        self.assertEqual(check_cwf(claim, accepted_boundary)[0], "ACCEPTED")

    def test_first_beneficiary_record_wins(self):
        reference = parse_cwf(
            b_record(msp_from=None) + b"\n"
            + b_record(msp_from=DOS, msp_to=DOS) + b"\n"
        )
        claim = priced_claim(primary=0)
        self.assertEqual(check_cwf(claim, reference)[0], "ACCEPTED")


class FramingTests(unittest.TestCase):
    def test_lf_crlf_lone_cr_and_empty_stream(self):
        record = claim_record()
        self.assertEqual(frame_input(b""), [])
        self.assertEqual(frame_input(record + b"\n")[0].length, 92)
        self.assertEqual(frame_input(record + b"\r\n")[0].length, 92)
        lone_cr = frame_input(record + b"\n\r")
        self.assertEqual([entry.length for entry in lone_cr], [92, 0])
        blank = frame_input(b"\n")
        self.assertEqual(len(blank), 1)
        self.assertEqual(blank[0].length, 0)

    def test_transport_limit_and_claim_raw_padding(self):
        for stream in (b"X" * 4096 + b"\n", b"X" * 4096 + b"\r\n"):
            with self.subTest(ending=stream[-2:]):
                accepted_length = frame_input(stream)
                self.assertEqual(len(accepted_length), 1)
                self.assertEqual(accepted_length[0].length, 4096)
                self.assertEqual(len(accepted_length[0].data), 92)
        with self.assertRaises(InputLineError) as error:
            frame_input(b"X" * 4097 + b"\n")
        self.assertEqual(str(error.exception), "input line exceeds 4096 bytes")
        with self.assertRaises(InputLineError) as error:
            frame_input(b"X" * 4097 + b"\r\n")
        self.assertIsNone(error.exception.message)
        with self.assertRaises(InputLineError) as error:
            frame_input(b"X" * 5000)
        self.assertIsNone(error.exception.message)


if __name__ == "__main__":
    unittest.main()
