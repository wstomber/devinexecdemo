"""Retain COBOL/Python batch outputs and produce record-level comparisons."""

import argparse
import csv
import io
import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_FIELDS = ("record_no", "claim_id", "status", "payment_cents", "reason")
TOTAL_FIELDS = ("records", "paid", "zero", "invalid", "payment_cents")
SIDE_BY_SIDE_FIELDS = (
    "record_no",
    "claim_id",
    "cobol_payment",
    "python_payment",
    "cobol_status",
    "python_status",
    "cobol_reason",
    "python_reason",
    "MATCH/MISMATCH",
)


def make_record(
    claim_id,
    charges=1000,
    gross=1000,
    primary=0,
    deductible=0,
    coinsurance=0,
    contract=None,
    full="N",
):
    raw_id = claim_id.encode("ascii").ljust(12, b" ")
    values = (charges, gross, primary, deductible, coinsurance)
    amounts = [f"{value:010d}".encode("ascii") for value in values]
    raw_contract = b"----------" if contract is None else f"{contract:010d}".encode("ascii")
    record = raw_id + b"".join(amounts) + raw_contract + full.encode("ascii")
    assert len(record) == 73, (len(record), record)
    return record


def replace_field(record, start, value):
    width = 12 if start == 0 else 1 if start == 72 else 10
    updated = record[:start] + value + record[start + width:]
    if len(updated) != 73:
        raise ValueError("replacement field must preserve the 73-byte record width")
    return updated


def edge_case_batch():
    lines = [
        make_record("EX3", 1500000, 1400000, 1250000, 155600, contract=1300000),
        make_record("NOOTAF", 1500000, 1400000, 1250000, 155600),
        make_record("FULL", 1000, 900, 500, 400, full="Y"),
        make_record("PRIMCAP", 1000, 900, 900, 900),
        make_record("DEDCAP", 1000, 900, 100, 800),
        make_record("ZEROA", 500, 900, contract=0),
        make_record("EQUALA", 500, 900, 100, 50, contract=500),
        make_record("BELOWA", 500, 900, 100, 50, contract=499),
        make_record("SHORT", 500, 500)[:-1],
        make_record("LONG", 500, 500) + b"X",
        replace_field(make_record("BADSPACE"), 0, b" " * 12),
        replace_field(make_record("LOWER"), 0, b"lower" + b" " * 7),
        replace_field(make_record("EMBED"), 0, b"BAD ID" + b" " * 6),
        replace_field(make_record("BADCHAR"), 0, b"BAD!ID" + b" " * 6),
        replace_field(make_record("PLUS"), 12, b"+000000000"),
        replace_field(make_record("SPACE"), 22, b" 000000000"),
        replace_field(make_record("UNDERSCR"), 32, b"_000000000"),
        replace_field(make_record("ARABIC"), 42, "٣".encode("utf-8") + b"0" * 8),
        replace_field(make_record("WIDE"), 52, "１".encode("utf-8") + b"0" * 7),
        replace_field(make_record("BADCONT"), 62, b"+000000000"),
        make_record("CONTRNG", 100, 100, contract=101),
        replace_field(make_record("BADFLAG"), 72, b"X"),
        replace_field(replace_field(make_record("PRECLEN"), 0, b" " * 12), 12,
                      b"+000000000")[:-1],
        replace_field(replace_field(make_record("PRECID"), 0, b"lower" + b" " * 7), 12,
                      b"+000000000"),
        replace_field(replace_field(make_record("PRECAMT", charges=100, contract=101), 12,
                                    b"+000000000"), 72, b"X"),
        replace_field(make_record("PRECCONT", charges=100, contract=101), 72, b"X"),
        make_record("MAX", 9999999999, 9999999999),
        make_record("MAXDED", 9999999999, 9999999999, deductible=9999999999,
                    coinsurance=9999999999),
        make_record("ONECENTP", 100, 100, primary=99),
        make_record("ONECENTD", 100, 100, deductible=99),
        make_record("ZEROALL", 0, 0),
        replace_field(make_record("REALAMT"), 12, b"00000_0000"),
        replace_field(make_record("REALCONT", charges=100), 62, b"0000000 01"),
        make_record("GROSSCAP", 700, 500, 100, 200),
        make_record("CHARGECAP", 500, 1000, 100, 200, contract=500),
        b"",
        b"X" * 4096,
        make_record("CRLF"),
        make_record("FULLPRE", 100, 100, 100, 100, full="Y"),
        make_record("DEDPRE", 100, 100, 99, 100),
        make_record("IDENTIFIED", 100, 100),
        make_record("LASTNO"),
    ]
    return b"".join(
        line + (b"\r\n" if line == b"X" * 4096 or index % 3 == 0 else b"\n")
        for index, line in enumerate(lines[:-1], start=1)
    ) + lines[-1]


