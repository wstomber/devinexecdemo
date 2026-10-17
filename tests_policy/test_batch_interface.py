"""Stage 2 batch/interface tests (README contract, not CMS policy), run against MSP_COMMAND."""
import unittest

from support import ROOT, command, record, run
import subprocess

EX3 = (1500000, 1400000, 1250000, 155600, 0, 1300000, "N")
EX3_NO_OTAF = (1500000, 1400000, 1250000, 155600, 0, None, "N")


def ids(rows):
    return [row[1] for row in rows[1:]]


class Framing(unittest.TestCase):
    def test_crlf_equals_lf(self):
        lines = [record("A1", *EX3), record("A2", *EX3_NO_OTAF)]
        lf = run(b"\n".join(lines) + b"\n")
        crlf = run(b"\r\n".join(lines) + b"\r\n")
        self.assertEqual(lf[0], 0)
        self.assertEqual(crlf[0], 0, crlf[3])
        self.assertEqual(lf[1:3], crlf[1:3])
        self.assertEqual([int(r[3]) for r in crlf[1][1:]], [50000, 150000])

    def test_missing_final_newline_still_processes_last_record(self):
        code, rows, totals, err = run(record("A1", *EX3) + b"\n" + record("A2", *EX3))
        self.assertEqual(code, 0, err)
        self.assertEqual(ids(rows), ["A1", "A2"])
        self.assertEqual(int(totals[1][4]), 100000)

    def test_empty_input_is_successful_zero_batch(self):
        code, rows, totals, err = run(b"")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows, [["record_no", "claim_id", "status", "payment_cents", "reason"]])
        self.assertEqual([int(v) for v in totals[1]], [0, 0, 0, 0, 0])

    def test_blank_line_between_records_is_bad_length_not_eof(self):
        code, rows, _, err = run(record("A1", *EX3) + b"\n\n" + record("A3", *EX3) + b"\n")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows[2][1:], ["@0000000002", "INVALID", rows[2][3], "BAD_LENGTH"])
        self.assertEqual(int(rows[2][3]), 0)
        self.assertEqual(ids(rows)[2], "A3")

    def test_4096_byte_line_is_one_invalid_record(self):
        code, rows, totals, err = run(b"X" * 4096 + b"\n" + record("A2", *EX3) + b"\n")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows[1][1:3] + rows[1][4:], ["@0000000001", "INVALID", "BAD_LENGTH"])
        self.assertEqual(int(totals[1][0]), 2)

    def test_4096_bytes_plus_crlf_is_accepted(self):
        code, rows, _, err = run(b"X" * 4096 + b"\r\n")
        self.assertEqual(code, 0, err)
        self.assertEqual(rows[1][4], "BAD_LENGTH")

    def test_4097_byte_line_is_fatal(self):
        self.assertEqual(run(b"X" * 4097 + b"\n")[0], 2)

    def test_4097_byte_final_line_without_newline_is_fatal(self):
        self.assertEqual(run(record("A1", *EX3) + b"\n" + b"X" * 4097)[0], 2)


class RecordLimit(unittest.TestCase):
    @staticmethod
    def batch(count):
        return b"".join(record("R%d" % n, 100, 100, 0, 0, 0, None, "N") + b"\n"
                        for n in range(1, count + 1))

    def test_10000_records_allowed(self):
        code, rows, totals, err = run(self.batch(10000))
        self.assertEqual(code, 0, err)
        self.assertEqual([int(v) for v in totals[1]], [10000, 10000, 0, 0, 1000000])
        self.assertEqual(int(rows[-1][0]), 10000)

    def test_10001_records_fatal(self):
        self.assertEqual(run(self.batch(10001))[0], 2)

    def test_10001st_blank_line_also_counts_as_record(self):
        self.assertEqual(run(self.batch(10000) + b"\n")[0], 2)


