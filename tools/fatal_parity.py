#!/usr/bin/env python3
"""Fatal-path parity: run COBOL and Python on each fatal scenario; compare exit code, stdout,
stderr and the state of the output files. Keeps every raw artefact."""
import argparse, hashlib, json, shlex, subprocess, sys
from pathlib import Path

VALID = (b"F00001      " + b"0000100000" + b"0000090000" + b"0000030000" + b"0000000000" * 2 +
         b"----------" + b"N" + b"P1MEDPRIM01" + b"20250610")
CWF = b"BP1MEDPRIM012020010199999999----------------\n"


def rec(i):
    return (b"F%05d" % i).ljust(12) + VALID[12:]


SCENARIOS = {
    "usage-no-args": dict(args=[]),
    "usage-three-args": dict(args=["IN", "CWF", "OUT"]),
    "usage-five-args": dict(args=["IN", "CWF", "OUT", "TOT", "EXTRA"]),
    "same-paths": dict(args=["IN", "CWF", "OUT", "OUT"]),
    "missing-input": dict(files={"CWF": CWF}),
    "missing-cwf": dict(files={"IN": VALID + b"\n"}),
    "malformed-cwf-type": dict(files={"IN": VALID + b"\n", "CWF": b"X" + CWF[1:]}),
    "malformed-cwf-blank": dict(files={"IN": VALID + b"\n", "CWF": CWF + b"\n"}),
    "malformed-cwf-date": dict(files={"IN": VALID + b"\n", "CWF": b"BP1MEDPRIM01202001019999999X----------------\n"}),
    "malformed-cwf-msp-mixed": dict(files={"IN": VALID + b"\n", "CWF": b"BP1MEDPRIM012020010199999999-------220251231\n"}),
    "malformed-h-charges": dict(files={"IN": VALID + b"\n", "CWF": CWF + b"HP1MEDPRIM0120250610000010000A\n"}),
    "cwf-1001-b": dict(files={"IN": VALID + b"\n", "CWF": b"".join(b"BM%010d2020010199999999----------------\n" % i for i in range(1001))}),
    "cwf-1001-h": dict(files={"IN": VALID + b"\n", "CWF": CWF + b"".join(b"HP1MEDPRIM0120250610%010d\n" % i for i in range(1001))}),
    "line-4097": dict(files={"IN": VALID + b"\n" + b"A" * 4097 + b"\n", "CWF": CWF}),
    "line-4098-no-newline": dict(files={"IN": VALID + b"\n" + b"A" * 4098, "CWF": CWF}),
    "line-5000": dict(files={"IN": VALID + b"\n" + b"A" * 5000 + b"\n" + VALID + b"\n", "CWF": CWF}),
    "line-4097-crlf-ok": dict(files={"IN": VALID + b"\n" + b"A" * 4096 + b"\r\n", "CWF": CWF}),
    "records-10001": dict(files={"IN": b"".join(rec(i) + b"\n" for i in range(10001)), "CWF": CWF}),
    "duplicate-id": dict(files={"IN": VALID + b"\n" + rec(2) + b"\n" + VALID + b"\n", "CWF": CWF}),
    "duplicate-id-rejected": dict(files={"IN": VALID + b"\n" + VALID[:72] + b"X" + VALID[73:] + b"\n", "CWF": CWF}),
    "output-dir-missing": dict(files={"IN": VALID + b"\n", "CWF": CWF}, args=["IN", "CWF", "nodir/OUT", "TOT"]),
    "totals-dir-missing": dict(files={"IN": VALID + b"\n", "CWF": CWF}, args=["IN", "CWF", "OUT", "nodir/TOT"]),
}


def state(d):
    out = {}
    for name in ("OUT", "TOT"):
        p = d / name
        out[name] = None if not p.exists() else hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def run(cmd, name, spec, root):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    for p in d.iterdir():
        if p.is_file():
            p.unlink()
    for fname, data in spec.get("files", {}).items():
        (d / fname).write_bytes(data)
    args = spec.get("args", ["IN", "CWF", "OUT", "TOT"])
    proc = subprocess.run(shlex.split(cmd) + args, cwd=d, capture_output=True, timeout=600)
    (d / "stdout.txt").write_bytes(proc.stdout)
    (d / "stderr.txt").write_bytes(proc.stderr)
    (d / "exit_code.txt").write_text(f"{proc.returncode}\n")
    return {"exit": proc.returncode, "stdout": proc.stdout.decode(errors="replace"),
            "stderr": proc.stderr.decode(errors="replace"), "outputs": state(d)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cobol", default=str(Path("build/msp-batch").resolve()))
    ap.add_argument("--python", default="python3 " + str(Path("python/msp.py").resolve()))
    a = ap.parse_args()
    rows, ok = [], True
    for name, spec in SCENARIOS.items():
        c = run(a.cobol, name, spec, a.out / "cobol")
        p = run(a.python, name, spec, a.out / "python")
        checks = {k: c[k] == p[k] for k in ("exit", "stdout", "stderr", "outputs")}
        match = all(checks.values())
        ok &= match
        rows.append({"scenario": name, "cobol": c, "python": p, "checks": checks, "match": match})
    (a.out / "fatal-parity.json").write_text(json.dumps(rows, indent=2) + "\n")
    md = ["# Fatal-path parity (COBOL vs Python)", "",
          "Each scenario runs in its own directory under `cobol/` and `python/` with the raw stdout, stderr, exit code and output files kept. "
          "`outputs` compares whether OUT/TOT exist afterwards and their SHA-256.", "",
          "| scenario | exit C / P | stderr (COBOL) | stderr same | outputs same | result |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        err = r["cobol"]["stderr"].strip().replace("\n", " ⏎ ").replace("|", "\\|")
        md.append(f"| {r['scenario']} | {r['cobol']['exit']} / {r['python']['exit']} | `{err}` | {r['checks']['stderr']} | {r['checks']['outputs']} | {'MATCH' if r['match'] else 'MISMATCH'} |")
    md += ["", f"**{sum(r['match'] for r in rows)} MATCH / {sum(not r['match'] for r in rows)} MISMATCH** of {len(rows)} scenarios."]
    (a.out / "fatal-parity.md").write_text("\n".join(md) + "\n")
    print(md[-1])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
