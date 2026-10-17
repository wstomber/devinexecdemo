"""Batch framing, limits, duplicates and usage — README interface, expectations written by hand.

Select the program with MSP_COMMAND (default build/msp-batch). All of these are
demo interface rules (README 'Architecture and interfaces'), not CMS policy.
"""
import tempfile
import unittest
from pathlib import Path

from msp_runner import ROOT, command, run_batch
import subprocess


def rec(claim_id, charges=100000, gross=80000, primary=10000, deductible=0,
        coinsurance=0, contract="----------", full="N"):
    """73-byte record. With the defaults: G-P = 70000 cents is the lowest limit."""
    contract = contract if isinstance(contract, str) else f"{contract:010d}"
    text = (claim_id.ljust(12) + f"{charges:010d}{gross:010d}{primary:010d}"
            f"{deductible:010d}{coinsurance:010d}" + contract + full)
    assert len(text) == 73
    return text.encode("ascii")


ZERO_TOTALS = {"records": 0, "paid": 0, "zero": 0, "invalid": 0, "payment_cents": 0}


class Framing(unittest.TestCase):
    def assertRows(self, run, expected):
        self.assertEqual(run.returncode, 0, run.stderr)
        got = [(r["record_no"], r["claim_id"], r["status"], r["payment_cents"], r["reason"])
               for r in run.rows()]
        self.assertEqual(got, expected)

    def test_crlf_and_lf_give_identical_results(self):
        expected = [(1, "F-1", "PAID", 70000, "SECONDARY_PAYABLE"),
                    (2, "F-2", "PAID", 70000, "SECONDARY_PAYABLE")]
        self.assertRows(run_batch(rec("F-1") + b"\n" + rec("F-2") + b"\n"), expected)
        self.assertRows(run_batch(rec("F-1") + b"\r\n" + rec("F-2") + b"\r\n"), expected)
        self.assertRows(run_batch(rec("F-1") + b"\r\n" + rec("F-2") + b"\n"), expected)

    def test_missing_final_newline_still_processes_last_record(self):
        run = run_batch(rec("F-1") + b"\n" + rec("F-2"))
        self.assertRows(run, [(1, "F-1", "PAID", 70000, "SECONDARY_PAYABLE"),
                              (2, "F-2", "PAID", 70000, "SECONDARY_PAYABLE")])
        self.assertEqual(run.totals()["payment_cents"], 140000)
        self.assertRows(run_batch(rec("F-3") + b"\r"), [(1, "F-3", "PAID", 70000, "SECONDARY_PAYABLE")])

    def test_empty_input_is_a_successful_zero_record_batch(self):
        run = run_batch(b"")
        self.assertRows(run, [])
        self.assertEqual(run.totals(), ZERO_TOTALS)

    def test_blank_and_cr_only_lines_are_bad_length_records(self):
        run = run_batch(rec("F-1") + b"\n\n\r\n" + rec("F-4") + b"\n")
        self.assertRows(run, [(1, "F-1", "PAID", 70000, "SECONDARY_PAYABLE"),
                              (2, "@0000000002", "INVALID", 0, "BAD_LENGTH"),
                              (3, "@0000000003", "INVALID", 0, "BAD_LENGTH"),
                              (4, "F-4", "PAID", 70000, "SECONDARY_PAYABLE")])
        self.assertEqual(run.totals(), {"records": 4, "paid": 2, "zero": 0, "invalid": 2,
                                        "payment_cents": 140000})

    def test_only_one_trailing_cr_is_removed(self):
        self.assertRows(run_batch(rec("F-1") + b"\r\r\n"), [(1, "@0000000001", "INVALID", 0, "BAD_LENGTH")])

    def test_non_ascii_digits_and_control_bytes_are_rejected(self):
        good = rec("U-1")
        superscript = good[:12] + b"\xb2" + good[13:]             # Latin-1 superscript two
        arabic = good[:12] + "\u0661".encode("utf-8") + good[14:]  # two bytes, still 73
        nul_id = b"U\x003" + good[3:]
        self.assertEqual(len(superscript), 73); self.assertEqual(len(arabic), 73)
        self.assertRows(run_batch(superscript + b"\n" + rec("U-2").replace(b"U-2", b"U-3") + b"\n"),
                        [(1, "U-1", "INVALID", 0, "BAD_AMOUNT"), (2, "U-3", "PAID", 70000, "SECONDARY_PAYABLE")])
        self.assertRows(run_batch(arabic + b"\n"), [(1, "U-1", "INVALID", 0, "BAD_AMOUNT")])
        self.assertRows(run_batch(nul_id + b"\n"), [(1, "@0000000001", "INVALID", 0, "BAD_ID")])

    def test_maximum_line_4096_bytes_is_one_invalid_record(self):
        line = b"A" * 4096
        for data in (line + b"\n", line + b"\r\n", line):
            with self.subTest(ending=data[-2:]):
                self.assertRows(run_batch(data + rec("AFTER") + b"\n" if data.endswith(b"\n") else data),
                                [(1, "@0000000001", "INVALID", 0, "BAD_LENGTH")]
                                + ([(2, "AFTER", "PAID", 70000, "SECONDARY_PAYABLE")] if data.endswith(b"\n") else []))


