"""Batch/interface tests from the README contract, run through MSP_COMMAND."""
import tempfile
import unittest
from pathlib import Path

from common import command, ledger_cwf, run
import subprocess

CWF = ledger_cwf()


def claim(claim_id, charges=10000, contract="----------", full="N", mbi="7ACTIVE0001", dos="20240615"):
    return (claim_id.ljust(12) + f"{charges:010d}" + f"{charges:010d}" + "0" * 30 + contract + full + mbi + dos)


class FramingTests(unittest.TestCase):
    def test_empty_input_is_zero_record_success(self):
        code, rows, totals, _, _ = run(b"", CWF)
        self.assertEqual(code, 0)
        self.assertEqual(rows, [])
        self.assertEqual(set(totals.values()), {0})

    def test_crlf_and_missing_final_newline(self):
        data = (claim("LF") + "\n" + claim("CRLF") + "\r\n" + claim("NOEOL")).encode()
        code, rows, totals, _, _ = run(data, CWF)
        self.assertEqual(code, 0)
        self.assertEqual([(r["claim_id"], r["status"], r["payment_cents"]) for r in rows],
                         [("LF", "PAID", 10000), ("CRLF", "PAID", 10000), ("NOEOL", "PAID", 10000)])
        self.assertEqual(totals["records"], 3)

    def test_crlf_without_final_lf(self):
        code, rows, _, _, _ = run((claim("CRONLY") + "\r").encode(), CWF)
        self.assertEqual((code, rows[0]["status"]), (0, "PAID"))

    def test_blank_lines_are_bad_length_records(self):
        data = ("\n" + claim("AFTER") + "\n\r\n").encode()
        code, rows, totals, _, _ = run(data, CWF)
        self.assertEqual(code, 0)
        self.assertEqual([(r["claim_id"], r["reason"]) for r in rows],
                         [("@0000000001", "BAD_LENGTH"), ("AFTER", "SECONDARY_PAYABLE"), ("@0000000003", "BAD_LENGTH")])
        self.assertEqual(totals["invalid"], 2)

    def test_only_one_trailing_cr_is_removed(self):
        code, rows, _, _, _ = run((claim("TWOCR") + "\r\r\n").encode(), CWF)
        self.assertEqual((code, rows[0]["claim_id"], rows[0]["reason"]), (0, "@0000000001", "BAD_LENGTH"))

    def test_non_ascii_bytes_are_invalid_not_fatal(self):
        line = claim("UTF").encode()
        code, rows, _, _, _ = run(line[:13] + b"\xd9\xa1" + line[15:] + b"\n" + "é".encode() * 47 + b"\n", CWF)
        self.assertEqual(code, 0)
        self.assertEqual([r["reason"] for r in rows], ["BAD_AMOUNT", "BAD_LENGTH"])

    def test_transport_bound(self):
        for body, suffix, ok in ((4096, b"\n", True), (4096, b"\r\n", True), (4096, b"", True),
                                 (4097, b"\n", False), (4097, b"\r\n", False), (4097, b"", False),
                                 (5000, b"\n", False)):
            with self.subTest(body=body, suffix=suffix):
                long_line = b"X" * body + suffix
                data = (claim("NEXT").encode() + b"\n" + long_line) if not suffix else (long_line + claim("NEXT").encode() + b"\n")
                code, rows, _, _, _ = run(data, CWF)
                if ok:
                    self.assertEqual(code, 0)
                    self.assertEqual(sorted(r["reason"] for r in rows), ["BAD_LENGTH", "SECONDARY_PAYABLE"])
                else:
                    self.assertEqual(code, 2)

    def test_record_limit(self):
        code, _, totals, _, _ = run(b"X\n" * 10000, CWF)
        self.assertEqual((code, totals["records"], totals["invalid"]), (0, 10000, 10000))
        self.assertEqual(run(b"X\n" * 10001, CWF)[0], 2)
        self.assertEqual(run(b"X\n" * 10000 + b"\n", CWF)[0], 2)

    def test_provisional_ids_do_not_collide(self):
        code, rows, _, _, _ = run(b"SHORT\nSHORT\n" + (" " * 92).encode() + b"\n", CWF)
        self.assertEqual(code, 0)
        self.assertEqual([r["claim_id"] for r in rows], ["@0000000001", "@0000000002", "@0000000003"])


