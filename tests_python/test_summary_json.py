"""Black-box acceptance tests for the optional batch summary JSON output."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "python" / "msp.py"


def raw(claim_id="T1", charges=100000, gross=100000, primary=10000, deductible=0,
        coinsurance=0, contract=None, full="N", mbi="1EG4TE5MK73", dos="20250315"):
    contract_field = "----------" if contract is None else f"{contract:010d}"
    record = (claim_id.ljust(12) + f"{charges:010d}{gross:010d}{primary:010d}{deductible:010d}"
              f"{coinsurance:010d}" + contract_field + full + mbi + dos).encode("ascii")
    assert len(record) == 92
    return record


class SummaryJsonTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.directory = Path(self.tempdir.name)
        self.input = self.directory / "input.dat"
        self.results = self.directory / "results.csv"
        self.totals = self.directory / "totals.csv"
        self.summary = self.directory / "summary.json"
        self.cwf = self.directory / "cwf.dat"
        self.cwf.write_text("B1EG4TE5MK732020010199999999----------------\n")

    def write_input(self, data):
        self.input.write_bytes(data)

    def cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(arg) for arg in args)],
            cwd=cwd or self.directory,
            capture_output=True,
        )

    def assert_summary_matches_totals(self, summary_path, totals_path):
        raw_json = Path(summary_path).read_bytes()
        text = raw_json.decode("ascii")
        self.assertTrue(text.endswith("\n"))
        summary = json.loads(text)
        self.assertIsInstance(summary, dict)
        self.assertEqual(
            set(summary),
            {"records", "paid", "zero", "invalid", "payment_cents", "accepted", "rejected", "released_cents"},
        )
        for value in summary.values():
            self.assertIs(type(value), int)
        totals_fields = Path(totals_path).read_text(encoding="ascii").splitlines()[1].split(",")
        self.assertEqual(
            summary,
            dict(zip(
                ("records", "paid", "zero", "invalid", "payment_cents", "accepted", "rejected", "released_cents"),
                map(int, totals_fields),
            )),
        )
        return text, summary

    def test_no_flag_csv_bytes_and_flag_preserves_csv(self):
        self.write_input(raw() + b"\n")
        plain_results = self.directory / "plain-results.csv"
        plain_totals = self.directory / "plain-totals.csv"
        plain = self.cli(self.input, self.cwf, plain_results, plain_totals)
        self.assertEqual(plain.returncode, 0, plain.stderr.decode("ascii"))
        self.assertEqual(
            plain_results.read_text(encoding="ascii"),
            "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents\n"
            "0000000001,T1,PAID,0000090000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000090000\n",
        )
        self.assertEqual(
            plain_totals.read_text(encoding="ascii"),
            "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents\n"
            "0000000001,0000000001,0000000000,0000000000,000000000090000,0000000001,0000000000,000000000090000\n",
        )
        self.assertEqual(
            sorted(path.name for path in self.directory.iterdir()),
            ["cwf.dat", "input.dat", "plain-results.csv", "plain-totals.csv"],
        )

        flagged_results = self.directory / "flagged-results.csv"
        flagged_totals = self.directory / "flagged-totals.csv"
        flagged = self.cli(
            self.input, self.cwf, flagged_results, flagged_totals, "--summary-json", self.summary
        )
        self.assertEqual(flagged.returncode, 0, flagged.stderr.decode("ascii"))
        self.assertEqual(flagged_results.read_bytes(), plain_results.read_bytes())
        self.assertEqual(flagged_totals.read_bytes(), plain_totals.read_bytes())

    def test_summary_contract_matches_totals(self):
        self.write_input(raw() + b"\n")
        proc = self.cli(self.input, self.cwf, self.results, self.totals, "--summary-json", self.summary)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("ascii"))
        _, summary = self.assert_summary_matches_totals(self.summary, self.totals)
        self.assertEqual(summary, {
            "records": 1, "paid": 1, "zero": 0, "invalid": 0, "payment_cents": 90000,
            "accepted": 1, "rejected": 0, "released_cents": 90_000,
        })

    def test_integer_cents_are_exact(self):
        maximum = 9_999_999_999
        records = [
            raw("CMS-EX3", charges=1_500_000, gross=1_400_000, primary=1_250_000,
                deductible=155_600, contract=1_300_000),
            raw("MAX1", charges=maximum, gross=maximum, primary=0),
            raw("MAX2", charges=maximum, gross=maximum, primary=0),
        ]
        # CMS-EX3 pays 1,300,000 - max(1,250,000, 155,600) = 50,000 cents;
        # each maximum claim pays 9,999,999,999 cents, with no rounding.
        self.write_input(b"\n".join(records) + b"\n")
        proc = self.cli(self.input, self.cwf, self.results, self.totals, "--summary-json", self.summary)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("ascii"))
        text, summary = self.assert_summary_matches_totals(self.summary, self.totals)
        self.assertEqual(summary["payment_cents"], 50_000 + 2 * maximum)
        numeric_tokens = re.findall(r":\s*([^,}\s]+)", text)
        self.assertEqual(len(numeric_tokens), 8)
        for token in numeric_tokens:
            self.assertTrue(token.isdigit(), token)
            self.assertNotRegex(token, r"[.eE]")

    def test_empty_batch_summary_matches_totals(self):
        self.write_input(b"")
        proc = self.cli(self.input, self.cwf, self.results, self.totals, "--summary-json", self.summary)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("ascii"))
        _, summary = self.assert_summary_matches_totals(self.summary, self.totals)
        self.assertEqual(summary, {
            "records": 0, "paid": 0, "zero": 0, "invalid": 0, "payment_cents": 0,
            "accepted": 0, "rejected": 0, "released_cents": 0,
        })

    def test_mixed_validity_counts_match_totals(self):
        records = [
            raw("PAID"),
            raw("FULL", full="Y"),
            raw("ATCAP", primary=100_000),
            b"SHORT",
            raw("lower"),
            raw("BADFLAG", full="X"),
            raw("BADCON", charges=100_000, contract=100_001),
        ]
        # One paid record pays 100,000 - max(10,000, 0) = 90,000 cents;
        # the next two are zero and the four malformed records are invalid.
        self.write_input(b"\n".join(records) + b"\n")
        proc = self.cli(self.input, self.cwf, self.results, self.totals, "--summary-json", self.summary)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("ascii"))
        _, summary = self.assert_summary_matches_totals(self.summary, self.totals)
        self.assertEqual(summary, {
            "records": 7, "paid": 1, "zero": 2, "invalid": 4, "payment_cents": 90_000,
            "accepted": 3, "rejected": 0, "released_cents": 90_000,
        })

    def test_option_positions_and_equals_form(self):
        self.write_input(raw() + b"\n")
        invocations = [
            ("before", lambda p: ("--summary-json", p, self.input, self.cwf, p.parent / "r.csv", p.parent / "t.csv")),
            ("between", lambda p: (self.input, self.cwf, "--summary-json", p, p.parent / "r.csv", p.parent / "t.csv")),
            ("after", lambda p: (self.input, self.cwf, p.parent / "r.csv", p.parent / "t.csv", "--summary-json", p)),
            ("equals", lambda p: (self.input, self.cwf, p.parent / "r.csv", p.parent / "t.csv", f"--summary-json={p}")),
        ]
        outputs = []
        for name, args_for in invocations:
            with self.subTest(position=name):
                case_dir = self.directory / name
                case_dir.mkdir()
                case_input = case_dir / "input.dat"
                case_input.write_bytes(self.input.read_bytes())
                case_summary = case_dir / "summary.json"
                args = tuple(str(arg).replace(str(self.input), str(case_input)) for arg in args_for(case_summary))
                proc = self.cli(*args)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode("ascii"))
                results = case_dir / "r.csv"
                totals = case_dir / "t.csv"
                self.assert_summary_matches_totals(case_summary, totals)
                outputs.append((results.read_bytes(), totals.read_bytes(), case_summary.read_bytes()))
        self.assertTrue(all(output == outputs[0] for output in outputs[1:]))

    def test_fatal_duplicate_does_not_write_or_replace_summary(self):
        self.write_input(raw("DUP") + b"\n" + raw("DUP") + b"\n")
        proc = self.cli(self.input, self.cwf, self.results, self.totals, "--summary-json", self.summary)
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"discard outputs", proc.stderr)
        self.assertFalse(self.summary.exists())

        previous = b'{"previous":"summary"}\n'
        self.summary.write_bytes(previous)
        proc = self.cli(
            self.input, self.cwf, self.directory / "again-results.csv", self.directory / "again-totals.csv",
            "--summary-json", self.summary,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"discard outputs", proc.stderr)
        self.assertEqual(self.summary.read_bytes(), previous)

    def test_summary_path_collisions_are_rejected_before_open(self):
        self.write_input(raw() + b"\n")
        cases = []

        def add_case(label, summary_path):
            out = self.directory / f"{label}-results.csv"
            totals = self.directory / f"{label}-totals.csv"
            cases.append((label, summary_path, out, totals))

        add_case("input-same", self.input)
        add_case("output-same", self.directory / "output-same-results.csv")
        add_case("totals-same", self.directory / "totals-same-totals.csv")

        (self.directory / "sub").mkdir()
        add_case("totals-realpath", self.directory / "sub" / ".." / "totals-realpath-totals.csv")
        input_link = self.directory / "input-link.dat"
        input_link.symlink_to(self.input)
        add_case("input-symlink", input_link)

        for label, summary_path, output, totals in cases:
            with self.subTest(collision=label):
                original_input = self.input.read_bytes()
                proc = self.cli(
                    self.input, self.cwf, output, totals, "--summary-json", summary_path
                )
                self.assertEqual(proc.returncode, 2)
                self.assertIn(b"--summary-json", proc.stderr)
                self.assertEqual(self.input.read_bytes(), original_input)
                self.assertFalse(output.exists())
                self.assertFalse(totals.exists())

    def test_unwritable_summary_destinations_fail_cleanly(self):
        cases = []

        missing_dir = self.directory / "missing-destination"
        cases.append(("missing-parent", missing_dir / "summary.json", "missing"))

        directory_target_parent = self.directory / "directory-target-parent"
        directory_target_parent.mkdir()
        directory_target = directory_target_parent / "summary.json"
        directory_target.mkdir()
        cases.append(("directory-target", directory_target, "directory"))

        readonly_parent = self.directory / "readonly-parent"
        readonly_parent.mkdir()
        readonly_path = readonly_parent / "summary.json"
        cases.append(("readonly-parent", readonly_path, "readonly"))

        for label, summary_path, kind in cases:
            with self.subTest(destination=label):
                work = self.directory / f"work-{label}"
                work.mkdir()
                input_path = work / "input.dat"
                input_path.write_bytes(raw() + b"\n")
                output_path = work / "results.csv"
                totals_path = work / "totals.csv"
                if kind == "readonly" and os.geteuid() == 0:
                    self.skipTest("read-only directory permission checks are ineffective as root")
                if kind == "readonly":
                    readonly_parent.chmod(0o555)
                try:
                    proc = self.cli(input_path, self.cwf, output_path, totals_path, "--summary-json", summary_path)
                finally:
                    if kind == "readonly":
                        readonly_parent.chmod(0o755)
                self.assertEqual(proc.returncode, 2)
                self.assertIn(b"discard outputs", proc.stderr)
                self.assertIn(b"summary", proc.stderr.lower())
                self.assertEqual(proc.stdout, b"")
                if kind == "directory":
                    self.assertTrue(summary_path.is_dir())
                    parent = summary_path.parent
                elif kind == "missing":
                    self.assertFalse(summary_path.exists())
                    self.assertFalse(summary_path.parent.exists())
                    continue
                else:
                    self.assertFalse(summary_path.exists())
                    parent = summary_path.parent
                self.assertFalse(any(path.name.startswith(".summary.json.") for path in parent.iterdir()))

    def test_summary_option_usage_errors(self):
        self.write_input(raw() + b"\n")
        cases = [
            ("missing-value", (self.input, self.cwf, self.results, self.totals, "--summary-json")),
            ("empty-equals", (self.input, self.cwf, self.results, self.totals, "--summary-json=")),
            ("empty-separated", (self.input, self.cwf, self.results, self.totals, "--summary-json", "")),
            ("repeated", (
                "--summary-json", self.summary, self.input, self.cwf, self.results, self.totals,
                "--summary-json=again.json",
            )),
            ("only-two-positionals", (self.input, self.cwf, self.results, "--summary-json", self.summary)),
        ]
        for label, args in cases:
            with self.subTest(error=label):
                proc = self.cli(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertIn(b"--summary-json", proc.stderr)


if __name__ == "__main__":
    unittest.main()
