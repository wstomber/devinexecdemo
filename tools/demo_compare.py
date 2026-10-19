#!/usr/bin/env python3
"""Run COBOL and Python on the same batch and write a human-readable side-by-side.

This is presentation tooling only. The authoritative exact comparison is
tools/verify.py (unchanged starter file); this script retains both programs'
raw outputs and lays them out per record with an explicit MATCH/MISMATCH.

Both programs get the same CWF reference file (default build/cwf.dat).

    python3 tools/demo_compare.py --input build/curated.dat --out evidence/.../curated
    python3 tools/demo_compare.py --edge-cases --out evidence/.../edge
"""
import argparse
import csv
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COBOL = "build/msp-batch"
DEFAULT_PYTHON = "python3 python/msp.py"
DEFAULT_CWF = str(ROOT / "build" / "cwf.dat")
HIGHLIGHT = "CMS-EX3"


def run(command, input_path, cwf_path, out_dir, label):
    input_path, cwf_path = Path(input_path).resolve(), Path(cwf_path).resolve()
    results = (out_dir / f"{label}-results.csv").resolve()
    totals = (out_dir / f"{label}-totals.csv").resolve()
    if input_path in (results, totals) or cwf_path in (results, totals):
        sys.exit(f"--input/--cwf must not be one of the generated outputs: {input_path}")
    for stale in (results, totals):
        stale.unlink(missing_ok=True)
    proc = subprocess.run(shlex.split(command) + [str(input_path), str(cwf_path), str(results), str(totals)],
                          cwd=ROOT, capture_output=True, text=True)
    return {"command": command, "exit_code": proc.returncode, "stderr": proc.stderr.strip(),
            "results": results, "totals": totals}


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def dollars(cents):
    return f"${int(cents) / 100:,.2f}" if cents not in (None, "") else ""


def edge_case_batch(path):
    """Adversarial bytes the curated/synthetic fixtures do not exercise."""
    def rec(claim_id, amounts=b"0000100000" * 2 + b"0000010000" + b"0" * 20, contract=b"----------", flag=b"N",
            mbi=b"1EG4TE5MK73", dos=b"20250315"):
        return claim_id.ljust(12).encode("latin-1") + amounts + contract + flag + mbi + dos

    good = rec("EDGE-OK")
    assert len(good) == 92
    lines = [
        good,
        rec("edge-lower"),                                     # lowercase ID
        b"\x00DGE-NUL    " + good[12:],                       # NUL in ID
        b"\xc9DGE-HIGH   " + good[12:],                       # byte above 0x7F in ID
        b"EDGE-TAB\t   " + good[12:],                          # tab in ID
        rec("EDGE-ID-OVER"),                                   # 12-char ID, no padding
        rec("EDGE-SIGN", b"+000100000" + good[22:62]),        # signed amount
        rec("EDGE-POINT", b"0000100000" + b"00000.1000" + good[32:62]),  # decimal point
        rec("EDGE-HIBIT", b"000010000\xb9" + good[22:62]),    # high-bit digit lookalike
        rec("EDGE-DASH", contract=b"--------- "),               # malformed absent-contract marker
        rec("EDGE-OVERK", contract=b"0000100001"),              # contract > charges
        rec("EDGE-LFLAG", flag=b"n"),                           # lowercase flag
        good.replace(b"EDGE-OK    ", b"EDGE-LONG  ") + b" ",   # 93 bytes
        rec("EDGE-SHORT")[:91],                                 # 91 bytes
        b"",                                                    # blank line
        b"\r",                                                 # bare CR before LF -> empty record
        b" " * 92,                                              # spaces only
        rec("EDGE-ZERO", b"0" * 50),                            # all zero -> PRIMARY_AT_CAP
        rec("EDGE-MAX", b"9999999999" * 2 + b"0" * 30, contract=b"9999999999"),
        rec("EDGE-CRLF") + b"\r",                              # CRLF line ending
        rec("EDGE-OTAF0", contract=b"0000000000"),              # zero contract -> cap 0
        rec("EDGE-FULL", flag=b"Y"),
        rec("EDGE-DEDCAP", b"0000100000" * 2 + b"0" * 10 + b"0000060000" + b"0000040000"),
        rec("EDGE-1CENT", b"0000100000" * 2 + b"0000099999" + b"0" * 20),
        rec("EDGE-MBILOW", mbi=b"1eg4te5mk73"),                  # lowercase MBI
        rec("EDGE-MBINUL", mbi=b"1EG4TE5MK7\x00"),               # NUL in MBI
        rec("EDGE-MON13", dos=b"20251301"),                      # month 13
        rec("EDGE-DAY00", dos=b"20250300"),                      # day 00
        rec("EDGE-DOSHI", dos=b"2025031\xb9"),                   # high-bit digit lookalike in date
        rec("EDGE-NOBENE", mbi=b"9NOTONFILE9"),                  # CWF: not on file
        rec("EDGE-ENDED", mbi=b"3ENDED00001"),                   # CWF: entitlement ended
        rec("EDGE-MSP0", b"0000100000" * 2 + b"0" * 30, mbi=b"2MSP0000001"),  # CWF: MSP, no primary
        rec("EDGE-DUP", b"0001500000" + b"0000100000" + b"0000010000" + b"0" * 20, mbi=b"5HIST000001"),
    ]
    path.write_bytes(b"\n".join(lines))  # deliberately no final newline
    return len(lines)


