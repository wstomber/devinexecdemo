#!/usr/bin/env python3
"""MSP secondary payment and synthetic CWF pre-payment check.

Python port of cobol/batch.cob, validate.cob, payment.cob and cwf.cob.
Usage: msp.py INPUT CWF OUTPUT TOTALS. Standard library only; integer cents.
Exit 0 = batch succeeded (records may be INVALID); exit 2 = fatal, discard outputs.
"""
import sys
from dataclasses import dataclass
from typing import Optional

RECORD_LENGTH = 92
MAX_LINE_BYTES = 4096
MAX_RECORDS = 10000
MAX_CWF_ENTRIES = 1000
CWF_RECORD_BYTES = 64
ABSENT_CONTRACT = b"-" * 10
NO_MSP_PERIOD = b"-" * 16

# Explicit ASCII sets: str.isdigit()/int() would accept '+', ' ', '_' and Unicode digits.
DIGITS = frozenset(b"0123456789")
ID_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
MBI_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
SPACE = 0x20

RESULT_HEADER = "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"


class Fatal(Exception):
    """Batch-level failure: exit 2, outputs must be discarded."""


@dataclass
class Claim:
    record_no: int
    claim_id: str
    status: str = "INVALID"
    reason: str = "BAD_LENGTH"
    charges: int = 0
    gross: int = 0
    primary: int = 0
    deductible: int = 0
    coinsurance: int = 0
    contract: Optional[int] = None
    full: bytes = b""
    mbi: bytes = b""
    dos: int = 0
    payment: int = 0
    cwf: str = "NOT_SENT"
    cwf_reason: str = "CLAIM_INVALID"
    released: int = 0


@dataclass
class Beneficiary:
    entitled_from: int
    entitled_to: int
    msp_from: Optional[int]
    msp_to: Optional[int]


@dataclass
class CwfReference:
    beneficiaries: dict
    history: set


def is_numeric(field: bytes) -> bool:
    return len(field) > 0 and all(b in DIGITS for b in field)


def digits_value(field: bytes) -> int:
    """Only call after is_numeric(field)."""
    value = 0
    for b in field:
        value = value * 10 + (b - 0x30)
    return value


def valid_id(raw_id: bytes) -> bool:
    """1-12 allowed bytes, left-justified; nothing but spaces after the first space."""
    if all(b == SPACE for b in raw_id):
        return False
    ended = False
    for b in raw_id:
        if b == SPACE:
            ended = True
        elif ended or b not in ID_BYTES:
            return False
    return True


def validate_record(line: bytes, record_no: int) -> Claim:
    """validate-record: first failure wins (length, ID, amounts, contract, flag, MBI, date)."""
    claim = Claim(record_no=record_no, claim_id=f"@{record_no:010d}")
    if len(line) != RECORD_LENGTH:
        return claim
    claim.reason = "BAD_ID"
    raw_id = line[0:12]
    if not valid_id(raw_id):
        return claim
    claim.claim_id = raw_id.rstrip(b" ").decode("ascii")
    claim.reason = "BAD_AMOUNT"
    amounts = [line[12:22], line[22:32], line[32:42], line[42:52], line[52:62]]
    if not all(is_numeric(a) for a in amounts):
        return claim
    raw_contract = line[62:72]
    if raw_contract != ABSENT_CONTRACT:
        if not is_numeric(raw_contract):
            return claim
        claim.contract = digits_value(raw_contract)
    claim.charges, claim.gross, claim.primary, claim.deductible, claim.coinsurance = map(digits_value, amounts)
    claim.reason = "BAD_CONTRACT"
    if claim.contract is not None and claim.contract > claim.charges:
        return claim
    claim.reason = "BAD_FLAG"
    claim.full = line[72:73]
    if claim.full not in (b"Y", b"N"):
        return claim
    claim.reason = "BAD_MBI"
    mbi = line[73:84]
    if not all(b in MBI_BYTES for b in mbi):
        return claim
    claim.reason = "BAD_DATE"
    dos = line[84:92]
    if not is_numeric(dos):
        return claim
    if not b"01" <= dos[4:6] <= b"12" or not b"01" <= dos[6:8] <= b"31":
        return claim
    claim.mbi, claim.dos = mbi, digits_value(dos)
    claim.status, claim.reason = "VALID", ""
    return claim


def calculate_payment(claim: Claim) -> None:
    """calculate-prospective-payment: max(0, min(G, B) - max(T, P)) with ordered zero reasons."""
    claim.payment, claim.status = 0, "ZERO"
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


def cwf_check(claim: Claim, reference: CwfReference) -> None:
    """check-claim: entitlement, duplicate of posted history, MSP primary not billed."""
    claim.released, claim.cwf = 0, "REJECTED"
    claim.cwf_reason = "NOT_ENTITLED"
    bene = reference.beneficiaries.get(claim.mbi)
    if bene is None or not bene.entitled_from <= claim.dos <= bene.entitled_to:
        return
    claim.cwf_reason = "DUPLICATE"
    if (claim.mbi, claim.dos, claim.charges) in reference.history:
        return
    claim.cwf_reason = "MSP_PRIMARY_NOT_BILLED"
    if bene.msp_from is not None and bene.msp_from <= claim.dos <= bene.msp_to and claim.primary == 0:
        return
    claim.cwf, claim.cwf_reason = "ACCEPTED", "DISPOSITION_01"
    claim.released = claim.payment


