#!/usr/bin/env python3
import errno
import io
import sys
from dataclasses import dataclass, replace


RESULTS_HEADER = (
    b"record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents\n"
)
TOTALS_HEADER = (
    b"records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents\n"
)
ASCII_DIGITS = frozenset(b"0123456789")
ASCII_ID = ASCII_DIGITS | frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ-_")


@dataclass(frozen=True)
class FramedRecord:
    data: bytes
    length: int


@dataclass(frozen=True)
class Beneficiary:
    mbi: bytes
    entitled_from: bytes
    entitled_to: bytes
    msp_from: bytes | None
    msp_to: bytes | None


@dataclass(frozen=True)
class History:
    mbi: bytes
    dos: bytes
    charges: bytes


@dataclass(frozen=True)
class CwfReference:
    beneficiaries: tuple[Beneficiary, ...]
    history: tuple[History, ...]


@dataclass(frozen=True)
class Claim:
    raw: bytes
    length: int
    claim_id: bytes
    status: str
    reason: str
    charges: int = 0
    gross: int = 0
    primary: int = 0
    deductible: int = 0
    coinsurance: int = 0
    contract: int | None = None
    full: bytes = b" "
    mbi: bytes = b"           "
    dos: bytes = b"        "
    payment: int = 0


class CwfError(Exception):
    pass


class InputLineError(Exception):
    def __init__(self, message=None):
        super().__init__(message or "")
        self.message = message


def ascii_digits(value):
    return bool(value) and all(byte in ASCII_DIGITS for byte in value)


def valid_claim_id(value):
    if len(value) != 12 or value == b" " * 12:
        return False
    ended = False
    for byte in value:
        if byte == 0x20:
            ended = True
        elif ended or byte not in ASCII_ID:
            return False
    return True


def _provisional_id(record_no):
    return (f"@{record_no:010d}").encode("ascii").ljust(12, b" ")


def validate_claim(raw, length, provisional_id=b"@0000000001 "):
    record = raw[:92].ljust(92, b" ")
    claim_id = provisional_id
    if length != 92:
        return Claim(record, length, claim_id, "INVALID", "BAD_LENGTH")

    raw_id = record[0:12]
    if not valid_claim_id(raw_id):
        return Claim(record, length, claim_id, "INVALID", "BAD_ID")
    claim_id = raw_id

    amounts = (
        record[12:22],
        record[22:32],
        record[32:42],
        record[42:52],
        record[52:62],
    )
    raw_contract = record[62:72]
    if not all(ascii_digits(amount) for amount in amounts) or (
        raw_contract != b"----------" and not ascii_digits(raw_contract)
    ):
        return Claim(record, length, claim_id, "INVALID", "BAD_AMOUNT")

    charges, gross, primary, deductible, coinsurance = (
        int(amount) for amount in amounts
    )
    contract = None if raw_contract == b"----------" else int(raw_contract)
    if contract is not None and contract > charges:
        return Claim(record, length, claim_id, "INVALID", "BAD_CONTRACT")

    full = record[72:73]
    if full not in (b"Y", b"N"):
        return Claim(record, length, claim_id, "INVALID", "BAD_FLAG")

    mbi = record[73:84]
    if any(
        byte not in ASCII_DIGITS and byte not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for byte in mbi
    ):
        return Claim(record, length, claim_id, "INVALID", "BAD_MBI")

    dos = record[84:92]
    if not ascii_digits(dos) or not (b"01" <= dos[4:6] <= b"12") or not (
        b"01" <= dos[6:8] <= b"31"
    ):
        return Claim(record, length, claim_id, "INVALID", "BAD_DATE")

    return Claim(
        record,
        length,
        claim_id,
        "VALID",
        "",
        charges,
        gross,
        primary,
        deductible,
        coinsurance,
        contract,
        full,
        mbi,
        dos,
    )


def calculate_payment(claim):
    if claim.full == b"Y":
        return "ZERO", "PAYMENT_IN_FULL", 0

    basis = claim.contract if claim.contract is not None else claim.charges
    cap = min(claim.gross, basis)
    if claim.primary >= cap:
        return "ZERO", "PRIMARY_AT_CAP", 0

    deductions = claim.deductible + claim.coinsurance
    if deductions >= cap:
        return "ZERO", "DEDUCTIONS_AT_CAP", 0

    return "PAID", "SECONDARY_PAYABLE", cap - max(deductions, claim.primary)