class DuplicateIds(unittest.TestCase):
    def test_duplicate_valid_ids_fatal(self):
        self.assertEqual(run(record("DUP", *EX3) + b"\n" + record("DUP", *EX3) + b"\n")[0], 2)

    def test_duplicate_with_rejected_first_occurrence_fatal(self):
        bad_flag = record("DUP", *EX3[:6], "X")
        self.assertEqual(run(bad_flag + b"\n" + record("DUP", *EX3) + b"\n")[0], 2)

    def test_duplicate_between_two_rejected_records_fatal(self):
        bad_contract = record("DUP", 100, 100, 0, 0, 0, 101, "N")
        self.assertEqual(run(bad_contract + b"\n" + bad_contract + b"\n")[0], 2)

    def test_unidentifiable_records_never_collide(self):
        code, rows, _, err = run(b"short\nshort\n" + b" " * 73 + b"\n")
        self.assertEqual(code, 0, err)
        self.assertEqual(ids(rows), ["@0000000001", "@0000000002", "@0000000003"])
        self.assertEqual([r[4] for r in rows[1:]], ["BAD_LENGTH", "BAD_LENGTH", "BAD_ID"])

    def test_similar_ids_are_distinct(self):
        code, rows, _, err = run(record("AB", *EX3) + b"\n" + record("AB-", *EX3) + b"\n")
        self.assertEqual(code, 0, err)


class StateReset(unittest.TestCase):
    def test_contract_does_not_leak_through_rejected_record(self):
        rejected = record("R2", *EX3[:6], "X")
        data = b"\n".join([record("R1", *EX3), rejected, record("R3", *EX3_NO_OTAF)]) + b"\n"
        code, rows, totals, err = run(data)
        self.assertEqual(code, 0, err)
        self.assertEqual([(r[2], int(r[3]), r[4]) for r in rows[1:]],
                         [("PAID", 50000, "SECONDARY_PAYABLE"), ("INVALID", 0, "BAD_FLAG"),
                          ("PAID", 150000, "SECONDARY_PAYABLE")])
        self.assertEqual([int(v) for v in totals[1]], [3, 2, 0, 1, 200000])

    def test_valid_after_malformed_amount_and_short_line(self):
        malformed = record("R1", *EX3).replace(b"0001500000", b"00015000.0", 1)
        data = b"\n".join([malformed, b"x" * 10, record("R3", *EX3)]) + b"\n"
        code, rows, _, err = run(data)
        self.assertEqual(code, 0, err)
        self.assertEqual([r[4] for r in rows[1:]], ["BAD_AMOUNT", "BAD_LENGTH", "SECONDARY_PAYABLE"])
        self.assertEqual(ids(rows), ["R1", "@0000000002", "R3"])
        self.assertEqual(int(rows[3][3]), 50000)

    def test_mixed_totals(self):
        data = b"\n".join([
            record("P1", *EX3),
            record("Z1", *EX3[:6], "Y"),
            record("P2", 9999999999, 9999999999, 0, 0, 0, None, "N"),
            b"",
        ]) + b"\n"
        code, _, totals, err = run(data)
        self.assertEqual(code, 0, err)
        self.assertEqual([int(v) for v in totals[1]], [4, 2, 1, 1, 10000049999])


class Usage(unittest.TestCase):
    def call(self, args):
        return subprocess.run(command() + args, cwd=ROOT, capture_output=True, timeout=60).returncode

    def test_wrong_argument_counts(self):
        self.assertEqual(self.call([]), 2)
        self.assertEqual(self.call(["a", "b"]), 2)
        self.assertEqual(self.call(["a", "b", "c", "d"]), 2)

    def test_identical_paths_rejected(self):
        code = run(record("A1", *EX3) + b"\n",
                   extra_args=lambda tmp, p: [str(p[0]), str(p[1]), str(p[1])])[0]
        self.assertEqual(code, 2)

    def test_missing_input_file(self):
        code = run(b"", extra_args=lambda tmp, p: [str(tmp / "absent.dat"), str(p[1]), str(p[2])])[0]
        self.assertEqual(code, 2)

    def test_unwritable_output(self):
        code = run(b"", extra_args=lambda tmp, p: [str(p[0]), str(tmp / "no" / "r.csv"), str(p[2])])[0]
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
