#!/usr/bin/env python3
"""Deterministic adversarial edge batch: the Stage 2 ledger records, then seeded byte-level
mutations of valid records (bad bytes, lengths, CR/blank lines, boundary amounts)."""
import argparse, json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests_policy"))
from msp_harness import build_case_record, cwf_file  # noqa: E402

ALPHABET = b"0123456789AZaz -_+.@\t\x00\x7f\xc3\xa9\xd9\xa3\xef\xbc\x93/,"
MBIS = [b"P1MEDPRIM01", b"P2MSPEGHP02", b"P3ENDENT003", b"P4STARTS004", b"P5HISTORY05", b"P6MSPEDGE06", b"P9NOTFILE09"]
DOS = [b"20250531", b"20250601", b"20250610", b"20250301", b"20250331", b"20250402", b"20250228", b"20250631"]


def amount(rng):
    return rng.choice([0, 1, 9999999999, 9999999998, rng.randrange(0, 10**6), rng.randrange(0, 10**10)])


def valid(rng, n):
    if rng.random() < 0.5:
        c = rng.randrange(1, 10**8); g = rng.randrange(0, c + c // 10 + 1)
        p = rng.randrange(0, g + 2); d = rng.randrange(0, 200000); k = rng.randrange(0, c // 5 + 1)
    else:
        c = amount(rng); g = amount(rng); p = amount(rng); d = amount(rng); k = amount(rng)
    contract = b"----------" if rng.random() < 0.5 else b"%010d" % rng.randrange(0, c + 1)
    return (b"E%05d" % n).ljust(12) + b"".join(b"%010d" % v for v in (c, g, p, d, k)) + contract + \
        rng.choice([b"N", b"N", b"Y"]) + rng.choice(MBIS) + rng.choice(DOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261019)
    ap.add_argument("--count", type=int, default=2000)
    a = ap.parse_args()
    ledger = json.loads((Path(__file__).resolve().parents[1] / "tests_policy/expectations.json").read_text())
    lines = [build_case_record(c, ledger["defaults"]).encode("ascii") for c in ledger["cases"]]
    rng = random.Random(a.seed)
    for n in range(a.count):
        rec = bytearray(valid(rng, n))
        mode = rng.random()
        if mode < 0.55:
            for _ in range(rng.randint(1, 3)):
                pos = rng.randrange(12, 92)  # keep the unique ID intact so no fatal duplicate
                rec[pos] = rng.choice(ALPHABET)
        elif mode < 0.62:
            rec = rec[:rng.randrange(0, 92)] if rng.random() < 0.5 else rec + bytes(rng.choice(ALPHABET) for _ in range(rng.randint(1, 40)))
        elif mode < 0.66:
            rec[rng.randrange(1, 12)] = rng.choice(b"az@.\t ")
        elif mode < 0.68:
            rec = bytearray()
        line = bytes(rec)
        if line.endswith(b"\r"):
            line = line[:-1] + b"X"
        if b"\n" in line:
            line = line.replace(b"\n", b"N")
        lines.append(line + (b"\r" if rng.random() < 0.2 else b""))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "edge.dat").write_bytes(b"\n".join(lines))  # no final newline on purpose
    (a.out / "edge-cwf.dat").write_bytes(cwf_file(ledger["cwf_reference"]))
    print(f"{len(lines)} records -> {a.out / 'edge.dat'}")


if __name__ == "__main__":
    main()
