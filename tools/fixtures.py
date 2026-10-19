"""Serialize cents to fixed-width records; no payment calculations live here."""
import argparse
import json
import random
from pathlib import Path

FIELDS = ("charges", "gross", "primary", "deductible", "coinsurance", "contract")
MAX_AMOUNT = 9_999_999_999
DEFAULT_MBI = "1EG4TE5MK73"
DEFAULT_DOS = "20250315"
SYNTHETIC_MBIS = ("1EG4TE5MK73",) * 5 + ("2MSP0000001",) * 3 + ("3ENDED00001", "4FUTURE0001", "5HIST000001", "9NOTONFILE9")


def serialize(claim):
    claim_id = claim["id"]
    if not 1 <= len(claim_id) <= 12 or any(
        c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in claim_id
    ):
        raise ValueError("id must contain 1-12 uppercase ASCII letters/digits/-/_")
    parts = [claim_id.ljust(12)]
    for field in FIELDS:
        value = claim.get(field)
        if field == "contract" and value is None:
            parts.append("----------")
        elif type(value) is int and 0 <= value <= MAX_AMOUNT:
            parts.append(f"{value:010d}")
        else:
            raise ValueError(f"{claim_id}: {field} must be integer cents in range")
    flag = claim.get("full", "N")
    if flag not in ("Y", "N"):
        raise ValueError("full must be Y or N")
    mbi, dos = claim.get("mbi", DEFAULT_MBI), claim.get("dos", DEFAULT_DOS)
    if len(mbi) != 11 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in mbi):
        raise ValueError(f"{claim_id}: mbi must be 11 uppercase letters/digits")
    if len(dos) != 8 or not dos.isdigit():
        raise ValueError(f"{claim_id}: dos must be YYYYMMDD")
    return "".join(parts) + flag + mbi + dos


def date_field(value):
    if value is None:
        return "--------"
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"date must be YYYYMMDD: {value!r}")
    return value


def serialize_cwf(reference):
    """CWF reference file: B (beneficiary, 44 bytes) and H (posted claim history, 30 bytes) records."""
    lines = []
    for b in reference["beneficiaries"]:
        if (b["msp_from"] is None) != (b["msp_to"] is None):
            raise ValueError(f"{b['mbi']}: MSP period needs both dates")
        lines.append("B" + b["mbi"] + date_field(b["entitled_from"]) + date_field(b["entitled_to"])
                     + date_field(b["msp_from"]) + date_field(b["msp_to"]))
    for h in reference["history"]:
        lines.append("H" + h["mbi"] + date_field(h["dos"]) + f"{h['charges']:010d}")
    for line in lines:
        if len(line) not in (44, 30) or len(line[1:12]) != 11:
            raise ValueError(f"bad CWF record {line!r}")
    return lines


def case_record(case):
    """Explicit raw overrides allow curated malformed-input fixtures."""
    if "raw_record" in case:
        return case["raw_record"]
    record = serialize(case["input"])
    for patch in case.get("patches", []):
        start, width, value = patch
        record = record[:start] + value + record[start + width:]
    return record


def generate(seed, count):
    rng = random.Random(seed)
    for i in range(count):
        charges = rng.randrange(MAX_AMOUNT + 1)
        gross = rng.randrange(MAX_AMOUNT + 1)
        cap = min(charges, gross)
        yield {
            "id": f"S{i + 1:011d}", "charges": charges,
            "gross": gross,
            "primary": 0 if rng.randrange(25) == 0 else rng.randrange(MAX_AMOUNT + 1),
            "deductible": rng.randrange(MAX_AMOUNT + 1) if i % 10 == 0 else rng.randrange(cap // 3 + 1),
            "coinsurance": rng.randrange(cap // 3 + 1),
            "contract": rng.randrange(charges + 1) if rng.randrange(3) == 0 else None,
            "full": "Y" if rng.randrange(20) == 0 else "N",
            "mbi": SYNTHETIC_MBIS[rng.randrange(len(SYNTHETIC_MBIS))],
            "dos": f"2025{rng.randrange(1, 13):02d}{rng.randrange(1, 29):02d}",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--cwf-source", type=Path, help="serialize CWF reference JSON instead of claims")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--readable-output", type=Path)
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    if not 0 <= args.count <= 10000:
        parser.error("count must be 0..10000")
    if args.cwf_source:
        lines = serialize_cwf(json.loads(args.cwf_source.read_text()))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("".join(line + "\n" for line in lines), encoding="ascii")
        print(f"Serialized {len(lines)} CWF reference records to {args.output}")
        return
    data = json.loads(args.source.read_text()) if args.source else list(generate(args.seed, args.count))
    records = [case_record(c) if "input" in c or "raw_record" in c else serialize(c) for c in data]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(r + "\n" for r in records), encoding="ascii")
    if args.readable_output:
        args.readable_output.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Serialized {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
