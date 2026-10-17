"""Executable verification using curated expectations, never a policy oracle."""
import argparse
import csv
import io
import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

from fixtures import case_record

RESULT_FIELDS = ["record_no", "claim_id", "status", "payment_cents", "reason"]
TOTAL_FIELDS = ["records", "paid", "zero", "invalid", "payment_cents"]
REASONS = {
    "PAID": {"SECONDARY_PAYABLE"},
    "ZERO": {"PAYMENT_IN_FULL", "PRIMARY_AT_CAP", "DEDUCTIONS_AT_CAP"},
    "INVALID": {"BAD_LENGTH", "BAD_ID", "BAD_AMOUNT", "BAD_CONTRACT", "BAD_FLAG"},
}


class VerificationError(Exception):
    pass


def read_csv(path, fields):
    try:
        content = path.read_text(encoding="ascii")
        if any(not line for line in content.splitlines()):
            raise VerificationError(f"{path.name}: blank CSV line")
        reader = csv.DictReader(io.StringIO(content), strict=True)
        if reader.fieldnames != fields:
            raise VerificationError(f"{path.name}: incorrect CSV header")
        rows = list(reader)
        if any(set(row) != set(fields) or any(v is None for v in row.values()) for row in rows):
            raise VerificationError(f"{path.name}: malformed CSV row")
        return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise VerificationError(f"{path.name}: {exc}") from exc


def integer(value, maximum):
    if not re.fullmatch(r"[0-9]+", value) or len(value) > 20 or int(value) > maximum:
        raise VerificationError(f"invalid unsigned integer {value!r}")
    return int(value)


def read_results(output, totals, identities):
    rows = read_csv(output, RESULT_FIELDS)
    results, ids = {}, set()
    for row in rows:
        number = integer(row["record_no"], 10000)
        if number in results:
            raise VerificationError(f"duplicate record {number}")
        if number not in identities:
            raise VerificationError(f"unexpected record {number}")
        if row["claim_id"] != identities[number]:
            raise VerificationError(f"record {number}: unexpected claim ID")
        if row["claim_id"] in ids:
            raise VerificationError(f"duplicate claim ID {row['claim_id']}")
        ids.add(row["claim_id"])
        status = row["status"]
        if status not in REASONS or row["reason"] not in REASONS[status]:
            raise VerificationError(f"record {number}: invalid status/reason")
        amount = integer(row["payment_cents"], 9_999_999_999)
        if (status == "PAID") != (amount > 0):
            raise VerificationError(f"record {number}: inconsistent status/payment")
        results[number] = {"claim_id": row["claim_id"], "status": status,
                           "payment_cents": amount, "reason": row["reason"]}
    if set(results) != set(identities):
        raise VerificationError(f"missing records {sorted(set(identities) - set(results))[:10]}")
    total_rows = read_csv(totals, TOTAL_FIELDS)
    if len(total_rows) != 1:
        raise VerificationError("totals must contain exactly one data row")
    supplied = {k: integer(v, 99_999_999_990_000 if k == "payment_cents" else 10000)
                for k, v in total_rows[0].items()}
    calculated = {"records": len(results), "paid": 0, "zero": 0, "invalid": 0,
                  "payment_cents": sum(r["payment_cents"] for r in results.values())}
    for row in results.values():
        calculated[row["status"].lower()] += 1
    if supplied != calculated:
        raise VerificationError(f"batch totals mismatch: {supplied} != {calculated}")
    return results, supplied


