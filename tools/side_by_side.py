"""Run COBOL and a candidate on the same batch; keep raw outputs; write per-record side-by-side.

    python3 tools/side_by_side.py --input build/curated.dat --name curated
    python3 tools/side_by_side.py --make-edge build/edge.dat      # deterministic adversarial batch
    python3 tools/side_by_side.py --fatal                           # fatal/usage path comparison

Added in the live migration run; does not replace tools/verify.py.
"""
import argparse
import csv
import json
import random
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/live/compare"
COBOL = "build/msp-batch"
PYTHON = "python3 python/msp.py"


def execute(command, input_path, directory, label):
    results, totals = directory / f"{label}-results.csv", directory / f"{label}-totals.csv"
    for p in (results, totals):
        p.unlink(missing_ok=True)
    done = subprocess.run(shlex.split(command) + [str(input_path), str(results), str(totals)],
                          cwd=ROOT, capture_output=True, timeout=120)
    (directory / f"{label}-exit.txt").write_text(
        f"command={command}\nexit={done.returncode}\nstdout={done.stdout!r}\nstderr={done.stderr!r}\n")
    return done, results, totals


def rows(path):
    with path.open(newline="", encoding="ascii") as handle:
        return list(csv.DictReader(handle))


def side_by_side(input_path, name, candidate):
    directory = OUT / name
    directory.mkdir(parents=True, exist_ok=True)
    left = execute(COBOL, input_path, directory, "cobol")
    right = execute(candidate, input_path, directory, "python")
    if left[0].returncode or right[0].returncode:
        sys.exit(f"{name}: exit codes cobol={left[0].returncode} python={right[0].returncode}")
    a, b = rows(left[1]), rows(right[1])
    ta, tb = rows(left[2])[0], rows(right[2])[0]
    table, mismatches = [], 0
    for i in range(max(len(a), len(b))):
        x, y = (a[i] if i < len(a) else {}), (b[i] if i < len(b) else {})
        same = x == y
        mismatches += not same
        table.append({"record_no": x.get("record_no", y.get("record_no")),
                      "cobol_id": x.get("claim_id"), "python_id": y.get("claim_id"),
                      "cobol_payment_cents": x.get("payment_cents"), "python_payment_cents": y.get("payment_cents"),
                      "cobol_status": x.get("status"), "python_status": y.get("status"),
                      "cobol_reason": x.get("reason"), "python_reason": y.get("reason"),
                      "match": "MATCH" if same else "MISMATCH"})
    totals_match = ta == tb
    bytes_identical = (left[1].read_bytes() == right[1].read_bytes()
                       and left[2].read_bytes() == right[2].read_bytes())
    with (directory / "side-by-side.csv").open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]) if table else ["record_no"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)
    summary = {"batch": name, "input": str(input_path), "input_bytes": input_path.stat().st_size,
               "records_cobol": len(a), "records_python": len(b), "record_mismatches": mismatches,
               "totals_cobol": ta, "totals_python": tb, "totals_match": totals_match,
               "output_files_byte_identical": bytes_identical, "candidate": candidate}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [f"# Side-by-side: {name}", "",
             f"Input `{input_path.relative_to(ROOT) if input_path.is_relative_to(ROOT) else input_path}`; "
             f"COBOL `{COBOL}` vs candidate `{candidate}`. Raw outputs: `cobol-*.csv`, `python-*.csv` in this directory.", "",
             "| | records | paid | zero | invalid | payment_cents |", "|---|---|---|---|---|---|",
             "| COBOL | " + " | ".join(ta[k] for k in ("records", "paid", "zero", "invalid", "payment_cents")) + " |",
             "| Python | " + " | ".join(tb[k] for k in ("records", "paid", "zero", "invalid", "payment_cents")) + " |", "",
             f"**Record mismatches: {mismatches} of {len(table)}. Totals match: {totals_match}. "
             f"Output files byte-identical: {bytes_identical}.**", "",
             "| record | COBOL ID | Python ID | COBOL cents | Python cents | COBOL status/reason | Python status/reason | result |",
             "|---|---|---|---|---|---|---|---|"]
    for r in table:
        lines.append(f"| {r['record_no']} | `{r['cobol_id']}` | `{r['python_id']}` | {r['cobol_payment_cents']} | "
                     f"{r['python_payment_cents']} | {r['cobol_status']}/{r['cobol_reason']} | "
                     f"{r['python_status']}/{r['python_reason']} | {r['match']} |")
    (directory / "side-by-side.md").write_text("\n".join(lines) + "\n")
    print(f"{name}: records={len(table)} mismatches={mismatches} totals_match={totals_match} "
          f"byte_identical={bytes_identical}")
    return mismatches == 0 and totals_match


