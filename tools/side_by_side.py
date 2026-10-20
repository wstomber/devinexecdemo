#!/usr/bin/env python3
"""Run COBOL and Python on the same batches; write per-record side-by-side evidence.

Batches: curated (build/curated.dat), synthetic (build/synthetic.dat), and a
seeded adversarial edge batch generated here. Also compares fatal paths.
Raw outputs of both programs are kept. Run `make build generate` first.

    python3 tools/side_by_side.py --out evidence/live/comparison
"""
import argparse
import csv
import io
import json
import random
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents"]
TOTAL_FIELDS = ["records", "paid", "zero", "invalid", "payment_cents", "accepted", "rejected", "released_cents"]


def run(command, inp, cwf, out, tot, args=None):
    argv = shlex.split(command) + ([str(inp), str(cwf), str(out), str(tot)] if args is None else args)
    return subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=300)


def rows(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="ascii"))))


# ---------------------------------------------------------------- edge batch
def edge_batch(seed=20261020, count=3000):
    """Adversarial records: boundary amounts, mutated bytes, odd framing.
    Base IDs are unique and mutations only make an ID invalid, so the batch
    has no duplicate identifiable IDs (that path is tested under fatal)."""
    rng = random.Random(seed)
    ledger = json.loads((ROOT / "tests_policy/expectations.json").read_text())
    cwf = list(ledger["cwf_reference"]["lines"])
    cwf_bytes = "\n".join(cwf).encode("ascii") + b"\n"
    # CWF quirks preserved from GnuCOBOL LINE SEQUENTIAL reading.
    quirks = [
        b"B7EDGECR\r0001" + b"2025010120251231" + b"-" * 16 + b"\r\n",                # CR mid-record dropped
        b"B7EDGELONG01" + b"2025010120251231" + b"-" * 16 + b" " * 20 + b"IGNORED-AFTER-COL-64\n",
        b"B7EDGELONG01" + b"2030010120301231" + b"-" * 16 + b"\n",                     # second B, same MBI: ignored
        b"H7EDGELONG01" + b"20250601" + b"0000100000" + b"     \n",                    # trailing spaces
        b"B7EDGE\x00NULL1" + b"2025010120251231" + b"-" * 16,                          # NUL is data; no final LF
    ]
    for q in quirks:
        body = q.replace(b"\r", b"").rstrip(b"\n")
        assert len(body[:64].rstrip(b" ")) in (30, 44), q
    cwf_bytes += b"".join(quirks)
    mbis = ["7POLICY0001", "7MSPEGHP001", "7ENTWIN0001", "7HISTORY001", "7ALLFAIL001", "7EDGECR0001",
            "7EDGELONG01", "7EDGE\x00NULL1", "7NOTONFILE1"]
    assert all(len(m) == 11 for m in mbis)
    dates = ["20240101", "20250101", "20250201", "20250228", "20250301", "20250315", "20250331", "20250415",
             "20250430", "20250501", "20250601", "20250610", "20250630", "20251231", "20991231", "20250231"]
    amounts = [0, 1, 2, 99, 100, 9999, 10000, 50000, 99999, 100000, 155600, 1250000, 1300000, 1400000, 1500000,
               9_999_999_998, 9_999_999_999]
    junk = [b"a", b"z", b"@", b"*", b"+", b"-", b"_", b" ", b"\x00", b"\xff", b"\t", b"\r", b"\x0c", b".", b"9", b"A"]
    out = []
    for i in range(count):
        cid = f"E{i:05d}"
        if i % 50 == 0 and i:
            out.append(b"" if i % 100 else b"X" * 4096)   # blank or maximum-length line
            continue
        if rng.random() < 0.35:   # payable shape, aimed at the CWF history records
            c = 100000
            vals = [c, rng.choice([80000, 100000]), rng.choice([0, 0, 20000, 79999, 80000]),
                    rng.choice([0, 10000]), rng.choice([0, 5000])]
        else:
            c = rng.choice(amounts)
            vals = [c] + [rng.choice(amounts + [c, c - 1 if c else 0]) for _ in range(4)]
        contract = None if rng.random() < 0.5 else rng.choice([c, max(c - 1, 0), c + 1, rng.choice(amounts)])
        full = rng.choice("NNNNNY")
        mbi = rng.choice(mbis)
        dos = rng.choice(dates + ["20250610", "20250611", "20250415", "20250315", "20250601"])
        rec = bytearray(cid.ljust(12).encode("latin-1"))
        rec += b"".join(f"{v:010d}".encode() for v in vals)
        rec += b"----------" if contract is None or contract > 9_999_999_999 else f"{contract:010d}".encode()
        rec += full.encode() + mbi.encode("latin-1") + dos.encode()
        r = rng.random()
        if r < 0.25:
            pos = rng.randrange(92)
            ch = rng.choice(junk)
            if pos < 12 and ch in (b"A", b"9", b"-", b"_"):
                ch = b"a"
            rec[pos:pos + 1] = ch
        elif r < 0.30:
            rec = rec[:rng.choice([0, 1, 12, 91])] if rng.random() < 0.5 else rec + rng.choice(junk) * rng.randint(1, 5)
        elif r < 0.33:
            rec[62:72] = rng.choice([b"0000000-01", b"         1", b"+000000001", b"----------"[:9] + b"0"])
        elif r < 0.36:
            rec[84:92] = rng.choice([b"20251301", b"20250001", b"20250100", b"20250132", b"2025-6-1", b"        "])
        elif r < 0.39:
            rec[73:84] = rng.choice([b"7policy0001", b"7POLICY 001", b"           ", b"7POLICY-001"])
        out.append(bytes(rec))
    endings = [b"\n", b"\n", b"\n", b"\r\n"]
    data = b"".join(line + rng.choice(endings) for line in out[:-1]) + out[-1]   # last line: no LF
    return data, cwf_bytes


