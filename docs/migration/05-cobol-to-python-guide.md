# 05 — COBOL → Python migration guide

## What had to stay identical (the contract)
- CLI `INPUT CWF OUTPUT TOTALS`, exit 0 / 2, nothing on stdout, stderr texts (including the
  `fatal batch failure; discard outputs; file status ii/oo/tt` line and the libcob
  `implicit CLOSE` warning lines, which callers may already parse or log).
- CWF loaded before the input is opened; then input, results, totals in that order, so
  the same file is (or is not) created on each fatal path.
- Byte-level framing, 4,096/4,097/4,098-byte behaviour, 10,000 records, provisional IDs,
  duplicate-ID rule, validation and zero-reason precedence, CWF check order, released amount.
- Output bytes: same headers, zero-padded widths, trimmed fields, LF endings — results and
  totals are byte-identical to COBOL on curated, synthetic and edge batches.

## What changed (internal only)
| COBOL | Python |
| --- | --- |
| global WORKING-STORAGE, `INITIALIZE` per record | an immutable `Claim` dataclass created per record (`validate_claim`) |
| `CALL … USING` writing into the caller's record | functions returning values (`calculate_payment` → status, reason, payment; `check_cwf` → decision, reason, released) |
| `PIC 9(10) COMP-3` packed decimal | Python `int` (exact, unbounded; field widths enforced by validation, not by storage) |
| `FILE STATUS` checks after every verb | `try/except OSError` mapped to COBOL statuses (`35` input not found, `30` output open failure) |
| fixed-size `OCCURS 1000` tables | tuples with explicit `>= 1000` checks |
| `seen-id OCCURS 10000` linear search | `set` (same outcome, O(1)) |
| GnuCOBOL line-sequential CWF reader | `_cwf_lines`: split on LF, drop CR, truncate/pad to 64 |

## Translation traps (each caught by a test)
1. `str.isdigit()` / `int()` accept Unicode digits, `+`, spaces and `_`; use an explicit
   ASCII set (`ascii_digits`). Work on **bytes**, never decoded text.
2. A blank line is a record (`BAD_LENGTH`), not EOF; a final lone `\r` is one more blank record.
3. A malformed contract is `BAD_AMOUNT` (checked with the amounts), not `BAD_CONTRACT`.
4. Duplicate IDs are checked as soon as the ID is valid — before later field checks.
5. Python lists/dicts reused across records leak state (COBOL relies on `INITIALIZE`).
6. Never subtract before the zero tests in a language with unsigned fields; in Python the
   result would just be negative — the order still decides the reason code.
7. CWF rejection must not zero `payment_cents`; only `released_cents`.
8. CWF duplicates are against `H` history only; two identical claims in one batch both pass.
9. The 4,098th byte is fatal *without* the "exceeds 4096" message (COBOL line 104).
10. Comparing `YYYYMMDD` as ASCII bytes equals numeric comparison only because all are
    8 validated digits; keep that invariant if dates change.
11. Do not "fix" COBOL quirks while porting (e.g. `20250631` accepted, first `B` record wins);
    change them deliberately afterwards with a ledger update.
