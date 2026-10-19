import csv
import io
import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


RESULTS_HEADER = (
    "record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents"
)
TOTALS_HEADER = (
    "records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents"
)


@dataclass
class BatchRun:
    returncode: int
    stdout: str
    stderr: str
    results: list[dict[str, str]] | None
    totals: dict[str, str] | None
    raw_results: str | None
    raw_totals: str | None


def command():
    return shlex.split(os.environ.get("MSP_COMMAND", "build/msp-batch"))


def _read_csv(path, first_row_only=False):
    if not path.exists():
        return None, None
    raw = path.read_text(encoding="ascii")
    rows = list(csv.DictReader(io.StringIO(raw)))
    if first_row_only:
        return (rows[0] if rows else None), raw
    return rows, raw


def _run(args, results_path=None, totals_path=None):
    completed = subprocess.run(
        [*command(), *map(str, args)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    results, raw_results = (
        _read_csv(Path(results_path)) if results_path is not None else (None, None)
    )
    totals, raw_totals = (
        _read_csv(Path(totals_path), first_row_only=True)
        if totals_path is not None
        else (None, None)
    )
    return BatchRun(
        completed.returncode,
        completed.stdout,
        completed.stderr,
        results,
        totals,
        raw_results,
        raw_totals,
    )


def run(input_bytes, cwf_bytes, argv_override=None):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "in.dat"
        cwf_path = root / "cwf.dat"
        results_path = root / "results.csv"
        totals_path = root / "totals.csv"
        input_path.write_bytes(input_bytes)
        cwf_path.write_bytes(cwf_bytes)
        args = (
            list(argv_override)
            if argv_override is not None
            else [input_path, cwf_path, results_path, totals_path]
        )
        return _run(args, results_path, totals_path)


def run_args(args):
    with tempfile.TemporaryDirectory():
        return _run(args)


def claim_record(
    id,
    charges,
    gross,
    primary,
    deductible,
    coinsurance,
    contract,
    full,
    mbi,
    dos,
):
    if isinstance(full, bool):
        full = "Y" if full else "N"
    record = (
        id.ljust(12)
        + f"{charges:010d}"
        + f"{gross:010d}"
        + f"{primary:010d}"
        + f"{deductible:010d}"
        + f"{coinsurance:010d}"
        + ("----------" if contract is None else f"{contract:010d}")
        + str(full)
        + mbi
        + dos
    )
    assert len(record) == 92
    return record


def b_record(mbi, frm, to, msp_from=None, msp_to=None):
    record = (
        "B"
        + mbi
        + frm
        + to
        + (msp_from or "--------")
        + (msp_to or "--------")
    )
    assert len(record) == 44
    return record


def h_record(mbi, dos, charges):
    record = "H" + mbi + dos + f"{charges:010d}"
    assert len(record) == 30
    return record


def cwf_file(ref_dict):
    lines = [
        *(
            b_record(
                beneficiary["mbi"],
                beneficiary["entitled_from"],
                beneficiary["entitled_to"],
                beneficiary.get("msp_from"),
                beneficiary.get("msp_to"),
            )
            for beneficiary in ref_dict.get("beneficiaries", [])
        ),
        *(
            h_record(history["mbi"], history["dos"], history["charges"])
            for history in ref_dict.get("history", [])
        ),
    ]
    return "".join(line + "\n" for line in lines).encode("ascii")


def load_ledger():
    configured = os.environ.get("MSP_EXPECTATIONS")
    path = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parent / "expectations.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def build_case_record(case, defaults=None):
    if "raw" in case:
        return case["raw"]

    defaults = defaults or {}
    values = case["input"]
    record = claim_record(
        values["id"],
        values["charges"],
        values["gross"],
        values["primary"],
        values["deductible"],
        values["coinsurance"],
        values.get("contract"),
        values["full"],
        values.get("mbi", defaults.get("mbi", "P1MEDPRIM01")),
        values.get("dos", defaults.get("dos", "20250610")),
    )
    return _patch_record(record, case.get("patch", []))


def _patch_record(record, patches):
    for offset, text in patches:
        if offset < 0 or offset + len(text) > len(record):
            raise ValueError(f"patch outside claim record: {offset}, {text!r}")
        record = record[:offset] + text + record[offset + len(text) :]
    return record


def expected_row(case, record_no):
    expected = dict(case["expected"])
    if expected["claim_id"] == "@":
        expected["claim_id"] = f"@{record_no:010d}"
    return {
        "record_no": record_no,
        "claim_id": expected["claim_id"],
        "status": expected["status"],
        "payment_cents": expected["payment_cents"],
        "reason": expected["reason"],
        "cwf": expected["cwf"],
        "cwf_reason": expected["cwf_reason"],
        "released_cents": expected["released_cents"],
    }
