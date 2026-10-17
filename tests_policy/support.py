"""Program-agnostic helpers for the independent policy tests.

The program under test is selected with MSP_COMMAND (default build/msp-batch).
It is tokenized with shlex and receives INPUT OUTPUT TOTALS appended.
"""
import csv
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = json.loads((Path(__file__).resolve().parent / "expectations.json").read_text())
FIELDS = ("charges", "gross", "primary", "deductible", "coinsurance", "contract", "full")
ABSENT = b"----------"


def command():
    return shlex.split(os.environ.get("MSP_COMMAND", "build/msp-batch"))


def record(claim_id, charges, gross, primary, deductible, coinsurance, contract, full):
    """Build one 73-byte record from integer cents; contract None means absent."""
    raw = {"id": claim_id.encode("ascii").ljust(12, b" ")}
    for name, value in zip(FIELDS[:5], (charges, gross, primary, deductible, coinsurance)):
        raw[name] = b"%010d" % value
    raw["contract"] = ABSENT if contract is None else b"%010d" % contract
    raw["full"] = full.encode("ascii")
    return assemble(raw)


def assemble(raw):
    line = raw["id"] + b"".join(raw[name] for name in FIELDS)
    assert len(line) == 73, (len(line), line)
    return line


def case_line(case):
    """Serialize a ledger case into one physical line (no terminator)."""
    frame = case.get("frame", {})
    if frame.get("blank"):
        return b""
    inputs = LEDGER["base_valid_record"]["in"] if case.get("base") else case["in"]
    line = record(case["id"], *inputs)
    raw = {"id": line[:12]}
    offset = 12
    for name in FIELDS:
        width = 1 if name == "full" else 10
        raw[name] = line[offset:offset + width]
        offset += width
    for name, text in case.get("raw", {}).items():
        value = text.encode("utf-8")
        raw[name] = value.ljust(12, b" ") if name == "id" else value
    for name, hexed in case.get("raw_bytes", {}).items():
        raw[name] = bytes.fromhex(hexed)
    line = assemble(raw)
    if "truncate" in frame:
        line = line[:frame["truncate"]]
    if "append" in frame:
        line = line + frame["append"].encode("ascii")
    return line


def run(data, extra_args=None):
    """Run the program on input bytes. Returns (exit, results rows, totals row, stderr)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        paths = [tmp / "input.dat", tmp / "results.csv", tmp / "totals.csv"]
        paths[0].write_bytes(data)
        args = [str(p) for p in paths] if extra_args is None else extra_args(tmp, paths)
        proc = subprocess.run(command() + args, cwd=ROOT, capture_output=True, timeout=120)
        rows = totals = None
        if proc.returncode == 0:
            with open(paths[1], newline="") as handle:
                rows = list(csv.reader(handle))
            with open(paths[2], newline="") as handle:
                totals = list(csv.reader(handle))
        return proc.returncode, rows, totals, proc.stderr.decode(errors="replace")