# ---------------------------------------------------------------- per-record report
def compare_batch(name, inp_bytes, cwf_bytes, out_dir, cobol, python):
    d = out_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "input.dat").write_bytes(inp_bytes)
    (d / "cwf.dat").write_bytes(cwf_bytes)
    procs = {}
    for label, cmd in (("cobol", cobol), ("python", python)):
        p = run(cmd, d / "input.dat", d / "cwf.dat", d / f"{label}-results.csv", d / f"{label}-totals.csv")
        (d / f"{label}-stderr.txt").write_bytes(p.stderr)
        procs[label] = p
        if p.returncode != 0:
            raise SystemExit(f"{name}: {label} exited {p.returncode}: {p.stderr[:300]!r}")
    a, b = rows(d / "cobol-results.csv"), rows(d / "python-results.csv")
    ta, tb = rows(d / "cobol-totals.csv")[0], rows(d / "python-totals.csv")[0]
    header = ["record_no", "cobol_claim_id", "python_claim_id"]
    for f in FIELDS:
        header += [f"cobol_{f}", f"python_{f}"]
    header.append("result")
    table, mismatches = [], 0
    for i in range(max(len(a), len(b))):
        ra, rb = (a[i] if i < len(a) else {}), (b[i] if i < len(b) else {})
        row = [ra.get("record_no") or rb.get("record_no"), ra.get("claim_id", ""), rb.get("claim_id", "")]
        for f in FIELDS:
            row += [ra.get(f, ""), rb.get(f, "")]
        same = ra == rb
        mismatches += not same
        row.append("MATCH" if same else "MISMATCH")
        table.append(row)
    with open(d / "side-by-side.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(table)
    raw_identical = all((d / f"cobol-{k}.csv").read_bytes() == (d / f"python-{k}.csv").read_bytes()
                        for k in ("results", "totals"))
    summary = {"batch": name, "records_cobol": len(a), "records_python": len(b), "match": len(table) - mismatches,
               "mismatch": mismatches, "totals_match": ta == tb, "byte_identical_outputs": raw_identical,
               "totals_cobol": ta, "totals_python": tb}
    md = [f"# Side-by-side: {name}", "",
          f"COBOL `{cobol}` vs Python `{python}`. Input `input.dat`, CWF `cwf.dat` in this folder.", "",
          "| | COBOL | Python |", "|---|---|---|",
          f"| records | {len(a)} | {len(b)} |"]
    md += [f"| total {k} | {ta[k]} | {tb[k]} |" for k in TOTAL_FIELDS]
    md += ["", f"**{summary['match']} MATCH, {mismatches} MISMATCH; totals "
           f"{'MATCH' if ta == tb else 'MISMATCH'}; result and totals files byte-identical: {raw_identical}.**", "",
           "| rec | COBOL id | Python id | COBOL status | Py status | COBOL pay | Py pay | COBOL reason | Py reason "
           "| COBOL CWF | Py CWF | COBOL CWF reason | Py CWF reason | COBOL released | Py released | result |",
           "|" + "---|" * 16]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in table]
    (d / "side-by-side.md").write_text("\n".join(md) + "\n")
    return summary