class DuplicateIdTests(unittest.TestCase):
    def test_duplicate_valid_ids_are_fatal(self):
        code, _, _, _, err = run((claim("TWIN") + "\n" + claim("TWIN", charges=5) + "\n").encode(), CWF)
        self.assertEqual(code, 2)
        self.assertIn(b"duplicate", err.lower())

    def test_duplicate_of_identifiable_invalid_record_is_fatal(self):
        for first, second in ((claim("TWIN", full="?"), claim("TWIN")),
                              (claim("TWIN"), claim("TWIN", contract="---------0"))):
            with self.subTest(first=first):
                self.assertEqual(run((first + "\n" + second + "\n").encode(), CWF)[0], 2)

    def test_padding_does_not_make_ids_distinct(self):
        self.assertEqual(run((claim("A") + "\n" + claim("A") + "\n").encode(), CWF)[0], 2)


class UsageAndFileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.d = Path(temp.name)
        (self.d / "in.dat").write_text(claim("ONE") + "\n")
        (self.d / "cwf.dat").write_text(CWF)

    def call(self, *args):
        return subprocess.run(command() + [str(a) for a in args], capture_output=True, timeout=60).returncode

    def test_wrong_argument_counts(self):
        d = self.d
        for args in ((), (d / "in.dat",), (d / "in.dat", d / "cwf.dat", d / "o"),
                     (d / "in.dat", d / "cwf.dat", d / "o", d / "t", d / "x")):
            with self.subTest(n=len(args)):
                self.assertEqual(self.call(*args), 2)

    def test_identical_paths(self):
        i, c, o, t = self.d / "in.dat", self.d / "cwf.dat", self.d / "o", self.d / "t"
        for args in ((i, c, i, t), (i, c, o, i), (i, c, o, o), (i, i, o, t), (i, c, c, t), (i, c, o, c)):
            with self.subTest(args=args):
                self.assertEqual(self.call(*args), 2)

    def test_missing_files(self):
        d = self.d
        self.assertEqual(self.call(d / "absent", d / "cwf.dat", d / "o", d / "t"), 2)
        self.assertEqual(self.call(d / "in.dat", d / "absent", d / "o", d / "t"), 2)
        self.assertEqual(self.call(d / "in.dat", d / "cwf.dat", d / "no/o", d / "t"), 2)
        self.assertEqual(self.call(d / "in.dat", d / "cwf.dat", d / "o", d / "no/t"), 2)
        self.assertEqual(self.call(d / "in.dat", d / "cwf.dat", d / "o", d / "t"), 0)


class CwfReferenceTests(unittest.TestCase):
    GOOD_B = "B7ACTIVE00012021060199999999" + "-" * 16
    GOOD_H = "H7POSTED0001202406100001500000"

    def batch(self, cwf):
        return run((claim("ONE") + "\n").encode(), cwf)

    def test_well_formed_reference_variants(self):
        for text in (self.GOOD_B + "\n", self.GOOD_B, self.GOOD_B + "\n" + self.GOOD_H + "\n",
                     self.GOOD_B + "   \n"):
            with self.subTest(text=text):
                code, rows, _, _, _ = self.batch(text)
                self.assertEqual((code, rows[0]["cwf"]), (0, "ACCEPTED"))

    def test_empty_reference_means_nobody_is_entitled(self):
        code, rows, totals, _, _ = self.batch("")
        self.assertEqual((code, rows[0]["cwf_reason"], totals["released_cents"]), (0, "NOT_ENTITLED", 0))

    def test_malformed_reference_is_fatal(self):
        b, h = self.GOOD_B, self.GOOD_H
        bad = {"unknown type": "X" + b[1:], "lowercase type": "b" + b[1:], "blank line": "",
               "B short": b[:40], "B extra byte": b + "Z", "B blank MBI": "B" + " " * 11 + b[12:],
               "B alpha date": b[:12] + "2021AB01" + b[20:], "B half MSP": b[:28] + "-" * 8 + "20241231",
               "B alpha MSP": b[:28] + "2024010120241X31", "H short": h[:29], "H extra": h + "0",
               "H alpha charges": h[:20] + "00015000X0", "H blank MBI": "H" + " " * 11 + h[12:]}
        for name, line in bad.items():
            with self.subTest(name=name):
                self.assertEqual(self.batch(b + "\n" + line + "\n")[0], 2)

    def test_table_limits(self):
        many_b = "".join(f"B9{n:010d}2020010199999999" + "-" * 16 + "\n" for n in range(1000))
        many_h = "".join(f"H9{n:010d}202401010000000001\n" for n in range(1000))
        self.assertEqual(self.batch(many_b)[0], 0)
        self.assertEqual(self.batch(many_b + self.GOOD_B + "\n")[0], 2)
        self.assertEqual(self.batch(many_h)[0], 0)
        self.assertEqual(self.batch(many_h + self.GOOD_H + "\n")[0], 2)


if __name__ == "__main__":
    unittest.main()
