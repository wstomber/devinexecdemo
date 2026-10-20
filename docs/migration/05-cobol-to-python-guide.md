# 05 — COBOL → Python guide: what changed, what stayed identical, translation traps

## Mapping

| COBOL | Python (`python/msp.py`) |
| --- | --- |
| `claim-interface` copybook + `initialize` | `Claim` dataclass, created fresh for every record |
| `validate-claim` / `validate-record` | `validate_record(line, record_no)` |
| `calculate-payment` / `calculate-prospective-payment` | `calculate_payment(claim)` |
| `cwf-check` / `check-claim` | `cwf_check(claim, reference)` |
| `cwf-tables` (two OCCURS 1000 tables, linear scans) | `CwfReference`: dict of first `B` per MBI + set of `H` keys |
| `load-cwf` / `parse-cwf` | `cwf_records()` (runtime line-sequential emulation) + `parse_cwf()` |
| byte loop in `main` + `finish-line` | `input_lines()` generator |
| `process-record` + counters | `Batch.process()` / `Batch.totals_row()` |
| `seen-id` OCCURS 10000 + linear scan | `set` (same result, O(1)) |
| `fatal-io` (`stop run`, return code 2) | `Fatal` exception / `OSError` → `run()` returns 2 |

## What had to stay identical, and how it is shown

- CLI `INPUT CWF OUTPUT TOTALS`, exit codes 0/2, diagnostics on stderr only:
  Stage 2 `UsageTests`, `fatal-paths.md`.
- Byte framing (LF, one CR, blank lines, 4,096/4,097, no final newline):
  `FramingTests`, edge batch.
- Validation precedence and every reason code: ledger cases 37–79 and the edge
  fuzz records.
- Integer cents, the payment formula and zero-reason order: ledger 1–36.
- `@`+10-digit IDs and fatal duplicate identifiable IDs: ledger, `IdentityTests`.
- CWF order, inclusive dates, history key, released vs calculated: ledger 80–107.
- Exact CSV bytes, including zero padding: all four comparison batches are
  byte-identical.
- Partial outputs left behind on a fatal error: `fatal-paths.md`, leftovers
  identical in all 18 scenarios.

## What changed (intentionally)

- Lookups use a dict and a set instead of linear scans. The first-`B`-wins
  behavior is kept with `setdefault`.
- The input is read whole into memory after the outputs are opened. It is bounded
  by the 10,000 × 4,096-byte limits (≈ 41 MB). The COBOL reads one byte at a time.
- Diagnostic text differs slightly. Only the presence of stderr output and the
  exit code are part of the contract.
- Path equality compares the exact argument strings. COBOL compares
  space-padded `pic x(1024)` values. This is not tested (see the rule-map open
  items).

## Translation traps (and where each one bit or could bite)

1. **`str.isdigit()` / `int()`**: both accept non-ASCII digits, signs, spaces and
   `_`. Use an explicit `b"0123456789"` set. Covered by the AMT-* cases and the
   edge-bytes batch.
2. **`float`**: even one conversion can lose cents at 10-digit magnitudes. Use
   `int` only.
3. **`splitlines()` / `strip()`**: these split on `\r`, `\x0b`, `\x0c`, `\x1c`
   and more, and strip all whitespace. COBOL removes exactly one trailing CR from
   a claim line. Use `find(b"\n")` and a single `endswith(b"\r")`.
4. **Text mode / encoding**: reading with `open(..., "r")` would translate
   newlines and fail on non-ASCII bytes. Read the input as bytes.
5. **Blank line ≠ EOF**: a blank line is a `BAD_LENGTH` record.
6. **Malformed contract**: this is `BAD_AMOUNT`, because the NUMERIC test
   precedes the range check. It is not `BAD_CONTRACT`.
7. **Duplicate ID after a rejection**: an ID that passed the `BAD_ID` check is
   remembered even if the record fails later, so a repeat is fatal.
8. **CWF rejection ≠ payment result**: keep `payment_cents` and the status/reason.
   Zero only `released_cents`.
9. **CWF duplicates** are matched against `H` history only, never against other
   claims in the batch (BATCH-SAMEKY).
10. **Line-sequential runtime quirks** (CWF file): GnuCOBOL drops *every* CR,
    truncates after 64 bytes and pads with spaces. A naive `rstrip("\r\n")` port
    would accept or reject different files. This was probed on the COBOL before
    the port was written.
11. **File-open order**: GnuCOBOL opens a directory as input successfully and
    fails on READ, after the outputs are truncated. The port mirrors this with
    `os.open` (corrections.md #3).
12. **Zero-padded output**: `pic 9(10)` always prints 10 digits, so use
    `f"{n:010d}"` and `f"{n:015d}"` for the totals.
