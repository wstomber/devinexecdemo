#!/usr/bin/env python3
"""Medicare Secondary Payer prospective-payment batch: Python replacement for cobol/.

Usage: python3 python/msp.py [--summary-json PATH] INPUT CWF OUTPUT TOTALS

Synthetic educational module derived from CMS Pub. 100-05 Ch. 5 §§40.8-40.8.3.
All money is integer cents (Python int); binary floating point is never used.
The record contract, reason codes and exit codes are the demo interface in README.md.
A requested summary JSON is written atomically only after successful CSV output.
"""
import json
import os
import sys
import tempfile
from dataclasses import dataclass, replace
from typing import Iterator, Optional

RECORD_LENGTH = 92
MAX_LINE_BYTES = 4096
MAX_RECORDS = 10_000
ABSENT_CONTRACT = b"----------"
ID_CHARACTERS = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
DIGITS = frozenset(b"0123456789")
RESULTS_HEADER = "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"
MBI_CHARACTERS = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
CWF_RECORD_BYTES = 64
MAX_CWF_ENTRIES = 1000

# Byte slices of the 92-byte record (README "Positions" table, 0-based here).
ID_FIELD = slice(0, 12)
AMOUNT_FIELDS = {"charges": slice(12, 22), "gross": slice(22, 32), "primary": slice(32, 42),
                 "deductible": slice(42, 52), "coinsurance": slice(52, 62)}
CONTRACT_FIELD = slice(62, 72)
FULL_FLAG = slice(72, 73)
MBI_FIELD = slice(73, 84)
DOS_FIELD = slice(84, 92)


