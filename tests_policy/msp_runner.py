"""Shared helpers for the independent tests: build records, run MSP_COMMAND, parse CSV.

No payment logic lives here. Expected values come from expectations.json or from
literal values in the test files, worked by hand from docs/rules.md and README.md.
"""
import csv
import io
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((Path(__file__).with_name("expectations.json")).read_text())
AMOUNT_FIELDS = ("charges", "gross", "primary", "deductible", "coinsurance", "contract")
RESULT_HEADER = ["record_no", "claim_id", "status", "payment_cents", "reason"]
TOTALS_HEADER = ["records", "paid", "zero", "invalid", "payment_cents"]


def command():
    return shlex.split(os.environ.get("MSP_COMMAND", "build/msp-batch"))


def build_record(spec):
    """Return record bytes for a ledger entry ({'input': ...} or {'raw_record': ...})."""
    if "raw_record" in spec:
        return spec["raw_record"].encode("ascii")
    claim = spec["input"]
    parts = [claim["id"].ljust(12)]
    for field in AMOUNT_FIELDS:
        value = claim[field]
        if value is None and field == "contract":
            parts.append("-" * 10)
        elif isinstance(value, str):
            parts.append(value)
        else:
            parts.append(f"{value:010d}")
    parts.append(claim["full"])
    record = "".join(parts).encode("ascii")
    if len(record) != 73:
        raise ValueError(f"ledger record is {len(record)} bytes, expected 73: {claim}")
    return record


def amount(text):
    if not text or any(c not in "0123456789" for c in text):
        raise AssertionError(f"not an unsigned digit string: {text!r}")
    return int(text)


class Run:
    def __init__(self, completed, results_text, totals_text):
        self.returncode = completed.returncode
        self.stderr = completed.stderr.decode(errors="replace")
        self.results_text, self.totals_text = results_text, totals_text

    def rows(self):
        reader = csv.reader(io.StringIO(self.results_text))
        header = next(reader)
        assert header == RESULT_HEADER, header
        return [{"record_no": amount(r[0]), "claim_id": r[1], "status": r[2],
                 "payment_cents": amount(r[3]), "reason": r[4]} for r in reader]

    def totals(self):
        lines = self.totals_text.splitlines()
        assert lines[0].split(",") == TOTALS_HEADER, lines
        assert len(lines) == 2, lines
        return dict(zip(TOTALS_HEADER, (amount(v) for v in lines[1].split(","))))


def run_batch(data, extra_args=None, timeout=60):
    """Run the configured program on raw input bytes; return a Run."""
    with tempfile.TemporaryDirectory(prefix="msp-policy-") as directory:
        d = Path(directory)
        source, results, totals = d / "input.dat", d / "results.csv", d / "totals.csv"
        source.write_bytes(data)
        args = extra_args if extra_args is not None else [str(source), str(results), str(totals)]
        completed = subprocess.run(command() + args, cwd=ROOT, capture_output=True, timeout=timeout)
        read = lambda p: p.read_text(encoding="ascii") if p.exists() else None
        return Run(completed, read(results), read(totals))


def batch_bytes(specs, newline=b"\n"):
    return b"".join(build_record(s) + newline for s in specs)