def cwf_records(data: bytes):
    """GnuCOBOL LINE SEQUENTIAL read of pic x(64): CR bytes dropped, excess truncated, space padded."""
    segments = data.split(b"\n")
    last = segments.pop()
    if last.replace(b"\r", b""):
        segments.append(last)
    for segment in segments:
        yield segment.replace(b"\r", b"")[:CWF_RECORD_BYTES].ljust(CWF_RECORD_BYTES, b" ")


def parse_cwf(data: bytes) -> CwfReference:
    """load-cwf / parse-cwf. Any malformed record is fatal."""
    beneficiaries, history = {}, set()
    bene_count = hist_count = 0
    for rec in cwf_records(data):
        kind = rec[0:1]
        if kind == b"B":
            if (rec[44:64] != b" " * 20 or rec[1:12] == b" " * 11 or not is_numeric(rec[12:28])
                    or bene_count >= MAX_CWF_ENTRIES):
                raise Fatal("invalid CWF reference record")
            bene_count += 1
            if rec[28:44] == NO_MSP_PERIOD:
                msp_from = msp_to = None
            elif is_numeric(rec[28:44]):
                msp_from, msp_to = digits_value(rec[28:36]), digits_value(rec[36:44])
            else:
                raise Fatal("invalid CWF reference record")
            # The COBOL lookup stops at the first matching MBI.
            beneficiaries.setdefault(rec[1:12], Beneficiary(digits_value(rec[12:20]), digits_value(rec[20:28]),
                                                            msp_from, msp_to))
        elif kind == b"H":
            if (rec[30:64] != b" " * 34 or rec[1:12] == b" " * 11 or not is_numeric(rec[12:30])
                    or hist_count >= MAX_CWF_ENTRIES):
                raise Fatal("invalid CWF reference record")
            hist_count += 1
            history.add((rec[1:12], digits_value(rec[12:20]), digits_value(rec[20:30])))
        else:
            raise Fatal("invalid CWF reference record")
    return CwfReference(beneficiaries, history)


def input_lines(data: bytes):
    """Byte framing of main/finish-line: LF ends a line, one trailing CR removed, 4,096-byte bound."""
    start, size = 0, len(data)
    while start < size:
        end = data.find(b"\n", start)
        if end < 0:
            end = size
        line = data[start:end]
        if line.endswith(b"\r"):
            line = line[:-1]
        if len(line) > MAX_LINE_BYTES:
            raise Fatal("input line exceeds 4096 bytes")
        yield line
        start = end + 1


def result_row(claim: Claim) -> str:
    return (f"{claim.record_no:010d},{claim.claim_id},{claim.status},{claim.payment:010d},{claim.reason},"
            f"{claim.cwf},{claim.cwf_reason},{claim.released:010d}\n")


class Batch:
    def __init__(self, reference: CwfReference):
        self.reference = reference
        self.seen_ids = set()
        self.records = self.paid = self.zero = self.invalid = 0
        self.accepted = self.rejected = 0
        self.payment_total = self.released_total = 0

    def process(self, line: bytes) -> Claim:
        """process-record: a fresh Claim per record is the INITIALIZE reset."""
        if self.records >= MAX_RECORDS:
            raise Fatal("batch exceeds 10000 records")
        self.records += 1
        claim = validate_record(line, self.records)
        if not claim.claim_id.startswith("@"):
            if claim.claim_id in self.seen_ids:
                raise Fatal(f"duplicate claim ID: {claim.claim_id}")
            self.seen_ids.add(claim.claim_id)
        if claim.status == "VALID":
            calculate_payment(claim)
        if claim.status in ("PAID", "ZERO"):
            cwf_check(claim, self.reference)
        if claim.cwf == "ACCEPTED":
            self.accepted += 1
        elif claim.cwf == "REJECTED":
            self.rejected += 1
        self.released_total += claim.released
        if claim.status == "PAID":
            self.paid += 1
        elif claim.status == "ZERO":
            self.zero += 1
        else:
            self.invalid += 1
        self.payment_total += claim.payment
        return claim

    def totals_row(self) -> str:
        return (f"{self.records:010d},{self.paid:010d},{self.zero:010d},{self.invalid:010d},"
                f"{self.payment_total:015d},{self.accepted:010d},{self.rejected:010d},"
                f"{self.released_total:015d}\n")


def run(argv) -> int:
    if len(argv) != 4:
        print("usage: msp-batch INPUT CWF OUTPUT TOTALS", file=sys.stderr)
        return 2
    input_path, cwf_path, output_path, totals_path = argv
    if len(set(argv)) != 4:
        print("paths must be distinct", file=sys.stderr)
        return 2
    results = totals = None
    try:
        try:
            with open(cwf_path, "rb") as stream:
                reference = parse_cwf(stream.read())
            with open(input_path, "rb") as stream:
                data = stream.read()
            # Outputs are opened (and truncated) only after CWF and input open, like the COBOL.
            results = open(output_path, "w", encoding="ascii", newline="\n")
            totals = open(totals_path, "w", encoding="ascii", newline="\n")
            results.write(RESULT_HEADER + "\n")
            batch = Batch(reference)
            for line in input_lines(data):
                results.write(result_row(batch.process(line)))
            totals.write(TOTALS_HEADER + "\n")
            totals.write(batch.totals_row())
        finally:
            for stream in (results, totals):
                if stream is not None:
                    stream.close()
    except (Fatal, OSError) as exc:
        print(f"{exc}\nfatal batch failure; discard outputs", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
