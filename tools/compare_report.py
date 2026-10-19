"""Run COBOL and Python on identical batches, keep both raw outputs, and build a
per-record side-by-side report (CSV + Markdown). Strict checks stay in tools/verify.py;
this adds the visible table, raw byte comparison, an adversarial edge batch and fatal-path parity."""
import argparse
import csv
import hashlib
import io
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests_policy"))
from common import ledger_cwf, load_ledger, record  # noqa: E402

FIELDS = ["claim_id", "status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents"]


def execute(command, input_path, cwf_path, out_dir, label):
    results, totals = out_dir / f"{label}-results.csv", out_dir / f"{label}-totals.csv"
    done = subprocess.run(shlex.split(command) + [str(input_path), str(cwf_path), str(results), str(totals)],
                          capture_output=True, timeout=120)
    return done.returncode, results, totals, done.stderr.decode(errors="replace")


def rows(path):
    return {int(r["record_no"]): r for r in csv.DictReader(io.StringIO(path.read_text()))}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def side_by_side(name, input_path, cwf_path, out_dir, cobol, python):
    out_dir.mkdir(parents=True, exist_ok=True)
    c_code, c_res, c_tot, c_err = execute(cobol, input_path, cwf_path, out_dir, "cobol")
    p_code, p_res, p_tot, p_err = execute(python, input_path, cwf_path, out_dir, "python")
    if c_code or p_code:
        raise SystemExit(f"{name}: exit cobol={c_code} python={p_code}\n{c_err}\n{p_err}")
    cobol_rows, python_rows = rows(c_res), rows(p_res)
    table, mismatches = [], 0
    for n in sorted(set(cobol_rows) | set(python_rows)):
        c, p = cobol_rows.get(n, {}), python_rows.get(n, {})
        same = all(c.get(f) == p.get(f) for f in FIELDS) and bool(c) and bool(p)
        mismatches += not same
        table.append({"record_no": n, "claim_id": c.get("claim_id") or p.get("claim_id"),
                      "cobol_payment_cents": c.get("payment_cents"), "python_payment_cents": p.get("payment_cents"),
                      "cobol_status": c.get("status"), "python_status": p.get("status"),
                      "cobol_reason": c.get("reason"), "python_reason": p.get("reason"),
                      "cobol_cwf": c.get("cwf"), "python_cwf": p.get("cwf"),
                      "cobol_cwf_reason": c.get("cwf_reason"), "python_cwf_reason": p.get("cwf_reason"),
                      "cobol_released_cents": c.get("released_cents"), "python_released_cents": p.get("released_cents"),
                      "match": "MATCH" if same else "MISMATCH"})
    c_totals = next(csv.DictReader(io.StringIO(c_tot.read_text())))
    p_totals = next(csv.DictReader(io.StringIO(p_tot.read_text())))
    summary = {"batch": name, "input": str(input_path.relative_to(ROOT)), "input_sha256": digest(input_path),
               "cwf": str(cwf_path.relative_to(ROOT)), "records": len(table), "mismatches": mismatches,
               "results_bytes_identical": c_res.read_bytes() == p_res.read_bytes(),
               "totals_bytes_identical": c_tot.read_bytes() == p_tot.read_bytes(),
               "cobol_results_sha256": digest(c_res), "python_results_sha256": digest(p_res),
               "cobol_totals": c_totals, "python_totals": p_totals, "totals_match": c_totals == p_totals}
    with (out_dir / "side-by-side.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]) if table else ["record_no"])
        writer.writeheader()
        writer.writerows(table)
    lines = [f"# Side-by-side: {name}", "",
             f"Input `{summary['input']}` (sha256 `{summary['input_sha256'][:16]}…`), CWF `{summary['cwf']}`.",
             f"Records **{len(table)}**, mismatches **{mismatches}**; results CSV byte-identical: "
             f"**{summary['results_bytes_identical']}**; totals CSV byte-identical: **{summary['totals_bytes_identical']}**.", "",
             "| Totals | " + " | ".join(c_totals) + " |", "| --- |" + " ---: |" * len(c_totals),
             "| COBOL | " + " | ".join(str(int(v)) for v in c_totals.values()) + " |",
             "| Python | " + " | ".join(str(int(v)) for v in p_totals.values()) + " |", "",
             "| # | Claim ID | COBOL payment | Python payment | COBOL status/reason | Python status/reason "
             "| COBOL CWF | Python CWF | COBOL released | Python released | Result |",
             "| ---: | --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- |"]
    for r in table:
        lines.append(f"| {r['record_no']} | {r['claim_id']} | {int(r['cobol_payment_cents'] or 0)} | "
                     f"{int(r['python_payment_cents'] or 0)} | {r['cobol_status']}/{r['cobol_reason']} | "
                     f"{r['python_status']}/{r['python_reason']} | {r['cobol_cwf']}/{r['cobol_cwf_reason']} | "
                     f"{r['python_cwf']}/{r['python_cwf_reason']} | {int(r['cobol_released_cents'] or 0)} | "
                     f"{int(r['python_released_cents'] or 0)} | {r['match']} |")
    (out_dir / "side-by-side.md").write_text("\n".join(lines) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def edge_batch(path):
    """Adversarial records: the Stage 2 ledger plus framing/byte-level oddities."""
    ledger = load_ledger()
    lines = [record(c, ledger["defaults"]).encode() for c in ledger["cases"]]
    base = record({"id": "EDGE", "in": {"C": 100000, "G": 90000, "P": 1000, "D": 500, "K": 0}}, ledger["defaults"]).encode()

    def named(tag, raw):
        return tag.encode().ljust(12) + raw[12:]
    extra = [
        b"", b"\r", b" " * 92, b"\t" * 92, b"\x00" * 92, b"X" * 4096, b"Y" * 4095 + b"\r",
        named("E-TAB", base[:22] + b"\t" + base[23:]), named("E-NUL", base[:22] + b"\x00" + base[23:]),
        named("E-ARABIC", base[:12] + "٠".encode() * 5 + base[22:]),  # 10 bytes of Arabic-Indic zero
        named("E-FULLWIDTH", base[:12] + "０".encode() * 3 + b"0" + base[22:]),
        named("E-SUPERSCR", base[:12] + "²".encode() * 5 + base[22:]),
        named("E-HIGHBIT", base[:72] + b"\xd9" + base[73:]),
        named("E-CR-MID", base[:40] + b"\r" + base[41:]),
        named("E-LOWER-N", base[:72] + b"n" + base[73:]),
        named("E-MBI-UTF", base[:73] + "É".encode() + base[75:]),
        named("E-DOS-SPACE", base[:84] + b"2024 615"),
        named("E-DOS-0000", base[:84] + b"00000101"),
        named("E-FEB30", base[:84] + b"20240230"),
        named("E-DASHES-9", base[:62] + b"-" * 9 + b" " + base[72:]),
        b"E_UNDER_SC-1" + base[12:], b"E-TRAIL " + b" " * 4 + base[12:],
        b"e-lower".ljust(12) + base[12:], b"E\xc3\x89" + b" " * 9 + base[12:],
        base[:91], base + b" ", base + b"\r" + b"\r",
    ]
    data = b"".join(l + b"\r\n" if i % 3 == 0 else l + b"\n" for i, l in enumerate(lines + extra))
    data += b"E-LASTNOEOL ".ljust(12) + base[12:]
    path.write_bytes(data)
    # tools/verify.py decodes its input as ASCII, so it gets the ASCII-only lines.
    ascii_lines = [l for l in data.split(b"\n") if all(b < 0x80 for b in l)]
    path.with_name("edge-ascii.dat").write_bytes(b"\n".join(ascii_lines))


FATAL_CASES = {
    "usage-3-args": lambda d: ["a", "b", "c"],
    "usage-5-args": lambda d: ["a", "b", "c", "d", "e"],
    "same-output-totals": lambda d: [d / "in.dat", d / "cwf.dat", d / "o.csv", d / "o.csv"],
    "trailing-space-alias": lambda d: [d / "in.dat", d / "cwf.dat", d / "o.csv", f"{d / 'o.csv'} "],
    "missing-input": lambda d: [d / "absent.dat", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "missing-cwf": lambda d: [d / "in.dat", d / "absent.cwf", d / "o.csv", d / "t.csv"],
    "malformed-cwf": lambda d: [d / "in.dat", d / "bad.cwf", d / "o.csv", d / "t.csv"],
    "cwf-1001-B": lambda d: [d / "in.dat", d / "many.cwf", d / "o.csv", d / "t.csv"],
    "empty-input-path": lambda d: ["", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "input-is-directory": lambda d: [d / "sub", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "unopenable-results": lambda d: [d / "in.dat", d / "cwf.dat", d / "no/o.csv", d / "t.csv"],
    "unopenable-totals": lambda d: [d / "in.dat", d / "cwf.dat", d / "o.csv", d / "no/t.csv"],
    "duplicate-id": lambda d: [d / "dup.dat", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "duplicate-invalid-id": lambda d: [d / "dupinv.dat", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "line-4097": lambda d: [d / "long.dat", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "records-10001": lambda d: [d / "many.dat", d / "cwf.dat", d / "o.csv", d / "t.csv"],
    "cwf-is-directory (not fatal)": lambda d: [d / "in.dat", d / "sub", d / "o.csv", d / "t.csv"],
}


def fatal_paths(cobol, python, out_dir):
    ledger = load_ledger()
    good = record({"id": "GOOD", "in": {"C": 100, "G": 100, "P": 0, "D": 0, "K": 0}}, ledger["defaults"])
    report = []
    for name, build in FATAL_CASES.items():
        outcome = {}
        for label, command in (("cobol", cobol), ("python", python)):
            with tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                (d / "sub").mkdir()
                (d / "in.dat").write_text(good + "\n")
                (d / "cwf.dat").write_text(ledger_cwf())
                (d / "bad.cwf").write_text(ledger_cwf() + "Q\n")
                (d / "many.cwf").write_text("".join(f"B9{n:010d}2020010199999999{'-' * 16}\n" for n in range(1001)))
                (d / "dup.dat").write_text(good + "\n" + good.replace("GOOD", "OK  ") + "\n" + good + "\n")
                (d / "dupinv.dat").write_text(good[:72] + "?" + good[73:] + "\n" + good + "\n")
                (d / "long.dat").write_text(good + "\n" + "X" * 4097 + "\n")
                (d / "many.dat").write_text("X\n" * 10001)
                for f in ("o.csv", "t.csv"):
                    (d / f).write_text("previous\n")
                args = [str(a) for a in build(d)]
                done = subprocess.run(shlex.split(command) + args, capture_output=True, timeout=120)
                outcome[label] = {"exit": done.returncode, "stdout_bytes": len(done.stdout),
                                  "results": (d / "o.csv").read_text() if (d / "o.csv").exists() else None,
                                  "totals": (d / "t.csv").read_text() if (d / "t.csv").exists() else None}
        c, p = outcome["cobol"], outcome["python"]
        report.append({"case": name, "cobol_exit": c["exit"], "python_exit": p["exit"],
                       "exit_match": c["exit"] == p["exit"],
                       "file_effects_match": (c["results"], c["totals"]) == (p["results"], p["totals"]),
                       "cobol_results_lines": None if c["results"] is None else len(c["results"].splitlines()),
                       "python_results_lines": None if p["results"] is None else len(p["results"].splitlines()),
                       "stdout_empty": c["stdout_bytes"] == p["stdout_bytes"] == 0})
    lines = ["# Fatal-path comparison", "",
             "Each case starts with `o.csv`/`t.csv` containing `previous`. Compared: exit code, and the final "
             "bytes of both output files (untouched, truncated or partial).", "",
             "| Case | COBOL exit | Python exit | Output files identical | Results lines (COBOL/Python) | stdout empty | Result |",
             "| --- | ---: | ---: | --- | --- | --- | --- |"]
    for r in report:
        ok = r["exit_match"] and r["file_effects_match"] and r["stdout_empty"]
        lines.append(f"| {r['case']} | {r['cobol_exit']} | {r['python_exit']} | {r['file_effects_match']} | "
                     f"{r['cobol_results_lines']}/{r['python_results_lines']} | {r['stdout_empty']} | "
                     f"{'MATCH' if ok else 'MISMATCH'} |")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fatal-paths.md").write_text("\n".join(lines) + "\n")
    (out_dir / "fatal-paths.json").write_text(json.dumps(report, indent=2) + "\n")
    return sum(not (r["exit_match"] and r["file_effects_match"] and r["stdout_empty"]) for r in report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cobol", default=str(ROOT / "build/msp-batch"))
    parser.add_argument("--python", default=f"{sys.executable} {ROOT / 'python/msp.py'}")
    parser.add_argument("--out", type=Path, default=ROOT / "evidence/live/comparison")
    args = parser.parse_args()
    edge_dir = args.out / "edge"
    edge_dir.mkdir(parents=True, exist_ok=True)
    edge_batch(edge_dir / "edge.dat")
    (edge_dir / "edge-cwf.dat").write_text(ledger_cwf())
    batches = [("curated", ROOT / "build/curated.dat", ROOT / "build/cwf.dat"),
               ("synthetic", ROOT / "build/synthetic.dat", ROOT / "build/cwf.dat"),
               ("edge", edge_dir / "edge.dat", edge_dir / "edge-cwf.dat"),
               ("edge-ascii", edge_dir / "edge-ascii.dat", edge_dir / "edge-cwf.dat")]
    summaries = [side_by_side(n, i, c, args.out / n, args.cobol, args.python) for n, i, c in batches]
    fatal_mismatches = fatal_paths(args.cobol, args.python, args.out)
    overall = {"batches": summaries, "fatal_path_mismatches": fatal_mismatches,
               "result": "PASS" if fatal_mismatches == 0 and all(
                   s["mismatches"] == 0 and s["results_bytes_identical"] and s["totals_bytes_identical"]
                   for s in summaries) else "FAIL"}
    (args.out / "summary.json").write_text(json.dumps(overall, indent=2) + "\n")
    for s in summaries:
        print(f"{s['batch']}: {s['records']} records, {s['mismatches']} mismatches, "
              f"results identical={s['results_bytes_identical']}, totals identical={s['totals_bytes_identical']}")
    print(f"fatal paths: {len(FATAL_CASES)} cases, {fatal_mismatches} mismatches")
    print(overall["result"])
    return 0 if overall["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
