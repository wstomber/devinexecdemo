#!/usr/bin/env python3
"""Synthetic MSP secondary-payment batch with a synthetic CWF pre-payment check.

Python translation of cobol/batch.cob, validate.cob, payment.cob and cwf.cob.
Usage: python3 python/msp.py INPUT CWF RESULTS TOTALS

All amounts are integer cents. Input is read as bytes. Fatal errors write a
diagnostic to stderr and exit 2; any partial outputs must be discarded.
"""
import sys

RECORD_LENGTH = 92
MAX_LINE = 4096
MAX_RECORDS = 10000
MAX_REFERENCE_RECORDS = 1000
CWF_RECORD_LENGTH = 64
PATH_LENGTH = 1024

DIGITS = frozenset(b"0123456789")
UPPER = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ID_CHARS = UPPER | DIGITS | frozenset(b"-_")
MBI_CHARS = UPPER | DIGITS
NO_CONTRACT = b"-" * 10

RESULT_HEADER = "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"


class Fatal(Exception):
    """A batch-level failure: exit 2, outputs discarded."""


def is_numeric(field):
    """COBOL `IS NUMERIC` on PIC X: every byte is an ASCII digit (and not empty)."""
    return bool(field) and all(b in DIGITS for b in field)


def is_blank(field):
    return all(b == 0x20 for b in field)


class Claim:
    def __init__(self, record_no):
        self.claim_id = f"@{record_no:010d}"
        self.status = "INVALID"
        self.reason = ""
        self.payment = 0
        self.cwf = "NOT_SENT"
        self.cwf_reason = "CLAIM_INVALID"
        self.released = 0
        self.charges = self.gross = self.primary = self.deductible = self.coinsurance = 0
        self.contract = None
        self.full = b""
        self.mbi = b""
        self.dos = 0


def validate(claim, line):
    """validate.cob: the first failing check sets the reason."""
    claim.reason = "BAD_LENGTH"
    if len(line) != RECORD_LENGTH:
        return
    raw_id = line[0:12]
    claim.reason = "BAD_ID"
    if is_blank(raw_id):
        return
    ended = False
    for b in raw_id:
        if b == 0x20:
            ended = True
        elif ended or b not in ID_CHARS:
            return
    claim.claim_id = raw_id.rstrip(b" ").decode("ascii")

    amounts = [line[i:i + 10] for i in range(12, 62, 10)]
    raw_contract = line[62:72]
    claim.reason = "BAD_AMOUNT"
    if not all(is_numeric(a) for a in amounts):
        return
    if raw_contract != NO_CONTRACT:
        if not is_numeric(raw_contract):
            return
        claim.contract = int(raw_contract)
    claim.charges, claim.gross, claim.primary, claim.deductible, claim.coinsurance = (int(a) for a in amounts)

    claim.reason = "BAD_CONTRACT"
    if claim.contract is not None and claim.contract > claim.charges:
        return
    claim.reason = "BAD_FLAG"
    full = line[72:73]
    if full not in (b"Y", b"N"):
        return
    claim.reason = "BAD_MBI"
    mbi = line[73:84]
    if not all(b in MBI_CHARS for b in mbi):
        return
    claim.reason = "BAD_DATE"
    dos = line[84:92]
    if not is_numeric(dos):
        return
    if not b"01" <= dos[4:6] <= b"12" or not b"01" <= dos[6:8] <= b"31":
        return
    claim.full, claim.mbi, claim.dos = full, mbi, int(dos)
    claim.status, claim.reason = "VALID", ""


def calculate_payment(claim):
    """payment.cob: max(0, min(G, B) - max(D + K, P)); full=Y pays 0."""
    claim.payment = 0
    claim.status = "ZERO"
    if claim.full == b"Y":
        claim.reason = "PAYMENT_IN_FULL"
        return
    charge_basis = claim.contract if claim.contract is not None else claim.charges
    payment_cap = min(claim.gross, charge_basis)
    if claim.primary >= payment_cap:
        claim.reason = "PRIMARY_AT_CAP"
        return
    deductions = claim.deductible + claim.coinsurance
    if deductions >= payment_cap:
        claim.reason = "DEDUCTIONS_AT_CAP"
        return
    claim.payment = payment_cap - max(deductions, claim.primary)
    claim.status, claim.reason = "PAID", "SECONDARY_PAYABLE"


def cwf_check(claim, beneficiaries, history):
    """cwf.cob: entitlement, duplicate of posted history, MSP primary not billed."""
    claim.released = 0
    claim.cwf, claim.cwf_reason = "REJECTED", "NOT_ENTITLED"
    bene = next((b for b in beneficiaries if b["mbi"] == claim.mbi), None)
    if bene is None or not bene["from"] <= claim.dos <= bene["to"]:
        return
    claim.cwf_reason = "DUPLICATE"
    if (claim.mbi, claim.dos, claim.charges) in history:
        return
    claim.cwf_reason = "MSP_PRIMARY_NOT_BILLED"
    if bene["msp"] is not None and bene["msp"][0] <= claim.dos <= bene["msp"][1] and claim.primary == 0:
        return
    claim.cwf, claim.cwf_reason = "ACCEPTED", "DISPOSITION_01"
    claim.released = claim.payment


