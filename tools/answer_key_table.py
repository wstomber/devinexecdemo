"""Print the 72-case answer key next to what COBOL and Python actually output, one line per case.

Runs each program on the ledger in tests_policy/expectations.json and compares every output field.
    python3 tools/answer_key_table.py
Exits 1 if any case differs. tests_policy is the authoritative test; this is the readable view.
"""
import csv
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from fixtures import case_record, serialize_cwf  # noqa: E402

LEDGER = json.loads((ROOT / "tests_policy/expectations.json").read_text())
PROGRAMS = {"COBOL": [str(ROOT / "build/msp-batch")], "Python": shlex.split("python3 python/msp.py")}
FIELDS = ["status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents"]


def run(command, directory):
    d = Path(directory)
    (d / "input.dat").write_text("".join(case_record(c) + "\n" for c in LEDGER["cases"]))
    (d / "cwf.dat").write_text("".join(line + "\n" for line in serialize_cwf(LEDGER["cwf_reference"])))
    subprocess.run(command + [str(d / n) for n in ("input.dat", "cwf.dat", "results.csv", "totals.csv")],
                   cwd=ROOT, check=True, capture_output=True, timeout=60)
    with (d / "results.csv").open(newline="") as stream:
        return {int(r["record_no"]): {k: (int(r[k]) if k.endswith("_cents") else r[k]) for k in FIELDS}
                for r in csv.DictReader(stream)}


def short(row):
    return f"{row['status']:<7} ${row['payment_cents'] / 100:>9,.2f} {row['cwf']:<8} ${row['released_cents'] / 100:>9,.2f}"


def main():
    outputs = {}
    for name, command in PROGRAMS.items():
        with tempfile.TemporaryDirectory() as directory:
            outputs[name] = run(command, directory)
    print(f"{'#':>2}  {'claim':<16} {'answer key: status / paid / CWF / released':<44} COBOL   Python")
    matched = 0
    for case in LEDGER["cases"]:
        expected = {k: case["expected"][k] for k in FIELDS}
        marks = ["match" if outputs[n].get(case["record_no"]) == expected else "DIFF" for n in PROGRAMS]
        matched += marks == ["match", "match"]
        print(f"{case['record_no']:>2}  {case['claim_id']:<16} {short(expected):<44} {marks[0]:<7} {marks[1]}")
    total = len(LEDGER["cases"])
    print(f"\n{matched} / {total} hand-worked cases: COBOL and Python both match the answer key on every field")
    return 0 if matched == total else 1


if __name__ == "__main__":
    sys.exit(main())