def run(command, input_path, identities, timeout):
    argv = shlex.split(command)
    if not argv:
        raise VerificationError("empty executable command")
    with tempfile.TemporaryDirectory(prefix="msp-verify-") as directory:
        output, totals = Path(directory) / "results.csv", Path(directory) / "totals.csv"
        try:
            completed = subprocess.run(
                argv + [str(input_path.resolve()), str(output), str(totals)],
                capture_output=True, timeout=timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise VerificationError(f"execution failed: {exc}") from exc
        if completed.returncode != 0:
            raise VerificationError(f"exit {completed.returncode}: "
                                    + completed.stderr.decode(errors="replace")[-1000:])
        return read_results(output, totals, identities)


def batch_identities(path):
    content = path.read_bytes().decode("ascii")
    records = content.split("\n") if content else []
    if records and records[-1] == "":
        records.pop()
    records = [line[:-1] if line.endswith("\r") else line for line in records]
    if len(records) > 10000:
        raise VerificationError("batch exceeds 10000 records")
    identities = {}
    for i, line in enumerate(records, 1):
        raw_id = line[:12].rstrip(" ")
        identities[i] = raw_id if len(line) == 73 and re.fullmatch(r"[A-Z0-9_-]{1,12}", raw_id) else f"@{i:010d}"
    return identities


def differences(actual, expected):
    return [{"record_no": n, "actual": actual.get(n), "expected": expected.get(n)}
            for n in sorted(set(actual) | set(expected)) if actual.get(n) != expected.get(n)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["baseline", "compare"])
    parser.add_argument("--command", default="build/msp-batch")
    parser.add_argument("--candidate")
    parser.add_argument("--cases", type=Path, default=Path("fixtures/curated.json"))
    parser.add_argument("--expected", type=Path, default=Path("fixtures/expected.json"))
    parser.add_argument("--input", type=Path, default=Path("build/synthetic.dat"))
    parser.add_argument("--report", type=Path, default=Path("build/verification.json"))
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    report = {"mode": args.mode, "command": args.command, "candidate": args.candidate,
              "result": "FAIL", "migration_comparison": "NOT_RUN",
              "input": str(args.input) if args.mode == "compare" else str(args.cases),
              "expected": str(args.expected) if args.mode == "baseline" else None,
              "timeout_seconds": args.timeout}
    exit_code = 1
    try:
        if args.timeout <= 0:
            raise VerificationError("timeout must be positive")
        if args.mode == "compare" and not args.candidate:
            report["result"] = "NOT_RUN"
            report["error"] = "Python candidate not supplied; migration comparison has not run"
            exit_code = 2
        elif args.mode == "baseline":
            cases = json.loads(args.cases.read_text())
            expected_file = json.loads(args.expected.read_text())
            expected = {r["record_no"]: {k: r[k] for k in RESULT_FIELDS if k != "record_no"}
                        for r in expected_file["records"]}
            if len(expected) != len(expected_file["records"]) or set(expected) != set(range(1, len(cases) + 1)):
                raise VerificationError("expected record keys must be unique and contiguous")
            with tempfile.TemporaryDirectory() as directory:
                batch = Path(directory) / "curated.dat"
                batch.write_text("".join(case_record(c) + "\n" for c in cases), encoding="ascii")
                identities = batch_identities(batch)
                actual, totals = run(args.command, batch, identities, args.timeout)
            report["differences"] = differences(actual, expected)
            report["totals"] = totals
            if totals != expected_file["totals"]:
                raise VerificationError("totals differ from curated expectations")
            if report["differences"]:
                raise VerificationError(f"{len(report['differences'])} curated discrepancies")
            report["result"], exit_code = "PASS", 0
        else:
            report["migration_comparison"] = "ATTEMPTED"
            identities = batch_identities(args.input)
            baseline, totals = run(args.command, args.input, identities, args.timeout)
            candidate, candidate_totals = run(args.candidate, args.input, identities, args.timeout)
            report["migration_comparison"] = "RUN"
            report["differences"] = differences(candidate, baseline)
            report["baseline_totals"], report["candidate_totals"] = totals, candidate_totals
            if report["differences"] or totals != candidate_totals:
                raise VerificationError(f"{len(report['differences'])} migration discrepancies")
            report["result"], exit_code = "PASS", 0
    except (VerificationError, OSError, ValueError, KeyError, TypeError) as exc:
        report["error"] = str(exc)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['result']}: {report.get('error', 'records and totals match')}; report={args.report}")
    if args.mode == "baseline":
        print("Migration comparison: NOT_RUN (baseline verification only)")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
