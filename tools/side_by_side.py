#!/usr/bin/env python3
"""Run COBOL and Python on the same batch; keep raw outputs; write a per-record side-by-side."""
import argparse, csv, hashlib, io, json, shlex, subprocess, sys
from pathlib import Path

FIELDS = ["status", "payment_cents", "reason", "cwf", "cwf_reason", "released_cents"]


def run(cmd, input_path, cwf_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    results, totals = out_dir / "results.csv", out_dir / "totals.csv"
    for p in (results, totals):
        p.unlink(missing_ok=True)
    argv = shlex.split(cmd) + [str(input_path), str(cwf_path), str(results), str(totals)]
    proc = subprocess.run(argv, capture_output=True, timeout=600)
    (out_dir / "stdout.txt").write_bytes(proc.stdout)
    (out_dir / "stderr.txt").write_bytes(proc.stderr)
    (out_dir / "exit_code.txt").write_text(f"{proc.returncode}\n")
    (out_dir / "command.txt").write_text(" ".join(shlex.quote(a) for a in argv) + "\n")
    return proc


def read_csv(path):
    with open(path, newline="", encoding="ascii") as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--cwf", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cobol", default="build/msp-batch")
    ap.add_argument("--python", default="python3 python/msp.py")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    pc = run(a.cobol, a.input, a.cwf, a.out / "cobol")
    pp = run(a.python, a.input, a.cwf, a.out / "python")
    problems = []
    for label, p in (("cobol", pc), ("python", pp)):
        if p.returncode != 0:
            problems.append(f"{label} exit {p.returncode}: {p.stderr.decode(errors='replace').strip()}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        sys.exit(1)
    cr, pr = read_csv(a.out / "cobol/results.csv"), read_csv(a.out / "python/results.csv")
    ct, pt = read_csv(a.out / "cobol/totals.csv")[0], read_csv(a.out / "python/totals.csv")[0]
    rows, mism = [], 0
    for i in range(max(len(cr), len(pr))):
        c = cr[i] if i < len(cr) else {}
        p = pr[i] if i < len(pr) else {}
        same = c == p
        mism += not same
        row = {"record_no": c.get("record_no", p.get("record_no", "")),
               "claim_id_cobol": c.get("claim_id", ""), "claim_id_python": p.get("claim_id", "")}
        for f in FIELDS:
            row[f + "_cobol"] = c.get(f, "")
            row[f + "_python"] = p.get(f, "")
        row["match"] = "MATCH" if same else "MISMATCH"
        rows.append(row)
    totals_match = ct == pt
    byte_identical = {n: sha(a.out / "cobol" / n) == sha(a.out / "python" / n) for n in ("results.csv", "totals.csv")}
    count = lambda rs, k, v: sum(r[k] == v for r in rs)
    summary = {
        "batch": a.name, "input": str(a.input), "input_sha256": sha(a.input),
        "cwf": str(a.cwf), "cwf_sha256": sha(a.cwf),
        "records_cobol": len(cr), "records_python": len(pr),
        "matches": len(rows) - mism, "mismatches": mism,
        "totals_match": totals_match, "byte_identical": byte_identical,
        "status_counts": {s: [count(cr, "status", s), count(pr, "status", s)] for s in ("PAID", "ZERO", "INVALID")},
        "cwf_counts": {s: [count(cr, "cwf", s), count(pr, "cwf", s)] for s in ("ACCEPTED", "REJECTED", "NOT_SENT")},
        "totals_cobol": ct, "totals_python": pt,
        "stdout_empty": [not pc.stdout, not pp.stdout],
    }
    with open(a.out / "side-by-side.csv", "w", newline="", encoding="ascii") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["record_no"], lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    md = io.StringIO()
    md.write(f"# Side-by-side: {a.name} batch (COBOL vs Python)\n\n")
    md.write(f"Input `{a.input}` (sha256 `{summary['input_sha256'][:16]}…`), CWF `{a.cwf}`. "
             f"Raw outputs: `cobol/` and `python/` next to this file.\n\n")
    md.write(f"**{summary['matches']} MATCH / {mism} MISMATCH** of {len(rows)} records; totals "
             f"{'MATCH' if totals_match else 'MISMATCH'}; results.csv byte-identical: {byte_identical['results.csv']}; "
             f"totals.csv byte-identical: {byte_identical['totals.csv']}.\n\n")
    md.write("| count | COBOL | Python |\n| --- | ---: | ---: |\n")
    for k, (x, y) in {**summary["status_counts"], **summary["cwf_counts"]}.items():
        md.write(f"| {k} | {x} | {y} |\n")
    md.write("\n| total | COBOL | Python |\n| --- | ---: | ---: |\n")
    for k in ct:
        md.write(f"| {k} | {ct[k]} | {pt.get(k, '')} |\n")
    md.write("\n| # | ID (COBOL / Python) | payment C / P | status·reason C / P | CWF·reason C / P | released C / P | result |\n"
             "| ---: | --- | ---: | --- | --- | ---: | --- |\n")
    for r in rows:
        ids = r["claim_id_cobol"] if r["claim_id_cobol"] == r["claim_id_python"] else f"{r['claim_id_cobol']} / {r['claim_id_python']}"
        md.write(f"| {int(r['record_no'] or 0)} | {ids} | {int(r['payment_cents_cobol'] or 0)} / {int(r['payment_cents_python'] or 0)} "
                 f"| {r['status_cobol']}·{r['reason_cobol']} / {r['status_python']}·{r['reason_python']} "
                 f"| {r['cwf_cobol']}·{r['cwf_reason_cobol']} / {r['cwf_python']}·{r['cwf_reason_python']} "
                 f"| {int(r['released_cents_cobol'] or 0)} / {int(r['released_cents_python'] or 0)} | {r['match']} |\n")
    md.write("\nParity shows the Python matches the COBOL on this batch only; it is not proof of Medicare correctness.\n")
    (a.out / "side-by-side.md").write_text(md.getvalue())
    print(json.dumps({k: summary[k] for k in ("batch", "records_cobol", "matches", "mismatches", "totals_match", "byte_identical")}))
    sys.exit(0 if mism == 0 and totals_match and len(cr) == len(pr) else 1)


if __name__ == "__main__":
    main()
