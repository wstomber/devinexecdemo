#!/usr/bin/env python3
"""MSP secondary payment and synthetic CWF pre-payment check (Python port of cobol/).

Usage: msp.py INPUT CWF OUTPUT TOTALS

Synthetic educational example, not CMS production code. Standard library only.
Money is integer cents throughout; there is no float anywhere in this module.
Exit 0 = batch ran (records may be INVALID); exit 2 = any fatal error.
"""
import os
import sys

RECORD_LENGTH = 92
MAX_LINE = 4096          # longest physical line processed as a (malformed) record
MAX_BUFFER = MAX_LINE + 1  # room for one trailing CR before the length check
MAX_RECORDS = 10000
MAX_CWF_ENTRIES = 1000
CWF_RECORD = 64          # cwf-record pic x(64): later bytes on a CWF line are ignored
PATH_FIELD = 1024        # pic x(1024) argument fields

DIGITS = frozenset(b"0123456789")
UPPER = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ID_CHARS = UPPER | DIGITS | frozenset(b"-_")
MBI_CHARS = UPPER | DIGITS
SPACE = 0x20
ABSENT_CONTRACT = b"-" * 10
NO_MSP = b"-" * 16

RESULT_HEADER = "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
TOTAL_HEADER = "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"


class Fatal(Exception):
    """Any condition that aborts the batch with exit 2."""


def is_digits(field):
    """COBOL NUMERIC class test on PIC X: every byte is ASCII 0-9 (not str.isdigit)."""
    return len(field) > 0 and all(byte in DIGITS for byte in field)


def to_int(field):
    """Exact unsigned integer from bytes already checked by is_digits."""
    value = 0
    for byte in field:
        value = value * 10 + (byte - 0x30)
    return value


def is_spaces(field):
    return all(byte == SPACE for byte in field)


class Claim:
    """Fresh state for one record (COBOL: INITIALIZE claim-interface)."""

    __slots__ = ("record_no", "claim_id", "status", "reason", "charges", "gross", "primary",
                 "deductible", "coinsurance", "contract", "full", "mbi", "dos",
                 "payment", "cwf", "cwf_reason", "released")

    def __init__(self, record_no):
        self.record_no = record_no
        self.claim_id = "@%010d" % record_no
        self.status = "INVALID"
        self.reason = ""
        self.charges = self.gross = self.primary = self.deductible = self.coinsurance = 0
        self.contract = None
        self.full = b""
        self.mbi = b""
        self.dos = 0
        self.payment = 0
        self.cwf = "NOT_SENT"
        self.cwf_reason = "CLAIM_INVALID"
        self.released = 0


def valid_id(raw_id):
    """1-12 of A-Z 0-9 - _, left-justified, only trailing spaces (validate.cob lines 15-32)."""
    if is_spaces(raw_id):
        return False
    ended = False
    for byte in raw_id:
        if byte == SPACE:
            ended = True
        elif ended or byte not in ID_CHARS:
            return False
    return True


def validate(claim, line):
    """Validation in fixed precedence; first failure wins (cobol/validate.cob)."""
    claim.status = "INVALID"
    claim.reason = "BAD_LENGTH"
    if len(line) != RECORD_LENGTH:
        return
    raw_id = line[0:12]
    claim.reason = "BAD_ID"
    if not valid_id(raw_id):
        return
    claim.claim_id = raw_id.rstrip(b" ").decode("ascii")
    amounts = [line[12:22], line[22:32], line[32:42], line[42:52], line[52:62]]
    raw_contract = line[62:72]
    claim.reason = "BAD_AMOUNT"
    if not all(is_digits(field) for field in amounts):
        return
    if raw_contract != ABSENT_CONTRACT:
        if not is_digits(raw_contract):
            return
        claim.contract = to_int(raw_contract)
    claim.charges, claim.gross, claim.primary, claim.deductible, claim.coinsurance = map(to_int, amounts)
    claim.reason = "BAD_CONTRACT"
    if claim.contract is not None and claim.contract > claim.charges:
        return
    claim.full = line[72:73]
    claim.reason = "BAD_FLAG"
    if claim.full not in (b"Y", b"N"):
        return
    raw_mbi = line[73:84]
    claim.reason = "BAD_MBI"
    if not all(byte in MBI_CHARS for byte in raw_mbi):
        return
    raw_dos = line[84:92]
    claim.reason = "BAD_DATE"
    if not is_digits(raw_dos):
        return
    month, day = to_int(raw_dos[4:6]), to_int(raw_dos[6:8])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return
    claim.mbi = raw_mbi
    claim.dos = to_int(raw_dos)
    claim.status = "VALID"
    claim.reason = ""


