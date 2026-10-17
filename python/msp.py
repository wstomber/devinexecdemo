"""Python implementation of the fixed-width MSP batch interface."""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

RESULT_HEADER = "record_no,claim_id,status,payment_cents,reason"
TOTALS_HEADER = "records,paid,zero,invalid,payment_cents"
ASCII_DIGITS = frozenset(b"0123456789")
ABSENT_CONTRACT = b"----------"
MAX_RECORDS = 10000
MAX_LINE_LENGTH = 4096


class FatalBatchError(Exception):
    """An input, batch, or output failure that aborts processing."""


@dataclass(frozen=True)
class Claim:
    record_no: int
    claim_id: str
    charges: int
    gross: int
    primary: int
    deductible: int
    coinsurance: int
    contract: int | None
    full: str


@dataclass(frozen=True)
class Rejection:
    record_no: int
    claim_id: str
    reason: str


ResultRow = tuple[int, str, str, int, str]
Totals = tuple[int, int, int, int, int]


def frame_lines(data: bytes) -> Iterator[bytes]:
    """Yield LF-delimited records, stripping one CR and enforcing COBOL limits."""
    if not data:
        return
    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()
    for raw_line in lines:
        if len(raw_line) > MAX_LINE_LENGTH + 1:
            raise FatalBatchError("input line exceeds 4096 bytes")
        line = raw_line[:-1] if raw_line.endswith(b"\r") else raw_line
        if len(line) > MAX_LINE_LENGTH:
            raise FatalBatchError("input line exceeds 4096 bytes")
        yield line


def _valid_id(raw_id: bytes) -> bool:
    if not raw_id.strip(b" "):
        return False
    ended = False
    for byte in raw_id:
        if byte == 32:
            ended = True
        elif ended or not (
            65 <= byte <= 90
            or 48 <= byte <= 57
            or byte in (45, 95)
        ):
            return False
    return True


def _is_ascii_digits(value: bytes) -> bool:
    return bool(value) and all(byte in ASCII_DIGITS for byte in value)


def validate(line: bytes, record_no: int) -> Claim | Rejection:
    """Validate one framed record using the COBOL rejection precedence."""
    provisional_id = f"@{record_no:010d}"
    if len(line) != 73:
        return Rejection(record_no, provisional_id, "BAD_LENGTH")

    raw_id = line[:12]
    if not _valid_id(raw_id):
        return Rejection(record_no, provisional_id, "BAD_ID")
    claim_id = raw_id.rstrip(b" ").decode("ascii")

    amounts = (line[12:22], line[22:32], line[32:42], line[42:52], line[52:62])
    raw_contract = line[62:72]
    if not all(_is_ascii_digits(amount) for amount in amounts):
        return Rejection(record_no, claim_id, "BAD_AMOUNT")
    if raw_contract != ABSENT_CONTRACT and not _is_ascii_digits(raw_contract):
        return Rejection(record_no, claim_id, "BAD_AMOUNT")

    charges, gross, primary, deductible, coinsurance = map(int, amounts)
    contract = None if raw_contract == ABSENT_CONTRACT else int(raw_contract)
    if contract is not None and contract > charges:
        return Rejection(record_no, claim_id, "BAD_CONTRACT")

    full = line[72:73]
    if full not in (b"Y", b"N"):
        return Rejection(record_no, claim_id, "BAD_FLAG")

    return Claim(
        record_no=record_no,
        claim_id=claim_id,
        charges=charges,
        gross=gross,
        primary=primary,
        deductible=deductible,
        coinsurance=coinsurance,
        contract=contract,
        full=full.decode("ascii"),
    )


def calculate_payment(claim: Claim) -> tuple[str, int, str]:
    """Calculate status, cents, and reason with COBOL branch precedence."""
    if claim.full == "Y":
        return "ZERO", 0, "PAYMENT_IN_FULL"

    cap = min(claim.gross, claim.charges if claim.contract is None else claim.contract)
    if claim.primary >= cap:
        return "ZERO", 0, "PRIMARY_AT_CAP"

    deductions = claim.deductible + claim.coinsurance
    if deductions >= cap:
        return "ZERO", 0, "DEDUCTIONS_AT_CAP"

    return "PAID", cap - max(deductions, claim.primary), "SECONDARY_PAYABLE"


def process_batch(data: bytes) -> tuple[list[ResultRow], Totals]:
    """Validate and calculate an entire input batch, aborting on fatal conditions."""
    rows: list[ResultRow] = []
    seen_ids: set[str] = set()
    paid = zero = invalid = payment_total = 0

    for record_no, line in enumerate(frame_lines(data), start=1):
        if record_no > MAX_RECORDS:
            raise FatalBatchError("batch exceeds 10000 records")
        parsed = validate(line, record_no)
        if not parsed.claim_id.startswith("@"):
            if parsed.claim_id in seen_ids:
                raise FatalBatchError(f"duplicate claim ID: {parsed.claim_id}")
            seen_ids.add(parsed.claim_id)

        if isinstance(parsed, Rejection):
            status, payment, reason = "INVALID", 0, parsed.reason
            invalid += 1
        else:
            status, payment, reason = calculate_payment(parsed)
            if status == "PAID":
                paid += 1
            else:
                zero += 1
        payment_total += payment
        rows.append((record_no, parsed.claim_id, status, payment, reason))

    totals = (len(rows), paid, zero, invalid, payment_total)
    return rows, totals


def format_result_row(row: ResultRow) -> str:
    record_no, claim_id, status, payment, reason = row
    return f"{record_no:010d},{claim_id},{status},{payment:010d},{reason}"


def format_totals_row(totals: Totals) -> str:
    records, paid, zero, invalid, payment_total = totals
    return f"{records:010d},{paid:010d},{zero:010d},{invalid:010d},{payment_total:015d}"


def _stage_output(path: Path, content: bytes) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as staged:
        staged.write(content)
        return Path(staged.name)


def _write_outputs(output_path: str, totals_path: str, rows: list[ResultRow], totals: Totals) -> None:
    result_text = "\n".join([RESULT_HEADER, *(format_result_row(row) for row in rows)]) + "\n"
    totals_text = "\n".join([TOTALS_HEADER, format_totals_row(totals)]) + "\n"
    staged_paths: list[Path] = []
    destinations = (Path(output_path), Path(totals_path))
    try:
        if any(path.is_dir() for path in destinations):
            raise OSError("output path is a directory")
        for path, content in zip(destinations, (result_text.encode("ascii"), totals_text.encode("ascii"))):
            staged_paths.append(_stage_output(path, content))
        for staged, destination in zip(staged_paths, destinations):
            os.replace(staged, destination)
    finally:
        for staged in staged_paths:
            try:
                staged.unlink()
            except FileNotFoundError:
                pass


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        print("usage: msp.py INPUT OUTPUT TOTALS", file=sys.stderr)
        return 2
    input_path, output_path, totals_path = args
    if input_path == output_path or input_path == totals_path or output_path == totals_path:
        print("paths must be distinct", file=sys.stderr)
        return 2

    try:
        data = Path(input_path).read_bytes()
        rows, totals = process_batch(data)
        _write_outputs(output_path, totals_path, rows, totals)
    except (FatalBatchError, OSError) as exc:
        print(str(exc) or "fatal batch failure", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
