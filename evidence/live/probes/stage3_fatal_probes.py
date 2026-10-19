#!/usr/bin/env python3
import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    repository = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("/tmp/fp"))
    parser.add_argument(
        "--report",
        type=Path,
        default=repository / "evidence/live/stage3-fatal-probes.txt",
    )
    args = parser.parse_args()

    parity = repository / "tools/fatal_parity.py"
    python_command = " ".join(
        (
            shlex.quote(sys.executable),
            shlex.quote(str(repository / "python/msp.py")),
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            str(parity),
            "--out",
            str(args.out.resolve()),
            "--python",
            python_command,
        ],
        cwd=repository,
        capture_output=True,
        text=True,
    )

    parity_file = args.out / "fatal-parity.json"
    if not parity_file.exists():
        sys.stderr.write(result.stderr)
        return result.returncode or 1

    rows = json.loads(parity_file.read_text())
    report = [
        f"# Fatal-path parity probe — {datetime.now(timezone.utc).isoformat()}",
        "",
        "Compared the COBOL executable and Python port across the 20 scenarios in "
        "`tools/fatal_parity.py`. `outputs` lists OUT/TOT SHA-256 values, or `null` "
        "when a file was absent.",
        "",
    ]
    for row in rows:
        cobol = row["cobol"]
        python = row["python"]
        report.extend(
            (
                f"## {row['scenario']}",
                f"- Exit: COBOL {cobol['exit']}; Python {python['exit']}",
                f"- Stdout identical: {row['checks']['stdout']}; "
                f"COBOL={cobol['stdout']!r}; Python={python['stdout']!r}",
                f"- Stderr identical: {row['checks']['stderr']}",
                f"- COBOL stderr: {cobol['stderr']!r}",
                f"- Python stderr: {python['stderr']!r}",
                f"- Outputs identical: {row['checks']['outputs']}",
                f"- COBOL OUT/TOT: {cobol['outputs']!r}",
                f"- Python OUT/TOT: {python['outputs']!r}",
                f"- Overall: {'MATCH' if row['match'] else 'MISMATCH'}",
                "",
            )
        )
    report.append(
        f"**{sum(row['match'] for row in rows)}/{len(rows)} scenarios matched all "
        "compared values.**"
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report) + "\n")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