def calculate_payment(claim):
    """calculate-prospective-payment (payment.cob 12-38): min(G, B) - max(D + K, P), floored at 0."""
    claim.payment = 0
    claim.status = "ZERO"
    if claim.full == b"Y":
        claim.reason = "PAYMENT_IN_FULL"
        return
    charge_basis = claim.charges
    if claim.contract is not None:
        charge_basis = claim.contract
    payment_cap = min(claim.gross, charge_basis)
    if claim.primary >= payment_cap:
        claim.reason = "PRIMARY_AT_CAP"
        return
    deductions = claim.deductible + claim.coinsurance
    if deductions >= payment_cap:
        claim.reason = "DEDUCTIONS_AT_CAP"
        return
    claim.payment = payment_cap - max(deductions, claim.primary)
    claim.status = "PAID"
    claim.reason = "SECONDARY_PAYABLE"


class CwfReference:
    """In-memory B (beneficiary) and H (posted claim) tables (cwf.cpy)."""

    def __init__(self):
        self.beneficiaries = {}  # mbi -> (from, to, msp or None); first B per MBI wins
        self.bene_count = 0
        self.history = set()     # (mbi, dos, charges)
        self.hist_count = 0

    def add(self, record):
        kind = record[0:1]
        mbi = record[1:12]
        if kind == b"B":
            if (not is_spaces(record[44:64]) or is_spaces(mbi) or not is_digits(record[12:28])
                    or self.bene_count >= MAX_CWF_ENTRIES):
                raise Fatal("invalid CWF reference record")
            msp_field = record[28:44]
            if msp_field == NO_MSP:
                msp = None
            elif is_digits(msp_field):
                msp = (to_int(msp_field[0:8]), to_int(msp_field[8:16]))
            else:
                raise Fatal("invalid CWF reference record")
            self.bene_count += 1
            self.beneficiaries.setdefault(mbi, (to_int(record[12:20]), to_int(record[20:28]), msp))
        elif kind == b"H":
            if (not is_spaces(record[30:64]) or is_spaces(mbi) or not is_digits(record[12:30])
                    or self.hist_count >= MAX_CWF_ENTRIES):
                raise Fatal("invalid CWF reference record")
            self.hist_count += 1
            self.history.add((mbi, to_int(record[12:20]), to_int(record[20:30])))
        else:
            raise Fatal("invalid CWF reference record")


def cwf_lines(chunks):
    """Emulate the GnuCOBOL 3.1.2 LINE SEQUENTIAL reader used for the CWF file.

    LF ends a line; every CR byte is dropped; bytes after the 64th are ignored; the
    record is space-padded to 64; a final unterminated line counts only if it has data.
    """
    current = bytearray()
    for chunk in chunks:
        start = 0
        while True:
            newline = chunk.find(b"\n", start)
            piece = chunk[start:] if newline < 0 else chunk[start:newline]
            if len(current) < CWF_RECORD:
                current += piece.replace(b"\r", b"")[:CWF_RECORD - len(current)]
            if newline < 0:
                break
            yield bytes(current).ljust(CWF_RECORD, b" ")
            current = bytearray()
            start = newline + 1
    if current:
        yield bytes(current).ljust(CWF_RECORD, b" ")


def read_chunks(fd, directory_is_empty=False):
    while True:
        try:
            chunk = os.read(fd, 65536)
        except IsADirectoryError:
            if directory_is_empty:  # GnuCOBOL sees immediate EOF on a directory CWF path
                return
            raise Fatal("input read failed")
        except OSError as exc:
            raise Fatal(f"read failed: {exc.strerror}")
        if not chunk:
            return
        yield chunk


def open_read(name):
    if not name:
        raise Fatal("empty file name")
    try:
        return os.open(name, os.O_RDONLY)
    except OSError as exc:
        raise Fatal(f"cannot open {os.fsdecode(name)}: {exc.strerror}")


def load_cwf(name):
    reference = CwfReference()
    fd = open_read(name)
    try:
        for record in cwf_lines(read_chunks(fd, directory_is_empty=True)):
            reference.add(record)
    finally:
        os.close(fd)
    return reference


def cwf_check(claim, reference):
    """check-claim (cwf.cob 17-52): entitlement, duplicate, MSP primary not billed."""
    claim.released = 0
    claim.cwf = "REJECTED"
    claim.cwf_reason = "NOT_ENTITLED"
    beneficiary = reference.beneficiaries.get(claim.mbi)
    if beneficiary is None:
        return
    entitled_from, entitled_to, msp = beneficiary
    if claim.dos < entitled_from or claim.dos > entitled_to:
        return
    claim.cwf_reason = "DUPLICATE"
    if (claim.mbi, claim.dos, claim.charges) in reference.history:
        return
    claim.cwf_reason = "MSP_PRIMARY_NOT_BILLED"
    if msp is not None and msp[0] <= claim.dos <= msp[1] and claim.primary == 0:
        return
    claim.cwf = "ACCEPTED"
    claim.cwf_reason = "DISPOSITION_01"
    claim.released = claim.payment