def fixed(claim_id, c, g, p, d, k, a, f):
    a = a if isinstance(a, str) else f"{a:010d}"
    return (claim_id.ljust(12) + "".join(v if isinstance(v, str) else f"{v:010d}" for v in (c, g, p, d, k))
            + a + f).encode("latin-1")


def make_edge(path, seed=20261018, count=3000):
    """Adversarial batch: ledger records, framing oddities, maxima, and seeded byte mutations."""
    rnd = random.Random(seed)
    ledger = json.loads((ROOT / "tests_policy/expectations.json").read_text())
    sys.path.insert(0, str(ROOT / "tests_policy"))
    from msp_runner import build_record
    records = [build_record(c) for c in ledger["policy_cases"] + ledger["interface_cases"]]
    m = 9_999_999_999
    records += [b"", b"\r", b" " * 73, b"x" * 4096, fixed("EDGE-MAX", m, m, 0, 0, 0, m, "N"),
                fixed("EDGE-MAX-1", m, m, 1, 0, 0, "----------", "N"),
                fixed("EDGE-DED", m, m, 0, m, m, "----------", "N"),
                fixed("edge-lower", 1, 1, 0, 0, 0, "----------", "N"),
                "EDGE-UNI".ljust(12).encode() + "\u0661".encode() + b"0" * 61 + b"N",
                fixed("EDGE-NUL", 100, 100, 0, 0, 0, "----------", "\x00")]
    junk = list(b" +-._,0123456789AZaz@\x00\t\x7f\x80\xb2\xc1\xff")
    for n in range(count):
        c = rnd.choice([0, 1, rnd.randrange(1, 10**6), rnd.randrange(1, m + 1), m])
        g, p = rnd.randrange(0, c + 2), rnd.randrange(0, c + 2)
        d, k = rnd.randrange(0, c // 2 + 2), rnd.randrange(0, c // 4 + 2)
        a = rnd.choice(["----------", rnd.randrange(0, c + 1), c, c + 1, rnd.randrange(0, m + 1)])
        f = rnd.choice("NNNNNY")
        rec = bytearray(fixed(f"E{n:07d}", min(c, m), min(g, m), min(p, m), min(d, m), min(k, m),
                              a if isinstance(a, str) else min(a, m), f))
        roll = rnd.random()
        if roll < 0.15:
            rec[rnd.randrange(12, 73)] = rnd.choice(junk)
        elif roll < 0.18:
            rec[rnd.randrange(0, 12)] = rnd.choice(b" a.@\x00\xff")
        elif roll < 0.21:
            rec = rec[:rnd.randrange(0, 73)] if rnd.random() < 0.5 else rec + b"9" * rnd.randrange(1, 40)
        elif roll < 0.23:
            rec[72] = rnd.choice(b"yn ZX0")
        records.append(bytes(rec))
    data = bytearray()
    for i, rec in enumerate(records):
        data += rec + (b"\r\n" if i % 3 == 0 else b"\n")
    data = data[:-1] if data.endswith(b"\n") else data
    if data.endswith(b"\r"):
        data = data[:-1]
    Path(path).write_bytes(bytes(data))
    print(f"wrote {len(records)} records to {path} (last record has no final newline)")


FATAL_CASES = [
    ("no-arguments", None, []),
    ("two-arguments", None, ["IN", "OUT"]),
    ("four-arguments", None, ["IN", "OUT", "TOT", "EXTRA"]),
    ("input-equals-output", b"", ["IN", "IN", "TOT"]),
    ("output-equals-totals", b"", ["IN", "OUT", "OUT"]),
    ("missing-input", None, ["MISSING", "OUT", "TOT"]),
    ("missing-output-directory", b"", ["IN", "nodir/OUT", "TOT"]),
    ("line-4097-bytes", b"x" * 4097 + b"\n", ["IN", "OUT", "TOT"]),
    ("line-4097-bytes-no-newline", b"x" * 4097, ["IN", "OUT", "TOT"]),
    ("line-8000-bytes-after-valid", fixed("V1", 1000, 1000, 0, 0, 0, "----------", "N") + b"\n" + b"9" * 8000,
     ["IN", "OUT", "TOT"]),
    ("records-10001", b"".join(fixed(f"R{i}", 1000, 1000, 0, 0, 0, "----------", "N") + b"\n"
                               for i in range(10001)), ["IN", "OUT", "TOT"]),
    ("duplicate-valid", (fixed("DUP", 1000, 1000, 0, 0, 0, "----------", "N") + b"\n") * 2, ["IN", "OUT", "TOT"]),
    ("duplicate-rejected-bad-flag", fixed("DUP", 1000, 1000, 0, 0, 0, "----------", "Q") + b"\n"
     + fixed("DUP", 1000, 1000, 0, 0, 0, "----------", "N") + b"\n", ["IN", "OUT", "TOT"]),
    ("duplicate-rejected-bad-amount", fixed("DUP", "00000X0000", 1000, 0, 0, 0, "----------", "N") + b"\n"
     + fixed("DUP", 1000, 1000, 0, 0, 0, "----------", "N") + b"\n", ["IN", "OUT", "TOT"]),
]


def fatal(candidate):
    table, ok = [], True
    for name, data, args in FATAL_CASES:
        outcome = {}
        for label, command in (("cobol", COBOL), ("python", candidate)):
            with tempfile.TemporaryDirectory() as d:
                d = Path(d)
                if data is not None:
                    (d / "IN").write_bytes(data)
                argv = [str(d / a) for a in args]
                done = subprocess.run(shlex.split(command) + argv, cwd=ROOT, capture_output=True, timeout=120)
                totals = d / "TOT"
                outcome[label] = {"exit": done.returncode, "stdout_bytes": len(done.stdout),
                                  "stderr_nonempty": bool(done.stderr),
                                  "totals_complete": totals.exists() and totals.read_bytes().count(b"\n") == 2}
        same = (outcome["cobol"]["exit"] == outcome["python"]["exit"] == 2
                and not outcome["python"]["totals_complete"] and not outcome["cobol"]["totals_complete"]
                and outcome["cobol"]["stdout_bytes"] == outcome["python"]["stdout_bytes"] == 0)
        ok &= same
        table.append({"case": name, **{f"{l}_{k}": v for l in outcome for k, v in outcome[l].items()},
                      "match": "MATCH" if same else "MISMATCH"})
    directory = OUT / "fatal"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "fatal-paths.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)
    md = ["# Fatal and usage paths: COBOL vs Python", "",
          "MATCH = both exit 2, neither writes stdout, neither leaves a complete totals file. "
          "Partial results files are discarded by contract (README) and are not compared; "
          "stderr wording is not part of the interface and is not compared.", "",
          "| case | COBOL exit | Python exit | COBOL stderr | Python stderr | result |", "|---|---|---|---|---|---|"]
    md += [f"| {r['case']} | {r['cobol_exit']} | {r['python_exit']} | {r['cobol_stderr_nonempty']} | "
           f"{r['python_stderr_nonempty']} | {r['match']} |" for r in table]
    (directory / "fatal-paths.md").write_text("\n".join(md) + "\n")
    print(f"fatal: cases={len(table)} mismatches={sum(r['match'] != 'MATCH' for r in table)}")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--candidate", default=PYTHON)
    parser.add_argument("--make-edge", type=Path)
    parser.add_argument("--fatal", action="store_true")
    args = parser.parse_args()
    if args.make_edge:
        make_edge(args.make_edge)
        return 0
    if args.fatal:
        return 0 if fatal(args.candidate) else 1
    return 0 if side_by_side(args.input.resolve(), args.name, args.candidate) else 1


if __name__ == "__main__":
    sys.exit(main())
