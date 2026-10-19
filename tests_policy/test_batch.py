import tempfile
import unittest
from pathlib import Path

from msp_harness import b_record, claim_record, cwf_file, h_record, run, run_args


MBI = "P1MEDPRIM01"
DOS = "20250610"
VALID_CWF = cwf_file(
    {
        "beneficiaries": [
            {
                "mbi": MBI,
                "entitled_from": "20200101",
                "entitled_to": "99999999",
            }
        ],
        "history": [],
    }
)


def valid_record(claim_id="T0000000001"):
    return claim_record(
        claim_id,
        charges=10000,
        gross=10000,
        primary=2000,
        deductible=1000,
        coinsurance=500,
        contract=None,
        full="N",
        mbi=MBI,
        dos=DOS,
    )


class BatchTests(unittest.TestCase):
    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def assert_invalid_row(self, row, record_no, reason, claim_id=None):
        self.assertEqual(int(row["record_no"]), record_no)
        self.assertEqual(
            row["claim_id"],
            claim_id if claim_id is not None else f"@{record_no:010d}",
        )
        self.assertEqual(row["status"], "INVALID")
        self.assertEqual(int(row["payment_cents"]), 0)
        self.assertEqual(row["reason"], reason)
        self.assertEqual(row["cwf"], "NOT_SENT")
        self.assertEqual(row["cwf_reason"], "CLAIM_INVALID")
        self.assertEqual(int(row["released_cents"]), 0)

    def test_crlf_missing_final_newline_and_final_carriage_return(self):
        record = valid_record()
        lf = run((record + "\n").encode("ascii"), VALID_CWF)
        crlf = run((record + "\r\n").encode("ascii"), VALID_CWF)
        self.assert_success(lf)
        self.assert_success(crlf)
        self.assertEqual(crlf.results, lf.results)
        self.assertEqual(crlf.totals, lf.totals)

        no_final_newline = run(record.encode("ascii"), VALID_CWF)
        self.assert_success(no_final_newline)
        self.assertEqual(no_final_newline.results, lf.results)

        carriage_return_line = run((record + "\n\r").encode("ascii"), VALID_CWF)
        self.assert_success(carriage_return_line)
        self.assertEqual(len(carriage_return_line.results), 2)
        self.assert_invalid_row(carriage_return_line.results[1], 2, "BAD_LENGTH")

    def test_empty_input(self):
        result = run(b"", VALID_CWF)
        self.assert_success(result)
        self.assertEqual(result.results, [])
        self.assertEqual(
            result.raw_results,
            "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,"
            "released_cents\n",
        )
        self.assertEqual(
            result.raw_totals,
            "records,paid,zero,invalid,payment_cents,accepted,rejected,"
            "released_cents\n0000000000,0000000000,0000000000,0000000000,"
            "000000000000000,0000000000,0000000000,000000000000000\n",
        )
        self.assertEqual(
            {key: int(value) for key, value in result.totals.items()},
            {
                "records": 0,
                "paid": 0,
                "zero": 0,
                "invalid": 0,
                "payment_cents": 0,
                "accepted": 0,
                "rejected": 0,
                "released_cents": 0,
            },
        )

    def test_blank_lines_are_bad_length_records(self):
        for blank_line in (b"\n", b"\r\n"):
            with self.subTest(blank_line=blank_line):
                result = run(
                    valid_record("T0000000001").encode("ascii")
                    + b"\n"
                    + blank_line
                    + valid_record("T0000000002").encode("ascii")
                    + b"\n",
                    VALID_CWF,
                )
                self.assert_success(result)
                self.assertEqual(len(result.results), 3)
                self.assert_invalid_row(result.results[1], 2, "BAD_LENGTH")
                self.assertEqual(result.results[0]["status"], "PAID")
                self.assertEqual(result.results[2]["status"], "PAID")

    def test_duplicate_ids_and_invalid_ids(self):
        duplicate_valid = run(
            (valid_record("DUPLICATE001") + "\n" + valid_record("DUPLICATE001") + "\n")
            .encode("ascii"),
            VALID_CWF,
        )
        self.assertEqual(duplicate_valid.returncode, 2)

        bad_amount = valid_record("DUPLICATE001")
        bad_amount = bad_amount[:12] + "+" + bad_amount[13:]
        duplicate_invalid = run(
            (valid_record("DUPLICATE001") + "\n" + bad_amount + "\n").encode("ascii"),
            VALID_CWF,
        )
        self.assertEqual(duplicate_invalid.returncode, 2)

        bad_id = valid_record("dup")
        two_bad_ids = run((bad_id + "\n" + bad_id + "\n").encode("ascii"), VALID_CWF)
        self.assert_success(two_bad_ids)
        self.assertEqual(
            [row["claim_id"] for row in two_bad_ids.results],
            ["@0000000001", "@0000000002"],
        )
        self.assertEqual([row["reason"] for row in two_bad_ids.results], ["BAD_ID"] * 2)

        two_bad_lengths = run(
            (valid_record()[:91] + "\n" + valid_record() + "X\n").encode("ascii"),
            VALID_CWF,
        )
        self.assert_success(two_bad_lengths)
        self.assertEqual(len(two_bad_lengths.results), 2)
        self.assert_invalid_row(two_bad_lengths.results[0], 1, "BAD_LENGTH")
        self.assert_invalid_row(two_bad_lengths.results[1], 2, "BAD_LENGTH")

    def test_missing_and_malformed_cwf_files(self):
        valid = b_record(MBI, "20200101", "99999999")
        malformed = [
            b"\n",
            b"X" + b" " * 63 + b"\n",
            (valid[:1].replace("B", "b") + valid[1:] + "\n").encode("ascii"),
            (valid[:28] + "\n").encode("ascii"),
            (
                b_record(MBI, "20200101", "99999999", "--------", "20251231")
                + "\n"
            ).encode("ascii"),
            b_record(" " * 11, "20200101", "99999999").encode("ascii") + b"\n",
            b_record(MBI, "2020A101", "99999999").encode("ascii") + b"\n",
            (valid + "X".ljust(20)).encode("ascii") + b"\n",
            h_record(MBI, DOS, 10000).encode("ascii") + b"X\n",
            ("H" + MBI + DOS + "000000000A\n").encode("ascii"),
        ]
        for index, cwf_bytes in enumerate(malformed):
            with self.subTest(malformed_case=index):
                result = run((valid_record() + "\n").encode("ascii"), cwf_bytes)
                self.assertEqual(result.returncode, 2, result.stderr)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "in.dat"
            input_path.write_text(valid_record() + "\n", encoding="ascii")
            result = run_args(
                [
                    str(input_path),
                    str(root / "missing-cwf.dat"),
                    str(root / "results.csv"),
                    str(root / "totals.csv"),
                ]
            )
            self.assertEqual(result.returncode, 2)

    def test_cwf_record_limits_and_valid_edges(self):
        beneficiary = b_record(MBI, "20200101", "99999999")
        history = h_record(MBI, DOS, 10000)
        too_many_beneficiaries = (beneficiary + "\n") * 1001
        too_many_history = (history + "\n") * 1001
        for data in (
            too_many_beneficiaries.encode("ascii"),
            too_many_history.encode("ascii"),
        ):
            with self.subTest(cwf_records=len(data)):
                result = run((valid_record() + "\n").encode("ascii"), data)
                self.assertEqual(result.returncode, 2, result.stderr)

        exactly_1000_each = run(
            (valid_record() + "\n").encode("ascii"),
            ((beneficiary + "\n") * 1000 + (history + "\n") * 1000).encode("ascii"),
        )
        self.assert_success(exactly_1000_each)

        empty_cwf = run(
            (valid_record() + "\n" + valid_record()[:91] + "\n").encode("ascii"),
            b"",
        )
        self.assert_success(empty_cwf)
        self.assertEqual(empty_cwf.results[0]["cwf"], "REJECTED")
        self.assertEqual(empty_cwf.results[0]["cwf_reason"], "NOT_ENTITLED")
        self.assertEqual(empty_cwf.results[1]["cwf"], "NOT_SENT")

        lf = run((valid_record() + "\n").encode("ascii"), (beneficiary + "\n").encode())
        crlf = run(
            (valid_record() + "\n").encode("ascii"),
            (beneficiary + "\r\n").encode(),
        )
        self.assert_success(lf)
        self.assert_success(crlf)
        self.assertEqual(crlf.results, lf.results)

        padded_beneficiary = run(
            (valid_record() + "\n").encode("ascii"),
            (beneficiary.ljust(64) + "\n").encode("ascii"),
        )
        self.assert_success(padded_beneficiary)
        self.assertEqual(padded_beneficiary.results[0]["cwf"], "ACCEPTED")

    def test_line_lengths_and_transport_limit(self):
        record = valid_record().encode("ascii")
        for data in (record[:91] + b"\n", record + b"X\n"):
            with self.subTest(length=len(data.rstrip(b"\n"))):
                result = run(data, VALID_CWF)
                self.assert_success(result)
                self.assertEqual(len(result.results), 1)
                self.assert_invalid_row(result.results[0], 1, "BAD_LENGTH")

        line_4096 = record + b"X" * (4096 - len(record))
        for data in (line_4096 + b"\n", line_4096 + b"\r\n"):
            with self.subTest(transport_length=len(data)):
                result = run(data, VALID_CWF)
                self.assert_success(result)
                self.assertEqual(len(result.results), 1)
                self.assert_invalid_row(result.results[0], 1, "BAD_LENGTH")

        line_4097 = record + b"X" * (4097 - len(record))
        for data in (line_4097 + b"\n", line_4097 + b"\r\n", b"X" * 5000):
            with self.subTest(transport_length=len(data)):
                result = run(data, VALID_CWF)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_record_count_limit(self):
        ten_thousand = "".join(
            valid_record(f"T{number:011d}") + "\n"
            for number in range(1, 10001)
        ).encode("ascii")
        result = run(ten_thousand, VALID_CWF)
        self.assert_success(result)
        self.assertEqual(int(result.totals["records"]), 10000)
        self.assertEqual(len(result.results), 10000)

        ten_thousand_one = ten_thousand + (
            valid_record("T00000010001") + "\n"
        ).encode("ascii")
        result = run(ten_thousand_one, VALID_CWF)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_usage_and_path_errors(self):
        for args in ([], ["one", "two", "three"], ["one", "two", "three", "four", "five"]):
            with self.subTest(arg_count=len(args)):
                result = run_args(args)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(result.stderr)

        for args in (
            ["same", "cwf", "same", "totals"],
            ["input", "same", "output", "same"],
        ):
            with self.subTest(paths=args):
                self.assertEqual(run_args(args).returncode, 2)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cwf_path = root / "cwf.dat"
            cwf_path.write_bytes(VALID_CWF)
            missing_input = run_args(
                [
                    str(root / "missing-input.dat"),
                    str(cwf_path),
                    str(root / "results.csv"),
                    str(root / "totals.csv"),
                ]
            )
            self.assertEqual(missing_input.returncode, 2)

            input_path = root / "in.dat"
            input_path.write_text(valid_record() + "\n", encoding="ascii")
            missing_output_dir = root / "does-not-exist"
            bad_output = run_args(
                [
                    str(input_path),
                    str(cwf_path),
                    str(missing_output_dir / "results.csv"),
                    str(root / "totals.csv"),
                ]
            )
            self.assertEqual(bad_output.returncode, 2)

    def test_byte_level_validation(self):
        original = bytearray(valid_record().encode("ascii"))
        malformed = []

        bad_id = original.copy()
        bad_id[3] = 0xC9
        malformed.append((bytes(bad_id), "BAD_ID"))

        bad_charges = original.copy()
        bad_charges[12:22] = b"00000000\xd9\xa1"
        malformed.append((bytes(bad_charges), "BAD_AMOUNT"))

        nul_primary = original.copy()
        nul_primary[32] = 0
        malformed.append((bytes(nul_primary), "BAD_AMOUNT"))

        fullwidth_primary = original.copy()
        fullwidth_primary[32:35] = "\uff11".encode("utf-8")
        malformed.append((bytes(fullwidth_primary), "BAD_AMOUNT"))

        for raw, expected_reason in malformed:
            with self.subTest(expected_reason=expected_reason, record=raw):
                result = run(raw + b"\n", VALID_CWF)
                self.assert_success(result)
                self.assertEqual(len(result.results), 1)
                self.assert_invalid_row(
                    result.results[0],
                    1,
                    expected_reason,
                    claim_id="T0000000001" if expected_reason == "BAD_AMOUNT" else None,
                )


if __name__ == "__main__":
    unittest.main()