def finish_line(buffer):
    """Remove one trailing CR, then enforce the 4,096-byte transport bound."""
    if buffer and buffer[-1] == 0x0D:
        del buffer[-1]
    if len(buffer) > MAX_LINE:
        raise Fatal("input line exceeds 4096 bytes")
    return bytes(buffer)


def input_lines(chunks):
    """Raw byte framing (batch.cob 94-135). A blank line is a record; EOF flushes a partial line."""
    buffer = bytearray()
    for chunk in chunks:
        start = 0
        while True:
            newline = chunk.find(b"\n", start)
            piece = chunk[start:] if newline < 0 else chunk[start:newline]
            if len(buffer) + len(piece) > MAX_BUFFER:
                raise Fatal("input line exceeds 4096 bytes")
            buffer += piece
            if newline < 0:
                break
            yield finish_line(buffer)
            buffer = bytearray()
            start = newline + 1
    if buffer:
        yield finish_line(buffer)


def result_row(claim):
    return "%010d,%s,%s,%010d,%s,%s,%s,%010d\n" % (
        claim.record_no, claim.claim_id, claim.status, claim.payment, claim.reason,
        claim.cwf, claim.cwf_reason, claim.released)


class Totals:
    def __init__(self):
        self.records = self.paid = self.zero = self.invalid = 0
        self.accepted = self.rejected = 0
        self.payment_cents = self.released_cents = 0

    def add(self, claim):
        if claim.cwf == "ACCEPTED":
            self.accepted += 1
        elif claim.cwf == "REJECTED":
            self.rejected += 1
        self.released_cents += claim.released
        if claim.status == "PAID":
            self.paid += 1
        elif claim.status == "ZERO":
            self.zero += 1
        else:
            self.invalid += 1
        self.payment_cents += claim.payment

    def row(self):
        return "%010d,%010d,%010d,%010d,%015d,%010d,%010d,%015d\n" % (
            self.records, self.paid, self.zero, self.invalid, self.payment_cents,
            self.accepted, self.rejected, self.released_cents)


def process_line(line, totals, seen_ids, reference):
    if totals.records >= MAX_RECORDS:
        raise Fatal("batch exceeds 10000 records")
    totals.records += 1
    claim = Claim(totals.records)
    validate(claim, line)
    if not claim.claim_id.startswith("@"):
        if claim.claim_id in seen_ids:
            raise Fatal(f"duplicate claim ID: {claim.claim_id}")
        seen_ids.add(claim.claim_id)
    if claim.status == "VALID":
        calculate_payment(claim)
    if claim.status in ("PAID", "ZERO"):
        cwf_check(claim, reference)
    else:
        claim.cwf, claim.cwf_reason = "NOT_SENT", "CLAIM_INVALID"
    totals.add(claim)
    return claim


def path_name(argument):
    """The COBOL program receives each path in a 1,024-byte space-padded field."""
    return os.fsencode(argument)[:PATH_FIELD].rstrip(b" ")


def open_write(name):
    if not name:
        raise Fatal("empty file name")
    try:
        return open(name, "wb")
    except OSError as exc:
        raise Fatal(f"cannot open {os.fsdecode(name)}: {exc.strerror}")


def run(arguments):
    if len(arguments) != 4:
        print("usage: msp-batch INPUT CWF OUTPUT TOTALS", file=sys.stderr)
        return 2
    input_name, cwf_name, output_name, totals_name = (path_name(a) for a in arguments)
    if len({input_name, cwf_name, output_name, totals_name}) != 4:
        print("paths must be distinct", file=sys.stderr)
        return 2
    files = []
    try:
        reference = load_cwf(cwf_name)
        input_fd = open_read(input_name)
        files.append(input_fd)
        results = open_write(output_name)
        files.append(results)
        totals_file = open_write(totals_name)
        files.append(totals_file)
        results.write((RESULT_HEADER + "\n").encode("ascii"))
        totals, seen_ids = Totals(), set()
        for line in input_lines(read_chunks(input_fd)):
            claim = process_line(line, totals, seen_ids, reference)
            results.write(result_row(claim).encode("ascii"))
        totals_file.write((TOTAL_HEADER + "\n" + totals.row()).encode("ascii"))
        close_all(files)
        return 0
    except Fatal as exc:
        print(str(exc), file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"unexpected failure: {exc}", file=sys.stderr)
    print("fatal batch failure; discard outputs", file=sys.stderr)
    try:
        close_all(files)
    except (Fatal, OSError):
        pass
    return 2


def close_all(files):
    """Close in COBOL order (input, results, totals); a failing close is fatal."""
    error = None
    while files:
        item = files.pop(0)
        try:
            if isinstance(item, int):
                os.close(item)
            else:
                item.close()
        except OSError as exc:
            error = exc
    if error is not None:
        raise Fatal(f"close failed: {error.strerror}")


def main():
    try:
        return run(sys.argv[1:])
    except Exception as exc:  # no exit code other than 0 or 2 is part of the contract
        print(f"fatal batch failure; discard outputs ({exc})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
