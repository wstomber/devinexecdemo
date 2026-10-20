"""Batch/interface tests (Stage 2). Derived from the README contract, not from any program's output."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import LEDGER, RESULT_HEADER, TOTALS_HEADER, claim_line, command, cwf_lines, parse, run_batch

BASE = {"record_no": 0, "id": "BATCH1", "input": {"charges": 100000, "gross": 100000, "primary": 60000}}
ZERO_TOTALS = "0000000000,0000000000,0000000000,0000000000,000000000000000,0000000000,0000000000,000000000000000"


def line(claim_id="BATCH1", **fields):
    return claim_line({"id": claim_id, "input": dict(BASE["input"], **fields)}).encode("ascii")


GOOD_CWF = cwf_lines(LEDGER["cwf_reference"])
B_LINE, H_LINE = GOOD_CWF[0], GOOD_CWF[-1]


def cwf_bytes(lines):
    return ("\n".join(lines) + "\n").encode("ascii")


class FramingTests(unittest.TestCase):
    def rows(self, data):
        run = run_batch(data)
        self.assertEqual(run.returncode, 0, run.stderr)
        return parse(run)

    def test_crlf_and_missing_final_newline(self):
        data = line("CR1") + b"\r\n" + line("LF2") + b"\n" + line("NONL3")
        _, rows, _, totals = self.rows(data)
        self.assertEqual([r[1] for r in rows], ["CR1", "LF2", "NONL3"])
        self.assertTrue(all(r[2:4] == ["PAID", "0000040000"] for r in rows))
        self.assertEqual(totals[0], "0000000003")

    def test_crlf_on_last_record_without_newline_is_still_92_bytes(self):
        _, rows, _, _ = self.rows(line("CR1") + b"\r\n")
        self.assertEqual(rows[0][2], "PAID")

    def test_empty_input_is_zero_record_batch(self):
        header, rows, theader, totals = self.rows(b"")
        self.assertEqual((header, rows, theader), (RESULT_HEADER, [], TOTALS_HEADER))
        self.assertEqual(",".join(totals), ZERO_TOTALS)

    def test_blank_lines_are_records_not_eof(self):
        _, rows, _, totals = self.rows(b"\n" + line("AFTER") + b"\n\n")
        self.assertEqual([(r[1], r[4]) for r in rows],
                         [("@0000000001", "BAD_LENGTH"), ("AFTER", "SECONDARY_PAYABLE"),
                          ("@0000000003", "BAD_LENGTH")])
        self.assertEqual(totals[3], "0000000002")

    def test_4096_byte_line_is_one_invalid_record(self):
        for suffix in (b"\n", b"\r\n", b""):
            with self.subTest(suffix=suffix):
                _, rows, _, _ = self.rows(b"X" * 4096 + suffix)
                self.assertEqual([(r[1], r[2], r[4]) for r in rows], [("@0000000001", "INVALID", "BAD_LENGTH")])

    def test_4097_byte_line_is_fatal(self):
        for suffix in (b"\n", b"\r\n", b""):
            with self.subTest(suffix=suffix):
                run = run_batch(line("FIRST") + b"\n" + b"X" * 4097 + suffix)
                self.assertEqual(run.returncode, 2)
                self.assertTrue(run.stderr)

    def test_10000_records_at_maximum_payment(self):
        data = b"".join(line(f"M{i:011d}", charges=9999999999, gross=9999999999, primary=0) + b"\n"
                        for i in range(1, 10001))
        _, rows, _, totals = self.rows(data)
        self.assertEqual(len(rows), 10000)
        self.assertEqual(rows[-1][0], "0000010000")
        self.assertEqual(",".join(totals), "0000010000,0000010000,0000000000,0000000000,099999999990000,"
                                          "0000010000,0000000000,099999999990000")

    def test_10001_records_is_fatal(self):
        run = run_batch(b"X\n" * 10001)
        self.assertEqual(run.returncode, 2)
        self.assertTrue(run.stderr)

    def test_10000_short_records_succeed(self):
        _, rows, _, totals = self.rows(b"X\n" * 10000)
        self.assertEqual(totals[:4], ["0000010000", "0000000000", "0000000000", "0000010000"])


class IdentityTests(unittest.TestCase):
    def test_duplicate_valid_ids_are_fatal(self):
        run = run_batch(line("DUP") + b"\n" + line("DUP") + b"\n")
        self.assertEqual(run.returncode, 2)
        self.assertTrue(run.stderr)

    def test_duplicate_of_identifiable_rejected_record_is_fatal(self):
        bad_flag = line("DUP")[:72] + b"?" + line("DUP")[73:]
        run = run_batch(bad_flag + b"\n" + line("DUP") + b"\n")
        self.assertEqual(run.returncode, 2)

    def test_unidentifiable_records_never_collide(self):
        blank_id = b" " * 12 + line()[12:]
        run = run_batch(blank_id + b"\n" + blank_id + b"\n")
        self.assertEqual(run.returncode, 0, run.stderr)
        _, rows, _, _ = parse(run)
        self.assertEqual([r[1] for r in rows], ["@0000000001", "@0000000002"])


class CwfFileTests(unittest.TestCase):
    def assertFatal(self, cwf):
        run = run_batch(line() + b"\n", cwf=cwf)
        self.assertEqual(run.returncode, 2, run.results)
        self.assertTrue(run.stderr)

    def test_malformed_cwf_records_are_fatal(self):
        bad = {
            "unknown type": "X" + B_LINE[1:],
            "short B": B_LINE[:40],
            "B extra field": B_LINE + "Z",
            "B non-numeric date": B_LINE[:12] + "2020AB01" + B_LINE[20:],
            "B half-dashed MSP": B_LINE[:28] + "--------20251231",
            "B blank MBI": "B" + " " * 11 + B_LINE[12:],
            "short H": H_LINE[:29],
            "H extra field": H_LINE + "9",
            "H non-numeric charges": H_LINE[:20] + "00001O0000",
            "blank line": "",
        }
        for name, record in bad.items():
            with self.subTest(name=name):
                self.assertFatal(cwf_bytes(GOOD_CWF + [record]))

    def test_missing_cwf_file_is_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "in.dat"
            inp.write_bytes(line() + b"\n")
            run = run_batch(b"", extra_args=[str(inp), str(Path(d) / "absent.cwf"), str(Path(d) / "o"),
                                             str(Path(d) / "t")])
            self.assertEqual(run.returncode, 2)

    def test_1000_beneficiaries_allowed_1001_fatal(self):
        bene = [f"B{i:011d}2020010199999999{'-' * 16}" for i in range(1000)]
        run = run_batch(line(mbi="00000000999") + b"\n", cwf=cwf_bytes(bene))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(parse(run)[1][0][5:7], ["ACCEPTED", "DISPOSITION_01"])
        self.assertFatal(cwf_bytes(bene + [f"B{1000:011d}2020010199999999{'-' * 16}"]))

    def test_1000_history_allowed_1001_fatal(self):
        hist = [f"H{i:011d}202501010000000001" for i in range(1000)]
        run = run_batch(line() + b"\n", cwf=cwf_bytes(GOOD_CWF[:1] + hist))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFatal(cwf_bytes(GOOD_CWF[:1] + hist + ["H99999999999202501010000000001"]))


class UsageTests(unittest.TestCase):
    def test_usage_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = [str(Path(d) / n) for n in ("in.dat", "cwf.dat", "out.csv", "tot.csv")]
            Path(p[0]).write_bytes(line() + b"\n")
            Path(p[1]).write_bytes(cwf_bytes(GOOD_CWF))
            cases = {
                "no args": [], "three args": p[:3], "five args": p + [str(Path(d) / "x")],
                "same output and totals": [p[0], p[1], p[2], p[2]],
                "input equals output": [p[0], p[1], p[0], p[3]],
                "cwf equals totals": [p[0], p[1], p[2], p[1]],
                "missing input": [str(Path(d) / "absent"), p[1], p[2], p[3]],
                "unwritable output": [p[0], p[1], str(Path(d) / "no/dir/out.csv"), p[3]],
            }
            for name, args in cases.items():
                with self.subTest(name=name):
                    run = run_batch(b"", extra_args=args)
                    self.assertEqual(run.returncode, 2)
                    self.assertTrue(run.stderr)
                    self.assertEqual(run.stdout, b"")
            self.assertEqual(Path(p[0]).read_bytes(), line() + b"\n", "input must not be overwritten")

    def test_existing_outputs_are_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "results.csv").write_text("stale\n" * 100)
            (Path(d) / "totals.csv").write_text("stale\n" * 100)
            run = run_batch(line() + b"\n", directory=d)
            self.assertEqual(run.returncode, 0, run.stderr)
            _, rows, _, _ = parse(run)
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
