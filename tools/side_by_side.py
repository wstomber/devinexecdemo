"""Run COBOL and Python on the same batch, keep both raw outputs, write a per-record side-by-side.

New presentation tooling for the live run; it does not replace tools/verify.py strict checks.
Usage: python3 tools/side_by_side.py NAME INPUT CWF OUTDIR [--baseline CMD] [--candidate CMD]
"""
import argparse
import csv
import shlex
import subprocess
from pathlib import Path

FIELDS = ["claim_id", "status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents"]


def execute(command, inp, cwf, results, totals):
    done = subprocess.run(shlex.split(command) + [str(inp), str(cwf), str(results), str(totals)],
                          capture_output=True, timeout=300)
    return done.returncode, done.stderr.decode(errors="replace")


def rows(path):
    with open(path, newline="", encoding="ascii") as stream:
        return list(csv.DictReader(stream))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name")
    p.add_argument("input", type=Path)
    p.add_argument("cwf", type=Path)
    p.add_argument("outdir", type=Path)
    p.add_argument("--baseline", default="build/msp-batch")
    p.add_argument("--candidate", default="python3 python/msp.py")
    a = p.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=True)
    out = {}
    for side, command in (("cobol", a.baseline), ("python", a.candidate)):
        res, tot = a.outdir / f"{a.name}-{side}-results.csv", a.outdir / f"{a.name}-{side}-totals.csv"
        code, err = execute(command, a.input, a.cwf, res, tot)
        if code != 0:
            raise SystemExit(f"{side} exited {code}: {err}")
        out[side] = (rows(res), res.read_bytes(), tot.read_bytes(), rows(tot)[0])
    cobol, python = out["cobol"], out["python"]
    numbers = sorted({r["record_no"] for r in cobol[0]} | {r["record_no"] for r in python[0]})
    cmap = {r["record_no"]: r for r in cobol[0]}
    pmap = {r["record_no"]: r for r in python[0]}
    table, mismatches = [], 0
    for n in numbers:
        c, q = cmap.get(n, {}), pmap.get(n, {})
        match = bool(c) and bool(q) and all(c[f] == q[f] for f in FIELDS)
        mismatches += not match
        table.append({"record_no": int(n), "claim_id": c.get("claim_id") or q.get("claim_id"),
                      **{f"cobol_{f}": c.get(f, "") for f in FIELDS[1:]},
                      **{f"python_{f}": q.get(f, "") for f in FIELDS[1:]},
                      "python_claim_id": q.get("claim_id", ""), "result": "MATCH" if match else "MISMATCH"})
    bytes_identical = cobol[1] == python[1] and cobol[2] == python[2]
    with open(a.outdir / f"{a.name}-side-by-side.csv", "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]) if table else ["record_no"])
        writer.writeheader()
        writer.writerows(table)
    ct, pt = cobol[3], python[3]
    md = [f"# Side-by-side: {a.name}", "",
          f"Input `{a.input}` ({len(numbers)} records), CWF `{a.cwf}`. COBOL `{a.baseline}`, Python `{a.candidate}`.",
          f"Raw outputs kept as `{a.name}-cobol-*.csv` and `{a.name}-python-*.csv`.", "",
          f"**Records: {len(numbers)}; MATCH: {len(numbers) - mismatches}; MISMATCH: {mismatches}. "
          f"Results and totals files byte-identical: {'YES' if bytes_identical else 'NO'}.**", "",
          "| Total | COBOL | Python | |", "| --- | ---: | ---: | --- |"]
    for k in ct:
        md.append(f"| {k} | {int(ct[k]):,} | {int(pt[k]):,} | {'MATCH' if ct[k] == pt[k] else 'MISMATCH'} |")
    md += ["", "| # | Claim ID | COBOL calc | Python calc | COBOL status/reason | Python status/reason | "
           "COBOL CWF | Python CWF | COBOL released | Python released | Result |",
           "| ---: | --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- |"]
    for r in table:
        md.append(f"| {r['record_no']} | {r['claim_id']} | {int(r['cobol_payment_cents'] or 0):,} | "
                  f"{int(r['python_payment_cents'] or 0):,} | {r['cobol_status']} {r['cobol_reason']} | "
                  f"{r['python_status']} {r['python_reason']} | {r['cobol_cwf']} {r['cobol_cwf_reason']} | "
                  f"{r['python_cwf']} {r['python_cwf_reason']} | {int(r['cobol_released_cents'] or 0):,} | "
                  f"{int(r['python_released_cents'] or 0):,} | {r['result']} |")
    (a.outdir / f"{a.name}-side-by-side.md").write_text("\n".join(md) + "\n")
    print(f"{a.name}: {len(numbers)} records, {mismatches} mismatches, byte-identical={bytes_identical}")
    return 1 if mismatches or ct != pt or not bytes_identical else 0


if __name__ == "__main__":
    raise SystemExit(main())