def cwf_records(data):
    """GnuCOBOL LINE SEQUENTIAL read into PIC X(64): CR bytes are dropped,
    LF ends a record, bytes past 64 are ignored, short records are space-padded."""
    lines = data.replace(b"\r", b"").split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    for line in lines:
        yield line[:CWF_RECORD_LENGTH].ljust(CWF_RECORD_LENGTH, b" ")


def bad_cwf():
    sys.stderr.write("invalid CWF reference record\n")
    raise Fatal


def load_cwf(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        raise Fatal
    beneficiaries, history = [], set()
    history_count = 0
    for rec in cwf_records(data):
        kind = rec[0:1]
        if kind == b"B":
            if (not is_blank(rec[44:64]) or is_blank(rec[1:12]) or not is_numeric(rec[12:28])
                    or len(beneficiaries) >= MAX_REFERENCE_RECORDS):
                bad_cwf()
            msp_field = rec[28:44]
            if msp_field == b"-" * 16:
                msp = None
            elif is_numeric(msp_field):
                msp = (int(msp_field[0:8]), int(msp_field[8:16]))
            else:
                bad_cwf()
            beneficiaries.append({"mbi": rec[1:12], "from": int(rec[12:20]), "to": int(rec[20:28]), "msp": msp})
        elif kind == b"H":
            if (not is_blank(rec[30:64]) or is_blank(rec[1:12]) or not is_numeric(rec[12:30])
                    or history_count >= MAX_REFERENCE_RECORDS):
                bad_cwf()
            history_count += 1
            history.add((rec[1:12], int(rec[12:20]), int(rec[20:30])))
        else:
            bad_cwf()
    return beneficiaries, history


def read_lines(f):
    """batch.cob framing: LF ends a line; one trailing CR is removed; a final
    line without LF still counts; a line over 4,096 bytes is fatal."""
    while True:
        chunk = f.readline(MAX_LINE + 2)
        if not chunk:
            return
        if chunk.endswith(b"\n"):
            line = chunk[:-1]
        elif len(chunk) == MAX_LINE + 2:
            raise Fatal  # the COBOL buffer (4,097 bytes) overflows before any LF
        else:
            line = chunk
        if line.endswith(b"\r"):
            line = line[:-1]
        if len(line) > MAX_LINE:
            sys.stderr.write("input line exceeds 4096 bytes\n")
            raise Fatal
        yield line


def format_result(record_no, claim):
    return (f"{record_no:010d},{claim.claim_id},{claim.status},{claim.payment:010d},{claim.reason},"
            f"{claim.cwf},{claim.cwf_reason},{claim.released:010d}\n")


def run_batch(input_path, cwf_path, results_path, totals_path):
    beneficiaries, history = load_cwf(cwf_path)
    try:
        infile = open(input_path, "rb")
        results = open(results_path, "w", encoding="ascii", newline="\n")
        totals_file = open(totals_path, "w", encoding="ascii", newline="\n")
    except OSError:
        raise Fatal
    with infile, results, totals_file:
        results.write(RESULT_HEADER + "\n")
        seen_ids = set()
        counts = {"records": 0, "PAID": 0, "ZERO": 0, "INVALID": 0, "ACCEPTED": 0, "REJECTED": 0}
        payment_total = released_total = 0
        for line in read_lines(infile):
            if counts["records"] >= MAX_RECORDS:
                sys.stderr.write("batch exceeds 10000 records\n")
                raise Fatal
            counts["records"] += 1
            claim = Claim(counts["records"])
            validate(claim, line)
            if not claim.claim_id.startswith("@"):
                if claim.claim_id in seen_ids:
                    sys.stderr.write(f"duplicate claim ID: {claim.claim_id:<12}\n")
                    raise Fatal
                seen_ids.add(claim.claim_id)
            if claim.status == "VALID":
                calculate_payment(claim)
                cwf_check(claim, beneficiaries, history)
            counts[claim.status] += 1
            if claim.cwf in counts:
                counts[claim.cwf] += 1
            payment_total += claim.payment
            released_total += claim.released
            results.write(format_result(counts["records"], claim))
        totals_file.write(TOTALS_HEADER + "\n")
        totals_file.write(f"{counts['records']:010d},{counts['PAID']:010d},{counts['ZERO']:010d},"
                          f"{counts['INVALID']:010d},{payment_total:015d},{counts['ACCEPTED']:010d},"
                          f"{counts['REJECTED']:010d},{released_total:015d}\n")


def cobol_path(arg):
    """ACCEPT ... FROM ARGUMENT-VALUE into PIC X(1024): truncated, trailing spaces ignored."""
    return arg[:PATH_LENGTH].rstrip(" ")


def main(argv):
    if len(argv) != 4:
        sys.stderr.write("usage: msp-batch INPUT CWF OUTPUT TOTALS\n")
        return 2
    input_path, cwf_path, results_path, totals_path = (cobol_path(a) for a in argv)
    paths = [input_path, cwf_path, results_path, totals_path]
    if len(set(paths)) != 4:
        sys.stderr.write("paths must be distinct\n")
        return 2
    try:
        run_batch(input_path, cwf_path, results_path, totals_path)
    except (Fatal, OSError):
        sys.stderr.write("fatal batch failure; discard outputs\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