def run_program(command, input_path, results_path, totals_path, args_override=None):
    argv = shlex.split(command)
    if not argv:
        raise ValueError("executable command cannot be empty")
    args = argv + ([str(input_path), str(results_path), str(totals_path)]
                   if args_override is None else args_override)
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return exc


def _load_csv(path):
    if not path.exists():
        return None
    try:
        return list(csv.DictReader(io.StringIO(path.read_text(encoding="ascii"), newline="")))
    except (OSError, UnicodeError, csv.Error):
        return None


def _records_by_number(rows):
    records = {}
    for row in rows or []:
        try:
            records[int(row["record_no"])] = row
        except (KeyError, TypeError, ValueError):
            continue
    return records


def _write_comparison_markdown(path, name, baseline, candidate, summary, side_rows):
    def totals_text(totals):
        if totals is None:
            return "unavailable"
        return ", ".join(f"{field}={totals.get(field, '')}" for field in TOTAL_FIELDS)

    lines = [
        f"# COBOL / Python comparison: {name}",
        "",
        "## Summary",
        "",
        f"- COBOL totals: {totals_text(summary['cobol_totals'])}",
        f"- Python totals: {totals_text(summary['python_totals'])}",
        f"- Record mismatches: {summary['record_mismatches']}",
        f"- Total mismatches: {summary['mismatch_count']}",
        f"- Results byte-identical: {'yes' if summary['results_byte_identical'] else 'no'}",
        f"- Totals byte-identical: {'yes' if summary['totals_byte_identical'] else 'no'}",
        f"- COBOL exit: {baseline.returncode if isinstance(baseline, subprocess.CompletedProcess) else 'error'}",
        f"- Python exit: {candidate.returncode if isinstance(candidate, subprocess.CompletedProcess) else 'error'}",
        "",
        "## Per-record results",
        "",
        "| record_no | claim_id | COBOL payment | Python payment | COBOL status | Python status | COBOL reason | Python reason | MATCH/MISMATCH |",
        "| ---: | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        "| " + " | ".join(
            str(value).replace("|", "\\|") for value in (
                row["record_no"], row["claim_id"], row["cobol_payment"],
                row["python_payment"], row["cobol_status"], row["python_status"],
                row["cobol_reason"], row["python_reason"], row["MATCH/MISMATCH"],
            )
        ) + " |"
        for row in side_rows
    )
    lines.extend([
        "",
        "## Limits",
        "",
        "Parity means agreement on these tested batches only; it does not prove Medicare correctness or completeness.",
        "",
        "Raw CSV outputs are retained beside this report; `side-by-side.csv` provides the same record-level comparison.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def compare_input(input_path, name, baseline_command, candidate_command, output_root):
    comparison_dir = output_root / name
    comparison_dir.mkdir(parents=True, exist_ok=True)
    retained_input = comparison_dir / "input.dat"
    if input_path.resolve() != retained_input.resolve():
        shutil.copyfile(input_path, retained_input)

    cobol_results = comparison_dir / "cobol-results.csv"
    cobol_totals = comparison_dir / "cobol-totals.csv"
    python_results = comparison_dir / "python-results.csv"
    python_totals = comparison_dir / "python-totals.csv"
    baseline = run_program(baseline_command, retained_input, cobol_results, cobol_totals)
    candidate = run_program(candidate_command, retained_input, python_results, python_totals)

    for label, completed in (("cobol", baseline), ("python", candidate)):
        if isinstance(completed, subprocess.CompletedProcess) and completed.stderr:
            (comparison_dir / f"{label}-stderr.txt").write_bytes(completed.stderr)
    (comparison_dir / "execution.json").write_text(
        json.dumps({
            "baseline_command": baseline_command,
            "candidate_command": candidate_command,
            "cobol_exit": baseline.returncode if isinstance(baseline, subprocess.CompletedProcess) else None,
            "python_exit": candidate.returncode if isinstance(candidate, subprocess.CompletedProcess) else None,
            "cobol_error": str(baseline) if isinstance(baseline, Exception) else None,
            "python_error": str(candidate) if isinstance(candidate, Exception) else None,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    cobol_rows = _load_csv(cobol_results)
    python_rows = _load_csv(python_results)
    cobol_totals_rows = _load_csv(cobol_totals)
    python_totals_rows = _load_csv(python_totals)
    cobol_totals_row = cobol_totals_rows[0] if cobol_totals_rows else None
    python_totals_row = python_totals_rows[0] if python_totals_rows else None
    cobol_by_number = _records_by_number(cobol_rows)
    python_by_number = _records_by_number(python_rows)
    record_mismatches = 0
    side_rows = []
    for record_no in sorted(set(cobol_by_number) | set(python_by_number)):
        cobol = cobol_by_number.get(record_no)
        python = python_by_number.get(record_no)
        match = cobol is not None and python is not None and all(
            cobol.get(field) == python.get(field) for field in RESULT_FIELDS
        )
        record_mismatches += not match
        cobol_id = cobol.get("claim_id", "") if cobol else ""
        python_id = python.get("claim_id", "") if python else ""
        claim_id = cobol_id if cobol_id == python_id else f"{cobol_id} / {python_id}"
        side_rows.append({
            "record_no": f"{record_no:010d}",
            "claim_id": claim_id,
            "cobol_payment": cobol.get("payment_cents", "") if cobol else "",
            "python_payment": python.get("payment_cents", "") if python else "",
            "cobol_status": cobol.get("status", "") if cobol else "",
            "python_status": python.get("status", "") if python else "",
            "cobol_reason": cobol.get("reason", "") if cobol else "",
            "python_reason": python.get("reason", "") if python else "",
            "MATCH/MISMATCH": "MATCH" if match else "MISMATCH",
        })

    result_bytes_equal = (
        cobol_results.exists() and python_results.exists()
        and cobol_results.read_bytes() == python_results.read_bytes()
    )
    totals_bytes_equal = (
        cobol_totals.exists() and python_totals.exists()
        and cobol_totals.read_bytes() == python_totals.read_bytes()
    )
    exits_match = (
        isinstance(baseline, subprocess.CompletedProcess)
        and isinstance(candidate, subprocess.CompletedProcess)
        and baseline.returncode == candidate.returncode == 0
    )
    mismatch_count = (
        record_mismatches
        + (not result_bytes_equal)
        + (not totals_bytes_equal)
        + (not exits_match)
    )
    summary = {
        "cobol_totals": cobol_totals_row,
        "python_totals": python_totals_row,
        "record_mismatches": record_mismatches,
        "mismatch_count": mismatch_count,
        "results_byte_identical": result_bytes_equal,
        "totals_byte_identical": totals_bytes_equal,
    }
    with (comparison_dir / "side-by-side.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SIDE_BY_SIDE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(side_rows)
    _write_comparison_markdown(
        comparison_dir / "side-by-side.md", name, baseline, candidate, summary, side_rows
    )
    print(f"{name}: records={len(side_rows)}, record_mismatches={record_mismatches}, "
          f"mismatches={mismatch_count}, results_byte_identical={'yes' if result_bytes_equal else 'no'}, "
          f"totals_byte_identical={'yes' if totals_bytes_equal else 'no'}")
    return 0 if mismatch_count == 0 else 1


def _fatal_case_data():
    duplicate = make_record("DUPLICATE")
    rejected = replace_field(make_record("REJECTED"), 72, b"X")
    return [
        ("usage_0_args", None, [], 2),
        ("usage_2_args", None, ["one", "two"], 2),
        ("usage_4_args", None, ["one", "two", "three", "four"], 2),
        ("identical_paths", None, ["{same}", "{same}", "{same}"], 2),
        ("missing_input", None, ["{missing}", "{results}", "{totals}"], 2),
        ("oversize_line", b"X" * 4097 + b"\n", None, 2),
        ("record_limit", b"\n" * 10001, None, 2),
        ("duplicate_valid_ids", duplicate + b"\n" + duplicate + b"\n", None, 2),
        ("duplicate_rejected_first",
         rejected + b"\n" + make_record("REJECTED") + b"\n", None, 2),
    ]


def fatal_comparisons(baseline_command, candidate_command, output_root):
    fatal_dir = output_root / "fatal"
    fatal_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, data, custom_args, expected in _fatal_case_data():
        case_dir = fatal_dir / name
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.dat"
        results_path = case_dir / "results.csv"
        totals_path = case_dir / "totals.csv"
        if data is not None:
            input_path.write_bytes(data)
        missing = case_dir / "missing.dat"
        for stale_output in (results_path, totals_path):
            stale_output.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix="msp-fatal-cobol-") as cobol_tmp:
            with tempfile.TemporaryDirectory(prefix="msp-fatal-python-") as python_tmp:
                cobol_results = Path(cobol_tmp) / "results.csv"
                cobol_totals = Path(cobol_tmp) / "totals.csv"
                python_results = Path(python_tmp) / "results.csv"
                python_totals = Path(python_tmp) / "totals.csv"
                if custom_args is not None:
                    def format_args(results, totals):
                        return [arg.format(
                            same=str(Path(results.parent) / "same.dat"),
                            missing=str(missing),
                            results=str(results),
                            totals=str(totals),
                        ) for arg in custom_args]

                    baseline = run_program(
                        baseline_command, input_path, cobol_results, cobol_totals,
                        format_args(cobol_results, cobol_totals),
                    )
                    candidate = run_program(
                        candidate_command, input_path, python_results, python_totals,
                        format_args(python_results, python_totals),
                    )
                else:
                    baseline = run_program(baseline_command, input_path, cobol_results, cobol_totals)
                    candidate = run_program(candidate_command, input_path, python_results, python_totals)
        baseline_stderr = baseline.stderr if isinstance(baseline, subprocess.CompletedProcess) else str(baseline).encode()
        candidate_stderr = candidate.stderr if isinstance(candidate, subprocess.CompletedProcess) else str(candidate).encode()
        (case_dir / "cobol-stderr.txt").write_bytes(baseline_stderr)
        (case_dir / "python-stderr.txt").write_bytes(candidate_stderr)
        cobol_exit = baseline.returncode if isinstance(baseline, subprocess.CompletedProcess) else "ERROR"
        python_exit = candidate.returncode if isinstance(candidate, subprocess.CompletedProcess) else "ERROR"
        matches = cobol_exit == python_exit == expected
        rows.append({
            "case": name,
            "expected_exit": expected,
            "cobol_exit": cobol_exit,
            "python_exit": python_exit,
            "MATCH/MISMATCH": "MATCH" if matches else "MISMATCH",
        })

    fields = ("case", "expected_exit", "cobol_exit", "python_exit", "MATCH/MISMATCH")
    with (fatal_dir / "fatal-paths.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    mismatches = sum(row["MATCH/MISMATCH"] != "MATCH" for row in rows)
    markdown = [
        "# Fatal path comparisons",
        "",
        f"- Fatal scenarios: {len(rows)}",
        f"- Mismatches: {mismatches}",
        "",
        "| Case | Expected exit | COBOL exit | Python exit | Result |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    markdown.extend(
        f"| {row['case']} | {row['expected_exit']} | {row['cobol_exit']} | "
        f"{row['python_exit']} | {row['MATCH/MISMATCH']} |" for row in rows
    )
    (fatal_dir / "fatal-paths.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(f"fatal: scenarios={len(rows)}, mismatches={mismatches}, "
          f"report={fatal_dir / 'fatal-paths.csv'}")
    return 0 if mismatches == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="build/msp-batch")
    parser.add_argument("--candidate", default="python3 python/msp.py")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/live/comparison"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--edge-cases", action="store_true")
    mode.add_argument("--fatal", action="store_true")
    args = parser.parse_args(argv)
    output_root = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir

    if args.fatal:
        return fatal_comparisons(args.baseline, args.candidate, output_root)
    if args.edge_cases:
        name = args.name or "edge"
        comparison_dir = output_root / name
        comparison_dir.mkdir(parents=True, exist_ok=True)
        input_path = comparison_dir / "input.dat"
        input_path.write_bytes(edge_case_batch())
    else:
        if args.input is None:
            parser.error("--input is required unless --edge-cases or --fatal is selected")
        input_path = args.input if args.input.is_absolute() else ROOT / args.input
        name = args.name or input_path.stem
    return compare_input(input_path, name, args.baseline, args.candidate, output_root)


if __name__ == "__main__":
    raise SystemExit(main())
