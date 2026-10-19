"""Shared helpers for the Stage 2 independent tests. No payment logic lives here."""
import csv
import io
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
RESULT_HEADER = ["record_no", "claim_id", "status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents"]
TOTAL_HEADER = ["records", "paid", "zero", "invalid", "payment_cents", "accepted", "rejected", "released_cents"]
FIELD_ORDER = (("id", 12), ("C", 10), ("G", 10), ("P", 10), ("D", 10), ("K", 10), ("A", 10),
               ("full", 1), ("mbi", 11), ("dos", 8))
DIGITS = re.compile(r"[0-9]+\Z")


def command():
    """Program under test: MSP_COMMAND (shlex-split), default build/msp-batch."""
    value = os.environ.get("MSP_COMMAND", str(ROOT / "build/msp-batch"))
    return shlex.split(value)


def load_ledger():
    return json.loads((HERE / "expectations.json").read_text())


def serialize_cwf(reference):
    lines = []
    for b in reference["beneficiaries"]:
        msp = (b["msp_from"] + b["msp_to"]) if b["msp_from"] else "-" * 16
        lines.append("B" + b["mbi"] + b["entitled_from"] + b["entitled_to"] + msp)
    for h in reference["history"]:
        lines.append("H" + h["mbi"] + h["dos"] + f"{h['charges']:010d}")
    return "".join(line + "\n" for line in lines)


def ledger_cwf():
    return serialize_cwf(json.loads((HERE / "cwf_reference.json").read_text()))


def record(case, defaults):
    """Build one physical line (without newline) from a ledger case."""
    if "line" in case:
        return case["line"]
    values = dict(defaults, id=case["id"])
    values.update(case.get("in", {}))
    raw = case.get("raw", {})
    parts = []
    for name, width in FIELD_ORDER:
        if name in raw:
            text = raw[name]
        elif name == "id":
            text = values["id"].ljust(12)
        elif name == "A" and values["A"] is None:
            text = "-" * 10
        elif name in ("full", "mbi", "dos"):
            text = values[name]
        else:
            text = f"{values[name]:010d}"
        if len(text) != width:
            raise ValueError(f"{case['id']}: field {name} must be {width} bytes, got {text!r}")
        parts.append(text)
    line = "".join(parts)
    if "line_trim" in case:
        line = line[:-case["line_trim"]]
    return line + case.get("line_append", "")


def run(input_bytes, cwf_text, extra_args=None):
    """Run the program; return (exit, rows, totals, stdout, stderr)."""
    with tempfile.TemporaryDirectory(prefix="msp-policy-") as directory:
        d = Path(directory)
        (d / "in.dat").write_bytes(input_bytes)
        (d / "cwf.dat").write_bytes(cwf_text.encode("ascii") if isinstance(cwf_text, str) else cwf_text)
        args = extra_args if extra_args is not None else [d / "in.dat", d / "cwf.dat", d / "out.csv", d / "tot.csv"]
        done = subprocess.run(command() + [str(a) for a in args], capture_output=True, timeout=60, cwd=d)
        rows = totals = None
        if done.returncode == 0:
            rows = parse(d / "out.csv", RESULT_HEADER)
            total_rows = parse(d / "tot.csv", TOTAL_HEADER)
            assert len(total_rows) == 1, "totals must have one data row"
            totals = total_rows[0]
        return done.returncode, rows, totals, done.stdout, done.stderr


def parse(path, header):
    text = path.read_bytes().decode("ascii")
    reader = csv.reader(io.StringIO(text))
    lines = list(reader)
    assert lines[0] == header, f"{path.name} header {lines[0]}"
    out = []
    for values in lines[1:]:
        row = dict(zip(header, values))
        assert len(values) == len(header)
        for key in row:
            if key in ("record_no", "payment_cents", "released_cents") or header is TOTAL_HEADER:
                assert DIGITS.match(row[key]), f"{key}={row[key]!r} is not unsigned digits"
                row[key] = int(row[key])
        out.append(row)
    return out
