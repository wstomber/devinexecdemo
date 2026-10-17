"""Infrastructure and batch tests. Payment migration remains Devin's task."""
import csv
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fixtures import serialize, generate, case_record
from verify import run, batch_identities, VerificationError

ROOT = Path(__file__).resolve().parents[1]
BASELINE = str(ROOT / "build/msp-batch")


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.batch = self.directory / "input.dat"
        self.cases = json.loads((ROOT / "fixtures/curated.json").read_text())
        self.batch.write_text("".join(case_record(c) + "\n" for c in self.cases))
        self.identities = batch_identities(self.batch)

    def snapshot_stub(self, mutation):
        """Capture real output, then build a replay-only broken candidate.

        This is a harness fault injection, not a Python payment implementation.
        """
        output, totals = self.directory / "source.csv", self.directory / "totals.csv"
        subprocess.run([BASELINE, str(self.batch), str(output), str(totals)], check=True)
        with output.open() as stream:
            reader = csv.DictReader(stream)
            header, rows = reader.fieldnames, list(reader)
        total_text = totals.read_text()
        if mutation == "missing": rows.pop()
        elif mutation == "duplicate": rows.append(dict(rows[0]))
        elif mutation == "unexpected": rows[-1]["record_no"] = "9999"
        elif mutation == "claim_id": rows[0]["claim_id"] = "OTHER"
        elif mutation == "malformed": rows[0]["payment_cents"] = "1.5"
        elif mutation == "negative": rows[0]["payment_cents"] = "-1"
        elif mutation == "status": rows[0]["status"] = "UNKNOWN"
        elif mutation == "reason": rows[0]["reason"] = "UNKNOWN"
        elif mutation == "header": header = list(reversed(header))
        elif mutation == "total": total_text = total_text.replace("10000450202", "0")
        elif mutation == "amount":
            # Change a cent AND corresponding total, so parity must catch it.
            rows[0]["payment_cents"] = "150001"
            total_text = total_text.replace("10000450202", "10000450203")
        elif mutation == "reason-parity":
            rows[5]["reason"] = "PRIMARY_AT_CAP"
        with output.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader(); writer.writerows(rows)
        totals.write_text(total_text)
        stub = self.directory / "replay.py"
        stub.write_text(
            "import pathlib, sys\n"
            f"pathlib.Path(sys.argv[2]).write_text({output.read_text()!r})\n"
            f"pathlib.Path(sys.argv[3]).write_text({totals.read_text()!r})\n"
        )
        return shlex.join([sys.executable, str(stub)])

    def test_rejects_output_faults(self):
        for mutation in ("missing", "duplicate", "unexpected", "claim_id", "malformed",
                         "negative", "status", "reason", "header", "total"):
            with self.subTest(mutation=mutation):
                command = self.snapshot_stub(mutation)
                with self.assertRaises(VerificationError):
                    run(command, self.batch, self.identities, 5)

    def test_comparison_detects_one_cent_and_reason_mismatch(self):
        for mutation in ("amount", "reason-parity"):
            with self.subTest(mutation=mutation):
                command = self.snapshot_stub(mutation)
                report = self.directory / "report.json"
                result = subprocess.run([sys.executable, "tools/verify.py", "compare",
                                         "--candidate", command, "--input", str(self.batch),
                                         "--report", str(report)], cwd=ROOT, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stdout)
                payload = json.loads(report.read_text())
                self.assertEqual(payload["result"], "FAIL")
                self.assertEqual(len(payload["differences"]), 1)

    def test_unchanged_replay_passes_plumbing_only(self):
        command = self.snapshot_stub("none")
        actual, totals = run(command, self.batch, self.identities, 5)
        self.assertEqual(len(actual), 30)
        self.assertEqual(totals["payment_cents"], 10000450202)

    def test_candidate_can_be_verified_against_curated_expectations(self):
        command = self.snapshot_stub("none")
        result = subprocess.run([sys.executable, "tools/verify.py", "baseline", "--command", command,
                                 "--report", str(self.directory / "candidate-baseline.json")],
                                cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_crash_missing_executable_timeout_and_missing_output(self):
        for source in ("raise SystemExit(7)", "import time; time.sleep(2)", "pass"):
            stub = self.directory / "fail.py"
            stub.write_text(source)
            with self.subTest(source=source), self.assertRaises(VerificationError):
                run(shlex.join([sys.executable, str(stub)]), self.batch, self.identities, 0.1)
        with self.assertRaises(VerificationError):
            run("/no/such/executable", self.batch, self.identities, 1)

    def test_missing_candidate_is_not_a_pass(self):
        report = self.directory / "skipped.json"
        result = subprocess.run([sys.executable, "tools/verify.py", "compare", "--report", str(report)],
                                cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 2)
        payload = json.loads(report.read_text())
        self.assertEqual(payload["result"], "NOT_RUN")
        self.assertEqual(payload["migration_comparison"], "NOT_RUN")

    def test_empty_batch(self):
        self.batch.write_text("")
        rows, totals = run(BASELINE, self.batch, {}, 5)
        self.assertEqual(rows, {})
        self.assertTrue(all(value == 0 for value in totals.values()))

    def test_blank_record_is_invalid_not_eof(self):
        self.batch.write_text("\n" + serialize(self.cases[0]["input"]) + "\n")
        rows, totals = run(BASELINE, self.batch, batch_identities(self.batch), 5)
        self.assertEqual(rows[1]["reason"], "BAD_LENGTH")
        self.assertEqual(rows[2]["payment_cents"], 150000)
        self.assertEqual(totals["invalid"], 1)

    def test_duplicate_claim_id_is_fatal(self):
        line = serialize(self.cases[0]["input"])
        self.batch.write_text(line + "\n" + line + "\n")
        result = subprocess.run([BASELINE, str(self.batch), str(self.directory / "out"),
                                 str(self.directory / "totals")], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"duplicate claim ID", result.stderr)

    def test_crlf_and_last_record_without_newline(self):
        self.batch.write_bytes((serialize(self.cases[0]["input"]) + "\r\n"
                                + serialize(self.cases[1]["input"])).encode("ascii"))
        rows, totals = run(BASELINE, self.batch, batch_identities(self.batch), 5)
        self.assertEqual(totals["records"], 2)
        self.assertEqual(rows[2]["payment_cents"], 50000)

    def test_control_bytes_and_validation_precedence(self):
        line = serialize(self.cases[0]["input"])
        # Exact-width tab and null bytes must not turn into valid numeric data.
        records = [line[:22] + "\t" + line[23:], line[:22] + "\0" + line[23:],
                   " " * 12 + "?" * 60 + "?", line[:72] + "?"]
        records = [(f"CTRL{i}".ljust(12) + record[12:]) if i != 3 else record
                   for i, record in enumerate(records, 1)]
        self.batch.write_bytes(("\n".join(records) + "\n").encode("ascii"))
        rows, _ = run(BASELINE, self.batch, batch_identities(self.batch), 5)
        self.assertEqual([r["reason"] for r in rows.values()],
                         ["BAD_AMOUNT", "BAD_AMOUNT", "BAD_ID", "BAD_FLAG"])

    def test_oversized_physical_line_aborts_without_splitting(self):
        for suffix in ("\n", "\r\n", ""):
            self.batch.write_bytes(("X" * 4097 + suffix).encode("ascii"))
            result = subprocess.run([BASELINE, str(self.batch), str(self.directory / "out"),
                                     str(self.directory / "total")], capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_maximum_transport_length_is_one_invalid_record(self):
        for suffix in ("\n", "\r\n", ""):
            self.batch.write_bytes(("X" * 4096 + suffix).encode("ascii"))
            rows, totals = run(BASELINE, self.batch, batch_identities(self.batch), 5)
            self.assertEqual(totals["records"], 1)
            self.assertEqual(rows[1]["reason"], "BAD_LENGTH")

    def test_identifiable_invalid_duplicate_is_fatal(self):
        line = serialize(self.cases[0]["input"])
        self.batch.write_text(line[:72] + "?\n" + line + "\n")
        result = subprocess.run([BASELINE, str(self.batch), str(self.directory / "out"),
                                 str(self.directory / "total")], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"duplicate claim ID", result.stderr)

    def test_usage_missing_input_unwritable_output_and_record_limit(self):
        for args in ([], [str(self.directory / "absent"), str(self.directory / "out"),
                          str(self.directory / "total")],
                     [str(self.batch), str(self.directory / "absent/out"), str(self.directory / "total")]):
            result = subprocess.run([BASELINE] + args, capture_output=True)
            self.assertEqual(result.returncode, 2)
        self.batch.write_text("X\n" * 10001)
        result = subprocess.run([BASELINE, str(self.batch), str(self.directory / "out"),
                                 str(self.directory / "total")], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"10000 records", result.stderr)

    def test_seeded_batch_and_serialization(self):
        claims = list(generate(20261017, 1000))
        self.assertEqual(claims, list(generate(20261017, 1000)))
        self.batch.write_text("".join(serialize(c) + "\n" for c in claims))
        rows, totals = run(BASELINE, self.batch, batch_identities(self.batch), 10)
        self.assertEqual(len(rows), 1000)
        self.assertEqual(totals["invalid"], 0)
        self.assertGreater(totals["paid"], 0)
        self.assertGreater(totals["zero"], 0)

    def test_serializer_rejects_float_negative_overflow_missing_and_bad_flag(self):
        for field, value in (("gross", 1.1), ("primary", -1), ("charges", 10**10),
                             ("deductible", None), ("full", "?")):
            claim = dict(self.cases[0]["input"], **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                serialize(claim)


if __name__ == "__main__":
    unittest.main()