def _cwf_lines(data):
    if not data:
        return
    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()
    for line in lines:
        yield line.replace(b"\r", b"")[:64].ljust(64, b" ")


def parse_cwf(data):
    beneficiaries = []
    history = []
    for record in _cwf_lines(data):
        record_type = record[:1]
        if record_type == b"B":
            mbi = record[1:12]
            entitled_from = record[12:20]
            entitled_to = record[20:28]
            msp = record[28:44]
            if (
                record[44:64] != b" " * 20
                or mbi == b" " * 11
                or not ascii_digits(entitled_from + entitled_to)
                or not (msp == b"-" * 16 or ascii_digits(msp))
                or len(beneficiaries) >= 1000
            ):
                raise CwfError
            if msp == b"-" * 16:
                msp_from = None
                msp_to = None
            else:
                msp_from = msp[:8]
                msp_to = msp[8:]
            beneficiaries.append(
                Beneficiary(mbi, entitled_from, entitled_to, msp_from, msp_to)
            )
        elif record_type == b"H":
            mbi = record[1:12]
            dos = record[12:20]
            charges = record[20:30]
            if (
                record[30:64] != b" " * 34
                or mbi == b" " * 11
                or not ascii_digits(dos + charges)
                or len(history) >= 1000
            ):
                raise CwfError
            history.append(History(mbi, dos, charges))
        else:
            raise CwfError
    return CwfReference(tuple(beneficiaries), tuple(history))


def check_cwf(claim, reference):
    beneficiary = next(
        (entry for entry in reference.beneficiaries if entry.mbi == claim.mbi),
        None,
    )
    if (
        beneficiary is None
        or claim.dos < beneficiary.entitled_from
        or claim.dos > beneficiary.entitled_to
    ):
        return "REJECTED", "NOT_ENTITLED", 0

    charges = f"{claim.charges:010d}".encode("ascii")
    if any(
        entry.mbi == claim.mbi and entry.dos == claim.dos and entry.charges == charges
        for entry in reference.history
    ):
        return "REJECTED", "DUPLICATE", 0

    if (
        beneficiary.msp_from is not None
        and beneficiary.msp_from <= claim.dos <= beneficiary.msp_to
        and claim.primary == 0
    ):
        return "REJECTED", "MSP_PRIMARY_NOT_BILLED", 0

    return "ACCEPTED", "DISPOSITION_01", claim.payment


def iter_framed_records(stream, on_status=None):
    pending = bytearray()
    while True:
        byte = stream.read(1)
        if not byte:
            if on_status is not None:
                on_status("10")
            if pending:
                yield _finish_line(pending)
            return
        if on_status is not None:
            on_status("00")
        if byte == b"\n":
            yield _finish_line(pending)
            pending.clear()
        else:
            if len(pending) >= 4097:
                raise InputLineError
            pending.extend(byte)


def _finish_line(pending):
    if pending and pending[-1] == 0x0D:
        del pending[-1]
    if len(pending) > 4096:
        raise InputLineError("input line exceeds 4096 bytes")
    data = bytes(pending)
    return FramedRecord(data[:92].ljust(92, b" "), len(data))


def frame_input(data):
    return list(iter_framed_records(io.BytesIO(data)))


def _display_bytes(value):
    return value.decode("ascii")


def _error_status(error):
    if error.errno == errno.ENOENT:
        return "35"
    return "30"


def _fatal_line(statuses):
    return (
        "fatal batch failure; discard outputs; file status "
        + statuses[0]
        + "/"
        + statuses[1]
        + "/"
        + statuses[2]
        + "\n"
    )


def _runtime_close_warning(name, path):
    return (
        f"libcob: cobol/batch.cob:267: warning: implicit CLOSE of {name} "
        f"('{path}')\n"
    )


def _write_fatal(message, statuses, opened):
    if message:
        sys.stderr.write(message + "\n")
    sys.stderr.write(_fatal_line(statuses))
    for name, path in reversed(opened):
        sys.stderr.write(_runtime_close_warning(name, path))


def _result_line(record_no, claim, cwf, cwf_reason, released):
    fields = (
        f"{record_no:010d}".encode("ascii"),
        claim.claim_id.strip(b" "),
        claim.status.encode("ascii"),
        f"{claim.payment:010d}".encode("ascii"),
        claim.reason.encode("ascii"),
        cwf.encode("ascii"),
        cwf_reason.encode("ascii"),
        f"{released:010d}".encode("ascii"),
    )
    return b",".join(fields) + b"\n"


