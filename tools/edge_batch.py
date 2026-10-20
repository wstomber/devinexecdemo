"""Write an adversarial edge batch and CWF file for the COBOL/Python comparison (no expectations)."""
import argparse
import random
from pathlib import Path


def rec(i, charges=100000, gross=100000, primary=60000, ded=0, coins=0, contract=None, full=b"N",
        mbi=b"E1ENT000001", dos=b"20250315", cid=None):
    cid = cid if cid is not None else b"E%05d" % i
    c = b"-" * 10 if contract is None else b"%010d" % contract
    return cid.ljust(12) + b"%010d%010d%010d%010d%010d" % (charges, gross, primary, ded, coins) + c + full + mbi + dos


CWF = (b"BE1ENT0000012020010199999999----------------\r\n"          # CRLF
       b"BE2MSP00000120190101999999992025030120250630" + b" " * 20 + b"IGNORED-BEYOND-64\n"  # >64 bytes
       b"BE3W\rIN0000012025020120250331----------------\n"           # CR inside is dropped
       b"BE1ENT0000012030010199999999----------------\n"            # duplicate MBI: first wins
       b"BE4BAD0000012025123120250101----------------\n"            # from > to: never entitled
       b"HE1ENT000001202504100001500000          \n"                 # trailing spaces allowed
       b"HE9NOTONFILE202503150000100000\n"
       b"\r")                                                       # CR-only final segment = EOF


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cwf-output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=20261020)
    p.add_argument("--fuzz", type=int, default=3000)
    p.add_argument("--ascii", action="store_true", help="omit non-ASCII bytes (tools/verify.py decodes ASCII only)")
    a = p.parse_args()
    rng = random.Random(a.seed)
    lines, i = [], 0

    def add(line, ending=b"\n"):
        lines.append(line + ending)

    def nxt():
        nonlocal i
        i += 1
        return i

    top = 9_999_999_999
    hand = [
        rec(nxt()), rec(nxt(), mbi=b"E2MSP000001", primary=0, dos=b"20250301"),
        rec(nxt(), mbi=b"E2MSP000001", primary=0, dos=b"20250701"), rec(nxt(), mbi=b"E3WIN000001", dos=b"20250201"),
        rec(nxt(), mbi=b"E3WIN000001", dos=b"20250401"), rec(nxt(), mbi=b"E4BAD000001"),
        rec(nxt(), dos=b"20290101"), rec(nxt(), charges=1500000, gross=1400000, primary=1000000, dos=b"20250410"),
        rec(nxt(), mbi=b"E9NOTONFILE", charges=100000), rec(nxt(), dos=b"20250230"), rec(nxt(), dos=b"00000101"),
        rec(nxt(), charges=top, gross=top, primary=0), rec(nxt(), charges=top, gross=top, primary=top, ded=top,
                                                             coins=top, contract=top),
        rec(nxt(), charges=0, gross=0, primary=0), rec(nxt(), contract=0), rec(nxt(), full=b"Y", primary=top),
        rec(nxt(), charges=1500000, gross=1400000, primary=1250000, ded=155600, contract=1300000,
            mbi=b"E2MSP000001", dos=b"20250415", cid=b"CMS-EX3"),
    ]
    for h in hand:
        add(h)
    add(rec(nxt()), b"\r\n")
    add(rec(nxt()) + b"\r", b"\r\n")                  # CR CR LF -> 93 bytes
    add(rec(nxt())[:50] + b"\r" + rec(i)[51:])       # CR inside the record is data
    add(b"")
    add(b"\r")
    add(b" " * 92)
    add(b"\x00" * 92)
    add(rec(nxt(), cid=b"E%05d\x00" % i))
    if not a.ascii:
        add(rec(nxt()).replace(b"0000100000", b"\xd9\xa0" * 5, 1))
        add(rec(nxt(), cid=b"\xc3\x89%05d" % i))
    add(rec(nxt()).replace(b"E1ENT000001", b"E1ENT00000\t"))
    add(rec(nxt(), cid=b"lower%05d" % i))
    add(b"X" * 4096)
    add(rec(nxt()), b"\r\n")
    for _ in range(a.fuzz):
        n = nxt()
        line = bytearray(rec(n, charges=rng.randrange(top + 1), gross=rng.randrange(top + 1),
                             primary=rng.choice([0, rng.randrange(top + 1), rng.randrange(1000000)]),
                             ded=rng.randrange(2000000), coins=rng.randrange(2000000),
                             contract=rng.choice([None, rng.randrange(top + 1)]), full=rng.choice([b"Y", b"N", b"N"]),
                             mbi=rng.choice([b"E1ENT000001", b"E2MSP000001", b"E3WIN000001", b"E9NOTONFILE"]),
                             dos=b"2025%02d%02d" % (rng.randrange(0, 14), rng.randrange(0, 33))))
        for _ in range(rng.choice([0, 0, 1, 2])):
            pos = rng.randrange(6, 92)
            line[pos] = rng.choice(b"0123456789 -+._Yy?NAZaz\t\x00\r" if a.ascii else b"0123456789 -+._Yy?NAZaz\t\x00\xff\r")
        cut = rng.randrange(40)
        line = bytes(line[:91]) if cut == 0 else (bytes(line) + b"9" if cut == 1 else bytes(line))
        add(line, rng.choice([b"\n", b"\n", b"\r\n"]))
    lines[-1] = lines[-1].rstrip(b"\r\n")             # final record without newline
    a.output.write_bytes(b"".join(lines))
    a.cwf_output.write_bytes(CWF)
    print(f"wrote {len(lines)} edge records to {a.output}")


if __name__ == "__main__":
    main()
