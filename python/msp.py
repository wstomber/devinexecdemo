"""MSP secondary-payment batch: Python migration of cobol/batch.cob, validate.cob, payment.cob.

Usage: python3 python/msp.py INPUT OUTPUT TOTALS

Synthetic educational module (CMS Pub. 100-05 Ch. 5 §§40.8-40.8.3 subset). Standard
library only. Money is always int cents; there is no float anywhere in this file.
"""
import sys
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Optional, TextIO

RECORD_LENGTH = 73
MAX_LINE_BYTES = 4096
MAX_RECORDS = 10000
ABSENT_CONTRACT = b"-" * 10
DIGITS = frozenset(b"0123456789")
ID_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
RESULTS_HEADER = "record_no,claim_id,status,payment_cents,reason"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents"

# Byte slices of the 73-byte record (claim.cpy claim-raw), 0-based half-open.
ID, CHARGES, GROSS, PRIMARY = slice(0, 12), slice(12, 22), slice(22, 32), slice(32, 42)
DEDUCTIBLE, COINSURANCE, CONTRACT, FULL = slice(42, 52), slice(52, 62), slice(62, 72), slice(72, 73)


class FatalBatchError(Exception):
    """Abort the whole batch with exit 2 (COBOL paragraph fatal-io)."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    charges: int
    gross: int
    primary: int
    deductible: int
    coinsurance: int
    contract: Optional[int]
    full: bool


@dataclass(frozen=True)
class Outcome:
    claim_id: str
    status: str
    reason: str
    payment_cents: int


def is_numeric(field: bytes) -> bool:
    """COBOL `IS NUMERIC` on PIC X: every byte an ASCII digit. Not str.isdigit()/int()."""
    return len(field) > 0 and all(b in DIGITS for b in field)


def valid_id(raw_id: bytes) -> bool:
    """1-12 of A-Z 0-9 - _, left-justified, right-padded with spaces only."""
    ended = False
    for b in raw_id:
        if b == 0x20:
            ended = True
        elif ended or b not in ID_BYTES:
            return False
    return raw_id[:1] != b" " and len(raw_id) == 12


def validate_record(record: bytes):
    """Return (claim_id or None, Claim or None, reason or None) in validate-record order.

    claim_id is None when the record is not identifiable (BAD_LENGTH / BAD_ID).
    """
    if len(record) != RECORD_LENGTH:
        return None, None, "BAD_LENGTH"
    raw_id = record[ID]
    if not valid_id(raw_id):
        return None, None, "BAD_ID"
    claim_id = raw_id.decode("ascii").rstrip(" ")
    required = (record[CHARGES], record[GROSS], record[PRIMARY], record[DEDUCTIBLE], record[COINSURANCE])
    if not all(is_numeric(f) for f in required):
        return claim_id, None, "BAD_AMOUNT"
    raw_contract = record[CONTRACT]
    if raw_contract == ABSENT_CONTRACT:
        contract = None
    elif is_numeric(raw_contract):
        contract = int(raw_contract)
    else:
        return claim_id, None, "BAD_AMOUNT"
    charges, gross, primary, deductible, coinsurance = (int(f) for f in required)
    if contract is not None and contract > charges:
        return claim_id, None, "BAD_CONTRACT"
    flag = record[FULL]
    if flag not in (b"Y", b"N"):
        return claim_id, None, "BAD_FLAG"
    return claim_id, Claim(claim_id, charges, gross, primary, deductible, coinsurance,
                           contract, flag == b"Y"), None


def calculate_payment(claim: Claim):
    """calculate-prospective-payment: (status, reason, payment_cents).

    payment = max(0, min(G, B) - max(D + K, P)), B = OTAF if supplied else charges,
    with zero-reason precedence PAYMENT_IN_FULL, PRIMARY_AT_CAP, DEDUCTIONS_AT_CAP.
    """
    if claim.full:
        return "ZERO", "PAYMENT_IN_FULL", 0
    charge_basis = claim.contract if claim.contract is not None else claim.charges
    payment_cap = min(claim.gross, charge_basis)
    if claim.primary >= payment_cap:
        return "ZERO", "PRIMARY_AT_CAP", 0
    deductions = claim.deductible + claim.coinsurance
    if deductions >= payment_cap:
        return "ZERO", "DEDUCTIONS_AT_CAP", 0
    return "PAID", "SECONDARY_PAYABLE", payment_cap - max(deductions, claim.primary)


def provisional_id(record_no: int) -> str:
    return f"@{record_no:010d}"


def process_record(record: bytes, record_no: int):
    """Return (identifiable claim ID or None, Outcome). Each call starts from fresh state."""
    claim_id, claim, reason = validate_record(record)
    shown_id = claim_id if claim_id is not None else provisional_id(record_no)
    if claim is None:
        return claim_id, Outcome(shown_id, "INVALID", reason, 0)
    status, reason, cents = calculate_payment(claim)
    return claim_id, Outcome(shown_id, status, reason, cents)


def iter_records(stream: BinaryIO, chunk_size: int = 65536) -> Iterator[bytes]:
    """Split on LF, drop one trailing CR, enforce the 4,096-byte line limit.

    A blank line is a (zero-length) record; a final line without LF is still a record.
    """
    pending = bytearray()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        start = 0
        while True:
            newline = chunk.find(b"\n", start)
            if newline < 0:
                pending += chunk[start:]
                if len(pending) > MAX_LINE_BYTES + 1:
                    raise FatalBatchError(f"input line exceeds {MAX_LINE_BYTES} bytes")
                break
            pending += chunk[start:newline]
            yield _finish_line(pending)
            pending = bytearray()
            start = newline + 1
    if pending:
        yield _finish_line(pending)


def _finish_line(line: bytearray) -> bytes:
    if line.endswith(b"\r"):
        del line[-1]
    if len(line) > MAX_LINE_BYTES:
        raise FatalBatchError(f"input line exceeds {MAX_LINE_BYTES} bytes")
    return bytes(line)


def format_result(record_no: int, outcome: Outcome) -> str:
    return (f"{record_no:010d},{outcome.claim_id},{outcome.status},"
            f"{outcome.payment_cents:010d},{outcome.reason}")


def format_totals(totals: dict) -> str:
    return (f"{totals['records']:010d},{totals['paid']:010d},{totals['zero']:010d},"
            f"{totals['invalid']:010d},{totals['payment_cents']:015d}")


def run_batch(source: BinaryIO, results: TextIO) -> dict:
    """Process every record, writing result rows; return the batch totals."""
    totals = {"records": 0, "paid": 0, "zero": 0, "invalid": 0, "payment_cents": 0}
    seen = set()
    results.write(RESULTS_HEADER + "\n")
    for record in iter_records(source):
        if totals["records"] >= MAX_RECORDS:
            raise FatalBatchError(f"batch exceeds {MAX_RECORDS} records")
        totals["records"] += 1
        record_no = totals["records"]
        claim_id, outcome = process_record(record, record_no)
        if claim_id is not None:
            if claim_id in seen:
                raise FatalBatchError(f"duplicate claim ID: {claim_id}")
            seen.add(claim_id)
        totals[outcome.status.lower()] += 1
        totals["payment_cents"] += outcome.payment_cents
        results.write(format_result(record_no, outcome) + "\n")
    return totals


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print("usage: msp.py INPUT OUTPUT TOTALS", file=sys.stderr)
        return 2
    input_path, output_path, totals_path = args
    if len({input_path, output_path, totals_path}) != 3:
        print("paths must be distinct", file=sys.stderr)
        return 2
    try:
        with open(input_path, "rb") as source, \
                open(output_path, "w", encoding="ascii", newline="\n") as results, \
                open(totals_path, "w", encoding="ascii", newline="\n") as totals_file:
            totals = run_batch(source, results)
            totals_file.write(TOTALS_HEADER + "\n" + format_totals(totals) + "\n")
    except FatalBatchError as exc:
        print(f"{exc}; fatal batch failure; discard outputs", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"fatal batch failure; discard outputs: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