def _totals_line(record_count, paid, zero, invalid, payment, accepted, rejected, released):
    return (
        f"{record_count:010d},{paid:010d},{zero:010d},{invalid:010d},"
        f"{payment:015d},{accepted:010d},{rejected:010d},{released:015d}\n"
    ).encode("ascii")


def _process_record(record, record_no, reference, seen_ids):
    claim = validate_claim(record.data, record.length, _provisional_id(record_no))
    if claim.claim_id[:1] != b"@":
        if claim.claim_id in seen_ids:
            raise ValueError(claim.claim_id)
        seen_ids.add(claim.claim_id)

    if claim.status == "VALID":
        status, reason, payment = calculate_payment(claim)
        claim = replace(claim, status=status, reason=reason, payment=payment)
        cwf, cwf_reason, released = check_cwf(claim, reference)
    else:
        cwf, cwf_reason, released = "NOT_SENT", "CLAIM_INVALID", 0
    return claim, cwf, cwf_reason, released


def _run_batch(input_path, cwf_path, output_path, totals_path):
    statuses = ["  ", "  ", "  "]
    opened = []
    handles = []
    reference = None

    try:
        try:
            cwf_handle = open(cwf_path, "rb")
        except OSError:
            _write_fatal(None, statuses, opened)
            return 2
        opened.append(("cwf-file", cwf_path))
        handles.append(cwf_handle)
        try:
            reference = parse_cwf(cwf_handle.read())
        except CwfError:
            _write_fatal("invalid CWF reference record", statuses, opened)
            return 2
        cwf_handle.close()
        handles.remove(cwf_handle)
        opened.remove(("cwf-file", cwf_path))

        try:
            input_handle = open(input_path, "rb")
        except OSError as error:
            statuses[0] = _error_status(error)
            _write_fatal(None, statuses, opened)
            return 2
        statuses[0] = "00"
        opened.append(("claims-file", input_path))
        handles.append(input_handle)

        try:
            results_handle = open(output_path, "wb")
        except OSError:
            statuses[1] = "30"
            _write_fatal(None, statuses, opened)
            return 2
        statuses[1] = "00"
        opened.append(("results-file", output_path))
        handles.append(results_handle)

        try:
            totals_handle = open(totals_path, "wb")
        except OSError:
            statuses[2] = "30"
            _write_fatal(None, statuses, opened)
            return 2
        statuses[2] = "00"
        opened.append(("totals-file", totals_path))
        handles.append(totals_handle)

        results_handle.write(RESULTS_HEADER)
        record_count = paid = zero = invalid = 0
        payment_total = accepted = rejected = released_total = 0
        seen_ids = set()

        def update_input_status(value):
            statuses[0] = value

        try:
            records = iter_framed_records(input_handle, update_input_status)
            for record in records:
                if record_count >= 10000:
                    _write_fatal("batch exceeds 10000 records", statuses, opened)
                    return 2
                record_count += 1
                try:
                    claim, cwf, cwf_reason, released = _process_record(
                        record, record_count, reference, seen_ids
                    )
                except ValueError as error:
                    claim_id = error.args[0]
                    _write_fatal(
                        "duplicate claim ID: " + _display_bytes(claim_id),
                        statuses,
                        opened,
                    )
                    return 2
                results_handle.write(
                    _result_line(record_count, claim, cwf, cwf_reason, released)
                )
                if claim.status == "PAID":
                    paid += 1
                elif claim.status == "ZERO":
                    zero += 1
                else:
                    invalid += 1
                if cwf == "ACCEPTED":
                    accepted += 1
                elif cwf == "REJECTED":
                    rejected += 1
                payment_total += claim.payment
                released_total += released
        except InputLineError as error:
            _write_fatal(error.message, statuses, opened)
            return 2

        totals_handle.write(TOTALS_HEADER)
        totals_handle.write(
            _totals_line(
                record_count,
                paid,
                zero,
                invalid,
                payment_total,
                accepted,
                rejected,
                released_total,
            )
        )
        return 0
    finally:
        for handle in reversed(handles):
            try:
                handle.close()
            except OSError:
                pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 4:
        sys.stderr.write("usage: msp-batch INPUT CWF OUTPUT TOTALS\n")
        return 2
    input_path, cwf_path, output_path, totals_path = argv
    if len({input_path, cwf_path, output_path, totals_path}) != 4:
        sys.stderr.write("paths must be distinct\n")
        return 2
    return _run_batch(input_path, cwf_path, output_path, totals_path)


if __name__ == "__main__":
    raise SystemExit(main())