def compare(input_path, out_dir, cobol_cmd, python_cmd, title, cwf_path=DEFAULT_CWF):
    out_dir.mkdir(parents=True, exist_ok=True)
    cobol = run(cobol_cmd, input_path, cwf_path, out_dir, "cobol")
    python = run(python_cmd, input_path, cwf_path, out_dir, "python")
    c_rows, p_rows = read_csv(cobol["results"]), read_csv(python["results"])
    c_tot, p_tot = read_csv(cobol["totals"]), read_csv(python["totals"])

    rows, mismatches = [], 0
    for i in range(max(len(c_rows), len(p_rows))):
        c = c_rows[i] if i < len(c_rows) else {}
        p = p_rows[i] if i < len(p_rows) else {}
        same = bool(c) and c == p
        mismatches += not same
        rows.append({
            "record_no": c.get("record_no") or p.get("record_no"),
            "claim_id": c.get("claim_id", "") if c.get("claim_id") == p.get("claim_id") else
                        f"{c.get('claim_id')} | {p.get('claim_id')}",
            "cobol_status": c.get("status", ""), "python_status": p.get("status", ""),
            "cobol_payment_cents": c.get("payment_cents", ""), "python_payment_cents": p.get("payment_cents", ""),
            "cobol_reason": c.get("reason", ""), "python_reason": p.get("reason", ""),
            "cobol_cwf": c.get("cwf", ""), "python_cwf": p.get("cwf", ""),
            "cobol_cwf_reason": c.get("cwf_reason", ""), "python_cwf_reason": p.get("cwf_reason", ""),
            "cobol_released_cents": c.get("released_cents", ""), "python_released_cents": p.get("released_cents", ""),
            "result": "MATCH" if same else "MISMATCH",
        })
    totals_match = c_tot == p_tot and bool(c_tot)
    exit_match = cobol["exit_code"] == python["exit_code"]
    files_identical = (sha256(cobol["results"]) == sha256(python["results"])
                       and sha256(cobol["totals"]) == sha256(python["totals"]))
    verdict = "MATCH" if (mismatches == 0 and totals_match and exit_match and files_identical) else "MISMATCH"

    with (out_dir / "side-by-side.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["record_no"])
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "title": title, "input": str(input_path), "input_sha256": sha256(input_path),
        "cwf": str(cwf_path), "cwf_sha256": sha256(Path(cwf_path).resolve()),
        "verdict": verdict, "records_compared": len(rows), "record_mismatches": mismatches,
        "totals_match": totals_match, "exit_codes": [cobol["exit_code"], python["exit_code"]],
        "byte_identical_outputs": files_identical,
        "cobol": {"command": cobol_cmd, "results_sha256": sha256(cobol["results"]),
                  "totals_sha256": sha256(cobol["totals"]), "totals": c_tot},
        "python": {"command": python_cmd, "results_sha256": sha256(python["results"]),
                   "totals_sha256": sha256(python["totals"]), "totals": p_tot},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    md = [f"# {title}", "",
          f"**Verdict: {verdict}** — {len(rows)} records compared, {mismatches} mismatches, "
          f"totals {'match' if totals_match else 'DIFFER'}, outputs "
          f"{'byte-identical' if files_identical else 'NOT byte-identical'}, exit codes "
          f"COBOL={cobol['exit_code']} Python={python['exit_code']}.", "",
          f"Input `{input_path}` (sha256 `{summary['input_sha256'][:16]}…`); CWF reference `{cwf_path}`.", "",
          "Each claim: the payment is calculated first, then the CWF pre-payment check accepts or "
          "rejects it; only an accepted claim releases its payment.", "",
          "Parity shows the Python matches the COBOL for this batch. It does not prove "
          "Medicare correctness; the independent tests in `tests_policy/` cover that layer.", ""]
    md += ["## Batch totals", "",
           "| | records | paid | zero | invalid | calculated | CWF accepted | CWF rejected | released |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name, tot in (("COBOL", c_tot), ("Python", p_tot)):
        if tot:
            t = tot[0]
            md.append(f"| {name} | {int(t['records'])} | {int(t['paid'])} | {int(t['zero'])} | "
                      f"{int(t['invalid'])} | {dollars(t['payment_cents'])} | {int(t['accepted'])} | "
                      f"{int(t['rejected'])} | {dollars(t['released_cents'])} |")
    md.append(f"| **Result** | | | | | | | | **{'MATCH' if totals_match else 'MISMATCH'}** |")
    highlighted = [r for r in rows if r["claim_id"] == HIGHLIGHT]
    if highlighted:
        r = highlighted[0]
        md += ["", f"## {HIGHLIGHT} (CMS Example 3)", "",
               f"COBOL {dollars(r['cobol_payment_cents'])} {r['cobol_reason']}, CWF {r['cobol_cwf']}, "
               f"released {dollars(r['cobol_released_cents'])} · "
               f"Python {dollars(r['python_payment_cents'])} {r['python_reason']}, CWF {r['python_cwf']}, "
               f"released {dollars(r['python_released_cents'])} · **{r['result']}**. "
               "Expected from policy: $13,000 OTAF − $12,500 primary = $500.00, accepted by CWF."]
    shown = rows if len(rows) <= 60 else [r for r in rows if r["result"] == "MISMATCH" or
                                          r["claim_id"] == HIGHLIGHT] + rows[:25]
    md += ["", "## Per record" + ("" if shown is rows else
           f" (first 25 + any mismatches + {HIGHLIGHT}; full table in side-by-side.csv)"), "",
           "| # | claim_id | COBOL status | Python status | COBOL calculated | Python calculated | COBOL reason | "
           "Python reason | COBOL CWF | Python CWF | COBOL released | Python released | result |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in shown:
        md.append(f"| {int(r['record_no'])} | `{r['claim_id']}` | {r['cobol_status']} | {r['python_status']} | "
                  f"{dollars(r['cobol_payment_cents'])} | {dollars(r['python_payment_cents'])} | "
                  f"{r['cobol_reason']} | {r['python_reason']} | {r['cobol_cwf']} {r['cobol_cwf_reason']} | "
                  f"{r['python_cwf']} {r['python_cwf_reason']} | {dollars(r['cobol_released_cents'])} | "
                  f"{dollars(r['python_released_cents'])} | **{r['result']}** |")
    (out_dir / "side-by-side.md").write_text("\n".join(md) + "\n")
    print(f"{verdict}: {title}: {len(rows)} records, {mismatches} mismatches, totals_match={totals_match}, "
          f"byte_identical={files_identical} -> {out_dir}/side-by-side.md")
    return verdict == "MATCH"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--edge-cases", action="store_true", help="generate an adversarial byte-level batch")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title")
    parser.add_argument("--cobol", default=DEFAULT_COBOL)
    parser.add_argument("--python", default=DEFAULT_PYTHON)
    parser.add_argument("--cwf", default=DEFAULT_CWF, help="CWF reference file given to both programs")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.edge_cases:
        args.input = args.out / "edge-cases.dat"
        edge_case_batch(args.input)
    title = args.title or f"COBOL vs Python: {args.input.name}"
    return 0 if compare(args.input, args.out, args.cobol, args.python, title, args.cwf) else 1


if __name__ == "__main__":
    sys.exit(main())