# ---------------------------------------------------------------- fatal paths
def fatal_cases():
    ok_cwf = b"B7POLICY00012024010199999999----------------\n"
    def rec(i):
        amounts = b"".join(f"{v:010d}".encode() for v in (100000, 80000, 20000, 10000, 0))
        line = f"F{i:05d}".ljust(12).encode() + amounts + b"----------N7POLICY000120250601"
        assert len(line) == 92
        return line
    good = rec(0) + b"\n"
    many = b"".join(rec(i) + b"\n" for i in range(10000))
    yield "usage-0-args", None, None, lambda d: []
    yield "usage-3-args", good, ok_cwf, lambda d: [str(d / "in.dat"), str(d / "cwf.dat"), str(d / "r.csv")]
    yield "usage-5-args", good, ok_cwf, lambda d: [str(d / x) for x in ("in.dat", "cwf.dat", "r.csv", "t.csv", "x")]
    yield "same-input-and-results", good, ok_cwf, lambda d: [str(d / x) for x in ("in.dat", "cwf.dat", "in.dat", "t.csv")]
    yield "same-cwf-and-totals", good, ok_cwf, lambda d: [str(d / x) for x in ("in.dat", "cwf.dat", "r.csv", "cwf.dat")]
    yield "missing-input", None, ok_cwf, None
    yield "missing-cwf", good, None, None
    yield "results-dir-missing", good, ok_cwf, lambda d: [str(d / "in.dat"), str(d / "cwf.dat"), str(d / "no/r.csv"), str(d / "t.csv")]
    yield "cwf-blank-line", good, ok_cwf + b"\n", None
    yield "cwf-unknown-type", good, ok_cwf + b"X7POLICY00012024010199999999\n", None
    yield "cwf-B-bad-dates", good, b"B7POLICY0001202401019999999X----------------\n", None
    yield "cwf-B-bad-msp", good, b"B7POLICY00012024010199999999--------20251231\n", None
    yield "cwf-B-col45", good, b"B7POLICY00012024010199999999----------------X\n", None
    yield "cwf-H-bad-charges", good, ok_cwf + b"H7POLICY000120250601000010000X\n", None
    yield "cwf-1001-B", good, b"".join(f"B{i:011d}2024010199999999----------------\n".encode() for i in range(1001)), None
    yield "line-4097", good + b"X" * 4097 + b"\n", ok_cwf, None
    yield "line-4098-no-lf", good + b"X" * 4098, ok_cwf, None
    yield "records-10001", many + good.replace(b"F00000", b"F99999"), ok_cwf, None
    yield "records-10001-blank", many + b"\n", ok_cwf, None
    yield "duplicate-valid-id", good + good, ok_cwf, None
    yield "duplicate-rejected-id", good + good[:72] + b"X" + good[73:], ok_cwf, None


def compare_fatal(out_dir, cobol, python):
    d = out_dir / "fatal"
    d.mkdir(parents=True, exist_ok=True)
    table = []
    for name, inp, cwf, args in fatal_cases():
        result = {}
        for label, cmd in (("cobol", cobol), ("python", python)):
            with tempfile.TemporaryDirectory() as t:
                t = Path(t)
                if inp is not None:
                    (t / "in.dat").write_bytes(inp)
                if cwf is not None:
                    (t / "cwf.dat").write_bytes(cwf)
                p = run(cmd, t / "in.dat", t / "cwf.dat", t / "r.csv", t / "t.csv", None if args is None else args(t))
            err = p.stderr.decode("latin-1").replace(str(t), "<tmp>")
            (d / f"{name}.{label}.stderr.txt").write_text(err)
            first = err.splitlines()[0] if err else ""
            # The COBOL appends its file-status codes to the generic fatal line; Python has none.
            result[label] = (p.returncode, len(p.stdout), first.split("; file status")[0])
        (ca, sa, ea), (cb, sb, eb) = result["cobol"], result["python"]
        same = ca == cb == 2 and sa == sb == 0 and ea == eb
        table.append([name, ca, cb, sa, sb, ea, eb, "MATCH" if same else "MISMATCH"])
    header = ["case", "cobol_exit", "python_exit", "cobol_stdout_bytes", "python_stdout_bytes",
              "cobol_stderr_first_line", "python_stderr_first_line", "result"]
    with open(d / "fatal-paths.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(table)
    md = ["# Fatal-path comparison", "",
          "MATCH = both exit 2, nothing on stdout, same first stderr line (COBOL's `; file status ii/oo/tt` suffix "
          "on the generic fatal line is not compared). Later stderr lines differ by design: "
          "COBOL prints its file-status codes and libcob implicit-CLOSE warnings, Python prints "
          "`fatal batch failure; discard outputs`. Full stderr of both is kept beside this file.", "",
          "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(f"`{c}`" if i >= 5 and i < 7 else str(c) for i, c in enumerate(r)) + " |" for r in table]
    mism = sum(r[-1] != "MATCH" for r in table)
    md += ["", f"**{len(table) - mism} MATCH, {mism} MISMATCH.**"]
    (d / "fatal-paths.md").write_text("\n".join(md) + "\n")
    return {"batch": "fatal", "cases": len(table), "match": len(table) - mism, "mismatch": mism}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/live/comparison")
    ap.add_argument("--cobol", default="build/msp-batch")
    ap.add_argument("--python", default="python3 python/msp.py")
    args = ap.parse_args()
    out = ROOT / args.out
    cwf = (ROOT / "build/cwf.dat").read_bytes()
    summaries = [
        compare_batch("curated", (ROOT / "build/curated.dat").read_bytes(), cwf, out, args.cobol, args.python),
        compare_batch("synthetic", (ROOT / "build/synthetic.dat").read_bytes(), cwf, out, args.cobol, args.python),
        compare_batch("edge", *edge_batch(), out, args.cobol, args.python),
        compare_fatal(out, args.cobol, args.python),
    ]
    (out / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    for s in summaries:
        print(json.dumps({k: v for k, v in s.items() if not k.startswith("totals_") or k == "totals_match"}))
    if any(s["mismatch"] for s in summaries) or not all(s.get("totals_match", True) for s in summaries):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
