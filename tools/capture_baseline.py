"""Capture actual COBOL outputs and provenance; never compute policy payments."""
import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from verify import VerificationError, batch_identities, differences, read_results


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", default="build/msp-batch")
    parser.add_argument("--compiler", default="cobc")
    parser.add_argument("--output", type=Path, default=Path("build/baseline"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    commands, log = [], []

    def execute(argv):
        entry = {"argv": argv, "exit_code": None}
        commands.append(entry)
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        entry["exit_code"] = completed.returncode
        log.append("$ " + shlex.join(argv) + "\n" + completed.stdout + completed.stderr
                   + f"[exit {completed.returncode}]\n")
        if completed.returncode:
            raise RuntimeError(f"command failed ({completed.returncode}): {shlex.join(argv)}")
        return completed.stdout

    if sys.version_info < (3, 9):
        parser.error("Python 3.9+ is required")
    if args.check_only:
        try:
            print(execute(shlex.split(args.compiler) + ["-V"]).splitlines()[0])
            print("Python " + platform.python_version() + "; standard library only, no pip dependencies")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"result": "FAIL", "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "kind": "COBOL baseline only", "migration_comparison": "NOT_RUN",
                "python_version": platform.python_version(), "seed": 20261017,
                "commands": commands, "batches": {}, "files_sha256": {}}
    try:
        # A commit plus hashes of the actual sources identifies what was executed.
        if Path(".git").exists():
            manifest["source_commit"] = execute(
                ["git", "-c", f"safe.directory={Path.cwd()}", "rev-parse", "HEAD"]
            ).strip()
        else:
            manifest["source_commit"] = None
            manifest["provenance_note"] = "No Git metadata in this export/image; use source hashes and the checkout's pinned commit."
        manifest["compiler_version"] = execute(shlex.split(args.compiler) + ["-V"]).splitlines()[0]
        python = sys.executable
        cwf = args.output / "cwf.dat"
        execute([python, "tools/fixtures.py", "--cwf-source", "fixtures/cwf.json", "--output", str(cwf)])
        execute([python, "tools/fixtures.py", "--source", "fixtures/curated.json",
                 "--output", str(args.output / "curated.dat")])
        execute([python, "tools/fixtures.py", "--count", "1000", "--seed", "20261017",
                 "--output", str(args.output / "synthetic.dat")])
        execute([python, "tools/verify.py", "baseline", "--command", args.command,
                 "--report", str(args.output / "curated-verification.json")])
        for name in ("curated", "synthetic"):
            input_path = args.output / f"{name}.dat"
            results = args.output / f"{name}-results.csv"
            totals = args.output / f"{name}-totals.csv"
            execute(shlex.split(args.command) + [str(input_path), str(cwf), str(results), str(totals)])
            actual, reconciled = read_results(results, totals, batch_identities(input_path))
            if name == "curated":
                ledger = json.loads(Path("fixtures/expected.json").read_text())
                expected = {r["record_no"]: {k: r[k] for k in ("claim_id", "status", "payment_cents", "reason",
                                                  "cwf", "cwf_reason", "released_cents")}
                            for r in ledger["records"]}
                if differences(actual, expected) or reconciled != ledger["totals"]:
                    raise RuntimeError("retained curated output differs from independent expectations")
            manifest["batches"][name] = reconciled
        sources = sorted(Path("cobol").rglob("*.cob")) + sorted(Path("cobol").rglob("*.cpy"))
        sources += [Path("fixtures/curated.json"), Path("fixtures/expected.json"), Path("fixtures/cwf.json"),
                    Path("tools/fixtures.py"), Path("tools/verify.py"), Path("tools/capture_baseline.py")]
        manifest["source_files_sha256"] = {str(p): digest(p) for p in sources}
        manifest["files_sha256"] = {p.name: digest(p) for p in sorted(args.output.iterdir())
                                    if p.suffix in (".dat", ".csv") or p.name == "curated-verification.json"}
        manifest["result"] = "PASS"
    except (OSError, RuntimeError, ValueError, VerificationError, subprocess.TimeoutExpired) as exc:
        manifest["error"] = str(exc)
    finally:
        (args.output / "commands.log").write_text("\n".join(log))
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{manifest['result']}: COBOL capture at {args.output}; migration comparison NOT_RUN")
    return 0 if manifest["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