class Fatal(unittest.TestCase):
    def assertFatal(self, run):
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertTrue(run.stderr.strip())

    def test_line_of_4097_bytes_aborts(self):
        line = b"A" * 4097
        for data in (line + b"\n", line + b"\r\n", line, rec("OK") + b"\n" + line + b"\n"):
            with self.subTest(size=len(data)):
                self.assertFatal(run_batch(data))

    def test_duplicate_valid_ids_abort(self):
        self.assertFatal(run_batch(rec("DUP") + b"\n" + rec("DUP") + b"\n"))

    def test_duplicate_of_rejected_identifiable_record_aborts(self):
        self.assertFatal(run_batch(rec("DUP", full="X") + b"\n" + rec("DUP") + b"\n"))
        self.assertFatal(run_batch(rec("DUP", contract=200000) + b"\n" + rec("DUP", full="Q") + b"\n"))
        bad_amount = rec("DUP")[:12] + b"x" * 10 + rec("DUP")[22:]
        self.assertFatal(run_batch(rec("DUP") + b"\n" + bad_amount + b"\n"))

    def test_repeated_unidentifiable_records_are_not_duplicates(self):
        lower = rec("X").replace(b"X ", b"x ", 1)
        run = run_batch(b"\n\n" + lower + b"\n" + lower + b"\n")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([r["claim_id"] for r in run.rows()],
                         ["@0000000001", "@0000000002", "@0000000003", "@0000000004"])
        self.assertEqual(run.totals(), {"records": 4, "paid": 0, "zero": 0, "invalid": 4, "payment_cents": 0})


class RecordLimit(unittest.TestCase):
    MAX = 9_999_999_999

    def records(self, count):
        return b"".join(rec(f"N{i:011d}", charges=self.MAX, gross=self.MAX, primary=0) + b"\n"
                        for i in range(1, count + 1))

    def test_10000_maximum_payments(self):
        run = run_batch(self.records(10000), timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = run.rows()
        self.assertEqual(len(rows), 10000)
        self.assertEqual(rows[-1]["record_no"], 10000)
        self.assertTrue(all(r["payment_cents"] == self.MAX for r in rows))
        # 10,000 x 9,999,999,999 = 99,999,999,990,000 (fits the 15-digit total)
        self.assertEqual(run.totals(), {"records": 10000, "paid": 10000, "zero": 0, "invalid": 0,
                                        "payment_cents": 99_999_999_990_000})

    def test_10001_records_abort(self):
        self.assertEqual(run_batch(self.records(10001), timeout=120).returncode, 2)
        self.assertEqual(run_batch(self.records(10000) + b"\n", timeout=120).returncode, 2)


class Usage(unittest.TestCase):
    def call(self, args):
        return subprocess.run(command() + args, cwd=ROOT, capture_output=True, timeout=30)

    def test_argument_count(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.dat"; src.write_bytes(rec("U") + b"\n")
            out, tot = str(Path(d) / "o.csv"), str(Path(d) / "t.csv")
            for args in ([], [str(src)], [str(src), out], [str(src), out, tot, "extra"]):
                with self.subTest(argc=len(args)):
                    result = self.call(args)
                    self.assertEqual(result.returncode, 2)
                    self.assertTrue(result.stderr)
                    self.assertEqual(result.stdout, b"")

    def test_identical_paths_and_missing_input(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.dat"; src.write_bytes(rec("U") + b"\n")
            out, tot = str(Path(d) / "o.csv"), str(Path(d) / "t.csv")
            for args in ([str(src), str(src), tot], [str(src), out, str(src)], [str(src), out, out]):
                with self.subTest(args=args):
                    self.assertEqual(self.call(args).returncode, 2)
            self.assertEqual(src.read_bytes(), rec("U") + b"\n")
            self.assertEqual(self.call([str(Path(d) / "missing.dat"), out, tot]).returncode, 2)

    def test_success_writes_nothing_to_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.dat"; src.write_bytes(rec("U") + b"\n")
            result = self.call([str(src), str(Path(d) / "o.csv"), str(Path(d) / "t.csv")])
            self.assertEqual((result.returncode, result.stdout), (0, b""))


if __name__ == "__main__":
    unittest.main()
