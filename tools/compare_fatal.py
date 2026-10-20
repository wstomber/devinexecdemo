"""Compare COBOL and Python on fatal and usage paths: exit code, stderr presence, and leftover outputs."""
import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path

B = b"BF1ENT0000012020010199999999----------------\n"


def rec(cid, mbi=b"F1ENT000001"):
    return cid.ljust(12) + b"0000100000" * 2 + b"0000060000" + b"0" * 20 + b"-" * 10 + b"N" + mbi + b"20250315"


GOOD = rec(b"G1") + b"\n" + rec(b"G2") + b"\n"
SCENARIOS = {
    "usage: no arguments": dict(args=[]),
    "usage: three arguments": dict(args=["in", "cwf", "out"]),
    "usage: five arguments": dict(args=["in", "cwf", "out", "tot", "extra"]),
    "identical output and totals": dict(args=["in", "cwf", "out", "out"]),
    "identical input and cwf": dict(args=["in", "in", "out", "tot"]),
    "missing input": dict(skip=["in"]),
    "missing CWF": dict(skip=["cwf"]),
    "malformed CWF (unknown type)": dict(cwf=B + b"Z\n"),
    "malformed CWF (blank line)": dict(cwf=B + b"\n"),
    "CWF 1001 beneficiaries": dict(cwf=b"".join(b"B%011d2020010199999999----------------\n" % i
                                                for i in range(1001))),
    "duplicate ID at record 3": dict(data=GOOD + rec(b"G1") + b"\n"),
    "duplicate of rejected identifiable ID": dict(data=rec(b"G1")[:72] + b"?" + rec(b"G1")[73:] + b"\n" + GOOD),
    "4097-byte line after 2 records": dict(data=GOOD + b"X" * 4097 + b"\n"),
    "4097-byte final line without LF": dict(data=GOOD + b"X" * 4097),
    "10001 records": dict(data=b"X\n" * 10001),
    "unwritable output directory": dict(args=["in", "cwf", "nodir/out", "tot"]),
    "unwritable totals directory": dict(args=["in", "cwf", "out", "nodir/tot"]),
    "input is a directory": dict(args=["adir", "cwf", "out", "tot"]),
}


def attempt(command, s):
    with tempfile.TemporaryDirectory(prefix="msp-fatal-") as d:
        d = Path(d)
        if "in" not in s.get("skip", []):
            (d / "in").write_bytes(s.get("data", GOOD))
        if "cwf" not in s.get("skip", []):
            (d / "cwf").write_bytes(s.get("cwf", B))
        (d / "adir").mkdir()
        (d / "out").write_bytes(b"stale\n")
        (d / "tot").write_bytes(b"stale\n")
        args = [str(d / a) for a in s.get("args", ["in", "cwf", "out", "tot"])]
        done = subprocess.run(shlex.split(command) + args, capture_output=True, timeout=120)
        leftovers = {n: (d / n).read_bytes().decode("ascii", "replace") for n in ("out", "tot")}
        return {"exit": done.returncode, "stderr_nonempty": bool(done.stderr.strip()),
                "stdout": done.stdout.decode(), "leftover_out": leftovers["out"], "leftover_tot": leftovers["tot"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", default="build/msp-batch")
    p.add_argument("--candidate", default="python3 python/msp.py")
    p.add_argument("--outdir", type=Path, required=True)
    a = p.parse_args()
    report, lines, bad = [], [], 0
    lines += ["# Fatal-path comparison", "",
              "Each scenario runs in a fresh directory whose OUTPUT and TOTALS start as `stale\\n`.",
              "Contract: exit 2, diagnostic on stderr, nothing on stdout, outputs discarded by the caller.", "",
              "| Scenario | COBOL exit | Python exit | stderr (C/P) | leftover outputs identical | Result |",
              "| --- | ---: | ---: | --- | --- | --- |"]
    for name, s in SCENARIOS.items():
        c, q = attempt(a.baseline, s), attempt(a.candidate, s)
        same_exit = c["exit"] == q["exit"] == 2 and c["stderr_nonempty"] and q["stderr_nonempty"] \
            and c["stdout"] == q["stdout"] == ""
        same_left = c["leftover_out"] == q["leftover_out"] and c["leftover_tot"] == q["leftover_tot"]
        bad += not same_exit
        report.append({"scenario": name, "cobol": c, "python": q, "exit_match": same_exit, "leftovers_match": same_left})
        lines.append(f"| {name} | {c['exit']} | {q['exit']} | {c['stderr_nonempty']}/{q['stderr_nonempty']} | "
                     f"{'YES' if same_left else 'NO'} | {'MATCH' if same_exit else 'MISMATCH'} |")
    a.outdir.mkdir(parents=True, exist_ok=True)
    (a.outdir / "fatal-paths.json").write_text(json.dumps(report, indent=2) + "\n")
    (a.outdir / "fatal-paths.md").write_text("\n".join(lines) + "\n")
    print(f"{len(SCENARIOS)} fatal scenarios, {bad} exit-code mismatches, "
          f"{sum(not r['leftovers_match'] for r in report)} leftover-output differences")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
