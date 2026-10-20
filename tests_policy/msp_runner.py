"""Run an MSP batch program for the independent tests.

The program under test is chosen with MSP_COMMAND (tokenized with shlex, run
without a shell, four paths appended). Default: build/msp-batch.
"""
import csv
import io
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = Path(__file__).resolve().parent / "expectations.json"
RESULT_HEADER = "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"
AMOUNTS = ("charges", "gross", "primary", "deductible", "coinsurance")


def command():
    return shlex.split(os.environ.get("MSP_COMMAND", "build/msp-batch"))


def load_ledger():
    return json.loads(LEDGER.read_text())


def serialize(fields, defaults):
    """Build the 92-byte record from the README layout (independent of tools/fixtures.py)."""
    text = fields["id"].ljust(12)
    for name in AMOUNTS:
        text += f"{fields[name]:010d}"
    text += "----------" if fields["contract"] is None else f"{fields['contract']:010d}"
    text += fields["full"] + fields.get("mbi", defaults["mbi"]) + fields.get("dos", defaults["dos"])
    assert len(text) == 92, fields
    return text.encode("ascii")


def case_bytes(case, defaults):
    record = bytearray(serialize(case["fields"], defaults))
    for offset, text in case.get("patches", []):
        patch = text.encode("latin-1")
        record[offset:offset + len(patch)] = patch
    raw = case.get("raw", {})
    if "truncate_to" in raw:
        record = record[:raw["truncate_to"]]
    if "append" in raw:
        record += raw["append"].encode("latin-1")
    return bytes(record)


class Run:
    def __init__(self, completed, results_text, totals_text):
        self.returncode = completed.returncode
        self.stdout = completed.stdout
        self.stderr = completed.stderr
        self.results_text = results_text
        self.totals_text = totals_text

    def rows(self):
        lines = self.results_text.splitlines()
        assert lines and lines[0] == RESULT_HEADER, lines[:1]
        return list(csv.DictReader(io.StringIO(self.results_text)))

    def totals(self):
        lines = self.totals_text.splitlines()
        assert len(lines) == 2 and lines[0] == TOTALS_HEADER, lines
        row = next(csv.DictReader(io.StringIO(self.totals_text)))
        return {k: int(v) for k, v in row.items()}


def run_batch(input_bytes, cwf_lines=None, cwf_bytes=None, timeout=60, extra_args=None):
    """Write the input and CWF files to a temp dir and run the program under test."""
    with tempfile.TemporaryDirectory(prefix="msp-policy-") as d:
        d = Path(d)
        inp, cwf, out, tot = d / "in.dat", d / "cwf.dat", d / "results.csv", d / "totals.csv"
        if input_bytes is not None:
            inp.write_bytes(input_bytes)
        if cwf_bytes is None and cwf_lines is not None:
            cwf_bytes = "".join(line + "\n" for line in cwf_lines).encode("ascii")
        if cwf_bytes is not None:
            cwf.write_bytes(cwf_bytes)
        args = [str(inp), str(cwf), str(out), str(tot)] if extra_args is None else extra_args(d)
        completed = subprocess.run(command() + args, cwd=ROOT, capture_output=True, timeout=timeout)
        read = lambda p: p.read_text(encoding="ascii") if p.exists() else ""
        return Run(completed, read(out), read(tot))
