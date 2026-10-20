"""Stage 2 harness: builds batches from the hand-derived ledger and runs MSP_COMMAND.

No payment arithmetic lives here. The program under test is chosen with the
MSP_COMMAND environment variable (shlex-split); default build/msp-batch.
"""
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((Path(__file__).with_name("expectations.json")).read_text())
RESULT_HEADER = "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"


def command():
    return shlex.split(os.environ.get("MSP_COMMAND", str(ROOT / "build/msp-batch")))


def claim_line(case):
    if "raw_line" in case:
        return case["raw_line"]
    fields = dict(LEDGER["defaults"], **case["input"])
    layout = LEDGER["field_layout"]
    if len(case["id"]) > 12:
        raise ValueError(f"{case['id']}: ID longer than 12")
    parts = {"id": case["id"].ljust(12)}
    for name in ("charges", "gross", "primary", "deductible", "coinsurance"):
        parts[name] = f"{fields[name]:010d}"
    parts["contract"] = "-" * 10 if fields["contract"] is None else f"{fields['contract']:010d}"
    parts["full"], parts["mbi"], parts["dos"] = fields["full"], fields["mbi"], fields["dos"]
    for name, value in case.get("patch", {}).items():
        if len(value) != layout[name][1]:
            raise ValueError(f"{case['id']}: patch {name} must be {layout[name][1]} bytes")
        parts[name] = value
    line = "".join(parts[name] for name in layout)
    for name, (start, width) in layout.items():
        assert len(parts[name]) == width and line[start:start + width] == parts[name], (case["id"], name)
    frame = case.get("frame", {})
    if "truncate" in frame:
        line = line[:frame["truncate"]]
    return line + frame.get("append", "")


def cwf_lines(reference):
    lines = []
    for b in reference["beneficiaries"]:
        msp = (b["msp_from"] + b["msp_to"]) if b["msp_from"] else "-" * 16
        lines.append("B" + b["mbi"] + b["entitled_from"] + b["entitled_to"] + msp)
    for h in reference["history"]:
        lines.append("H" + h["mbi"] + h["dos"] + f"{h['charges']:010d}")
    return lines


class Run:
    def __init__(self, returncode, stdout, stderr, results, totals):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr
        self.results, self.totals = results, totals


def run_batch(data, cwf=None, extra_args=None, directory=None, timeout=120):
    """Write INPUT bytes and CWF bytes, run the program, return raw outputs."""
    own = directory is None
    temp = tempfile.TemporaryDirectory(prefix="msp-policy-") if own else None
    d = Path(temp.name if own else directory)
    try:
        inp, cwf_path, out, tot = d / "input.dat", d / "cwf.dat", d / "results.csv", d / "totals.csv"
        inp.write_bytes(data)
        if cwf is None:
            cwf = ("\n".join(cwf_lines(LEDGER["cwf_reference"])) + "\n").encode("ascii")
        cwf_path.write_bytes(cwf)
        args = extra_args if extra_args is not None else [str(inp), str(cwf_path), str(out), str(tot)]
        done = subprocess.run(command() + args, capture_output=True, timeout=timeout, cwd=ROOT)
        results = out.read_bytes() if out.exists() else None
        totals = tot.read_bytes() if tot.exists() else None
        return Run(done.returncode, done.stdout, done.stderr, results, totals)
    finally:
        if own:
            temp.cleanup()


def parse(run):
    rows = run.results.decode("ascii").split("\n")
    assert rows[-1] == "", "results must end with LF"
    totals = run.totals.decode("ascii").split("\n")
    assert totals[-1] == "" and len(totals) == 3, "totals must be header + one row + LF"
    return rows[0], [r.split(",") for r in rows[1:-1]], totals[0], totals[1].split(",")