class FatalBatchError(Exception):
    """Batch-level failure: caller must discard any partial outputs (exit 2)."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    charges: int
    gross: int
    primary: int
    deductible: int
    coinsurance: int
    contract: Optional[int]
    paid_in_full: bool
    mbi: str = ""
    dos: int = 0


@dataclass(frozen=True)
class Result:
    claim_id: str
    status: str
    payment_cents: int
    reason: str
    cwf: str = "NOT_SENT"
    cwf_reason: str = "CLAIM_INVALID"
    released_cents: int = 0


@dataclass(frozen=True)
class Beneficiary:
    entitled_from: int
    entitled_to: int
    msp_period: Optional[tuple]


@dataclass(frozen=True)
class CwfReference:
    """What the CWF Host knows (cwf.cpy tables): entitlement/MSP periods and posted claims."""
    beneficiaries: dict
    history: frozenset


def read_records(stream) -> Iterator[bytes]:
    """Yield physical lines without LF and one trailing CR (batch.cob read loop + finish-line).

    A blank line is a record; a final line without LF is a record; an empty file has none.
    """
    line = bytearray()
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        start = 0
        while True:
            newline = chunk.find(b"\n", start)
            piece = chunk[start:] if newline < 0 else chunk[start:newline]
            line += piece
            if len(line) > MAX_LINE_BYTES + 1:
                raise FatalBatchError(f"input line exceeds {MAX_LINE_BYTES} bytes")
            if newline < 0:
                break
            yield finish_line(line)
            line = bytearray()
            start = newline + 1
    if line:
        yield finish_line(line)


def finish_line(line: bytearray) -> bytes:
    if line.endswith(b"\r"):
        del line[-1]
    if len(line) > MAX_LINE_BYTES:
        raise FatalBatchError(f"input line exceeds {MAX_LINE_BYTES} bytes")
    return bytes(line)


def is_numeric(field: bytes) -> bool:
    """COBOL NUMERIC class test on PIC X: every byte is an ASCII digit (no sign, point or space)."""
    return bool(field) and all(byte in DIGITS for byte in field)


def valid_claim_id(field: bytes) -> bool:
    """1-12 of A-Z 0-9 - _, left-justified, right-padded with spaces only (validate-record loop)."""
    text = field.rstrip(b" ")
    return bool(text) and all(byte in ID_CHARACTERS for byte in text)


def invalid(claim_id: str, reason: str) -> Result:
    return Result(claim_id, "INVALID", 0, reason)


def validate(record: bytes, record_no: int):
    """Return (Claim, None) or (None, invalid Result), in validate-record precedence order."""
    provisional_id = f"@{record_no:010d}"
    if len(record) != RECORD_LENGTH:
        return None, invalid(provisional_id, "BAD_LENGTH")
    if not valid_claim_id(record[ID_FIELD]):
        return None, invalid(provisional_id, "BAD_ID")
    claim_id = record[ID_FIELD].rstrip(b" ").decode("ascii")
    raw_contract = record[CONTRACT_FIELD]
    if not all(is_numeric(record[f]) for f in AMOUNT_FIELDS.values()):
        return None, invalid(claim_id, "BAD_AMOUNT")
    if raw_contract != ABSENT_CONTRACT and not is_numeric(raw_contract):
        return None, invalid(claim_id, "BAD_AMOUNT")
    amounts = {name: int(record[f]) for name, f in AMOUNT_FIELDS.items()}
    contract = None if raw_contract == ABSENT_CONTRACT else int(raw_contract)
    if contract is not None and contract > amounts["charges"]:
        return None, invalid(claim_id, "BAD_CONTRACT")
    flag = record[FULL_FLAG]
    if flag not in (b"Y", b"N"):
        return None, invalid(claim_id, "BAD_FLAG")
    mbi = record[MBI_FIELD]
    if not all(byte in MBI_CHARACTERS for byte in mbi):
        return None, invalid(claim_id, "BAD_MBI")
    dos = record[DOS_FIELD]
    if not is_numeric(dos) or not (b"01" <= dos[4:6] <= b"12") or not (b"01" <= dos[6:8] <= b"31"):
        return None, invalid(claim_id, "BAD_DATE")
    return Claim(claim_id, contract=contract, paid_in_full=flag == b"Y", mbi=mbi.decode("ascii"),
                 dos=int(dos), **amounts), None


def load_cwf(path: str) -> CwfReference:
    """batch.cob load-cwf/parse-cwf: B and H records; any malformed record is fatal."""
    try:
        with open(path, "rb") as stream:
            data = stream.read()
    except OSError as exc:
        raise FatalBatchError(f"cannot open CWF reference: {exc}") from exc
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    beneficiaries, history, posted = {}, set(), 0
    for line in lines:
        line = line.rstrip(b"\r")
        if len(line) > CWF_RECORD_BYTES:
            raise FatalBatchError("invalid CWF reference record")
        line = line.ljust(CWF_RECORD_BYTES)
        kind, mbi = line[:1], line[1:12]
        if kind == b"B":
            if line[44:].strip(b" ") or not mbi.strip(b" ") or not is_numeric(line[12:28]) \
                    or posted_count(beneficiaries) >= MAX_CWF_ENTRIES:
                raise FatalBatchError("invalid CWF reference record")
            msp = line[28:44]
            if msp == b"-" * 16:
                period = None
            elif is_numeric(msp):
                period = (int(msp[:8]), int(msp[8:]))
            else:
                raise FatalBatchError("invalid CWF reference record")
            beneficiaries.setdefault(mbi.decode("ascii"), []).append(
                Beneficiary(int(line[12:20]), int(line[20:28]), period))
        elif kind == b"H":
            if line[30:].strip(b" ") or not mbi.strip(b" ") or not is_numeric(line[12:30]) \
                    or posted >= MAX_CWF_ENTRIES:
                raise FatalBatchError("invalid CWF reference record")
            posted += 1
            history.add((mbi.decode("ascii"), int(line[12:20]), int(line[20:30])))
        else:
            raise FatalBatchError("invalid CWF reference record")
    # The COBOL table search stops at the first entry for an MBI.
    first = {mbi: entries[0] for mbi, entries in beneficiaries.items()}
    return CwfReference(first, frozenset(history))


def posted_count(beneficiaries: dict) -> int:
    return sum(len(entries) for entries in beneficiaries.values())


def cwf_check(claim: Claim, result: Result, reference: CwfReference) -> Result:
    """cwf.cob cwf-check: first failure wins; only an accepted claim releases its payment."""
    beneficiary = reference.beneficiaries.get(claim.mbi)
    if beneficiary is None or not beneficiary.entitled_from <= claim.dos <= beneficiary.entitled_to:
        return replace(result, cwf="REJECTED", cwf_reason="NOT_ENTITLED", released_cents=0)
    if (claim.mbi, claim.dos, claim.charges) in reference.history:
        return replace(result, cwf="REJECTED", cwf_reason="DUPLICATE", released_cents=0)
    msp = beneficiary.msp_period
    if msp is not None and msp[0] <= claim.dos <= msp[1] and claim.primary == 0:
        return replace(result, cwf="REJECTED", cwf_reason="MSP_PRIMARY_NOT_BILLED", released_cents=0)
    return replace(result, cwf="ACCEPTED", cwf_reason="DISPOSITION_01", released_cents=result.payment_cents)


def charge_basis(claim: Claim) -> int:
    """§40.8.2: a lower obligatory acceptance amount (OTAF) is treated as the charges."""
    return claim.charges if claim.contract is None else claim.contract


def payment_cap(claim: Claim) -> int:
    return min(claim.gross, charge_basis(claim))


def calculate(claim: Claim) -> Result:
    """§40.8/§40.8.3 A: min(G-P, G-T, B-P, B-T) floored at 0; reason precedence per demo interface.

    min(G,B) - max(T,P) equals the lowest of the four limits whenever both are below the cap.
    """
    if claim.paid_in_full:
        return Result(claim.claim_id, "ZERO", 0, "PAYMENT_IN_FULL")
    cap = payment_cap(claim)
    if claim.primary >= cap:
        return Result(claim.claim_id, "ZERO", 0, "PRIMARY_AT_CAP")
    deductions = claim.deductible + claim.coinsurance
    if deductions >= cap:
        return Result(claim.claim_id, "ZERO", 0, "DEDUCTIONS_AT_CAP")
    return Result(claim.claim_id, "PAID", cap - max(deductions, claim.primary), "SECONDARY_PAYABLE")


class Batch:
    """Per-batch identity tracking and totals (batch.cob process-record and main)."""

    def __init__(self, reference: CwfReference):
        self.reference = reference
        self.records = self.paid = self.zero = self.invalid = self.payment_cents = 0
        self.accepted = self.rejected = self.released_cents = 0
        self.seen_ids = set()

    def process(self, record: bytes) -> Result:
        if self.records >= MAX_RECORDS:
            raise FatalBatchError(f"batch exceeds {MAX_RECORDS} records")
        self.records += 1
        claim, result = validate(record, self.records)
        identity = claim.claim_id if claim else result.claim_id
        if not identity.startswith("@"):
            if identity in self.seen_ids:
                raise FatalBatchError(f"duplicate claim ID: {identity}")
            self.seen_ids.add(identity)
        if claim:
            result = cwf_check(claim, calculate(claim), self.reference)
        if result.cwf == "ACCEPTED":
            self.accepted += 1
        elif result.cwf == "REJECTED":
            self.rejected += 1
        self.released_cents += result.released_cents
        if result.status == "PAID":
            self.paid += 1
        elif result.status == "ZERO":
            self.zero += 1
        else:
            self.invalid += 1
        self.payment_cents += result.payment_cents
        return result

    def totals_row(self) -> str:
        return (f"{self.records:010d},{self.paid:010d},{self.zero:010d},"
                f"{self.invalid:010d},{self.payment_cents:015d},{self.accepted:010d},"
                f"{self.rejected:010d},{self.released_cents:015d}")

    def summary(self) -> dict:
        return {
            "records": self.records,
            "paid": self.paid,
            "zero": self.zero,
            "invalid": self.invalid,
            "payment_cents": self.payment_cents,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "released_cents": self.released_cents,
        }


def result_row(record_no: int, result: Result) -> str:
    return f"{record_no:010d},{result.claim_id},{result.status},{result.payment_cents:010d},{result.reason}," \
           f"{result.cwf},{result.cwf_reason},{result.released_cents:010d}"


def open_output(path: str):
    try:
        return open(path, "w", encoding="ascii", newline="\n")
    except OSError as exc:
        raise FatalBatchError(f"cannot open output: {exc}") from exc


def write_summary(path: str, summary: dict) -> None:
    temporary_path = None
    file_descriptor = None
    try:
        file_descriptor, temporary_path = tempfile.mkstemp(
            dir=os.path.dirname(os.path.abspath(path)),
            prefix="." + os.path.basename(path) + ".",
            suffix=".tmp",
        )
        with os.fdopen(file_descriptor, "w", encoding="ascii", newline="\n") as temporary:
            file_descriptor = None
            temporary.write(json.dumps(summary) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        if file_descriptor is not None:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
        raise FatalBatchError(f"cannot write summary JSON: {exc}") from exc


def run(input_path: str, cwf_path: str, output_path: str, totals_path: str, summary_path=None) -> None:
    batch = Batch(load_cwf(cwf_path))
    try:
        source = open(input_path, "rb")
    except OSError as exc:
        raise FatalBatchError(f"cannot open input: {exc}") from exc
    with source:
        output = open_output(output_path)
        with output:
            totals = open_output(totals_path)
            with totals:
                output.write(RESULTS_HEADER + "\n")
                for record in read_records(source):
                    output.write(result_row(batch.records + 1, batch.process(record)) + "\n")
                totals.write(TOTALS_HEADER + "\n" + batch.totals_row() + "\n")
    if summary_path is not None:
        write_summary(summary_path, batch.summary())


def parse_args(args):
    positionals = []
    summary_path = None
    summary_seen = False
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--summary-json":
            if summary_seen:
                print("usage: msp-batch [--summary-json PATH] INPUT CWF OUTPUT TOTALS", file=sys.stderr)
                return 2
            summary_seen = True
            index += 1
            if index >= len(args) or args[index] == "":
                print("usage: msp-batch [--summary-json PATH] INPUT CWF OUTPUT TOTALS", file=sys.stderr)
                return 2
            summary_path = args[index]
        elif token.startswith("--summary-json="):
            if summary_seen or token.partition("=")[2] == "":
                print("usage: msp-batch [--summary-json PATH] INPUT CWF OUTPUT TOTALS", file=sys.stderr)
                return 2
            summary_seen = True
            summary_path = token.partition("=")[2]
        else:
            positionals.append(token)
        index += 1
    return positionals, summary_path


def summary_path_collides(summary_path, positionals) -> bool:
    summary_realpath = os.path.realpath(summary_path)
    for path in positionals:
        if summary_path == path or summary_realpath == os.path.realpath(path):
            return True
        if (os.path.exists(summary_path) and os.path.exists(path)
                and os.path.samefile(summary_path, path)):
            return True
    return False


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    parsed = parse_args(args)
    if parsed == 2:
        return 2
    positionals, summary_path = parsed
    if len(positionals) != 4:
        if summary_path is None:
            print("usage: msp-batch INPUT CWF OUTPUT TOTALS", file=sys.stderr)
        else:
            print("usage: msp-batch [--summary-json PATH] INPUT CWF OUTPUT TOTALS", file=sys.stderr)
        return 2
    if len(set(positionals)) != 4:
        print("paths must be distinct", file=sys.stderr)
        return 2
    if summary_path is not None and summary_path_collides(summary_path, positionals):
        print("--summary-json PATH must differ from INPUT, CWF, OUTPUT and TOTALS", file=sys.stderr)
        return 2
    try:
        run(*positionals, summary_path=summary_path)
    except (FatalBatchError, OSError) as exc:
        print(f"fatal batch failure; discard outputs; {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
