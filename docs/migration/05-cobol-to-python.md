# 05 — COBOL → Python translation guide

`python/msp.py` replaces `msp-batch` + `validate-claim` + `calculate-payment` with one
standard-library module. This page lists what changed, what had to stay byte-for-byte the
same, and the traps a translator falls into.

## Structure mapping

| COBOL | Python |
|---|---|
| `claim.cpy` `claim-raw` (eight PIC X fields) | slice constants `ID`, `CHARGES`, … `FULL` |
| `claim.cpy` parsed `comp-3` fields | `Claim` dataclass (frozen, `int` cents, `contract: Optional[int]`) |
| `claim-status` / `claim-reason` / `claim-payment` | `Outcome` dataclass |
| validate.cob `validate-record` | `validate_record(record) -> (claim_id or None, Claim or None, reason or None)` |
| validate.cob ID scan 16–32 | `valid_id` |
| `is numeric` | `is_numeric` (explicit ASCII digit set) |
| payment.cob `calculate-prospective-payment` | `calculate_payment(claim) -> (status, reason, cents)` |
| batch.cob 125–141 | `process_record`, `provisional_id`, duplicate set in `run_batch` |
| batch.cob 78–118 byte loop | `iter_records` (64 KiB chunks) + `_finish_line` |
| batch.cob `STRING` rows | `format_result`, `format_totals` |
| `fatal-io` / `stop run` | `FatalBatchError` caught in `main` → return 2 |
| file status checks | `OSError` → return 2 |

## What changed (on purpose)

- **State model.** COBOL reuses one by-reference block and must `INITIALIZE` it per record.
  Python builds new immutable objects per record, so stale contract/payment leakage cannot happen.
- **Returns instead of shared memory.** Validation and payment return values rather than
  writing into the caller's storage.
- **Duplicate lookup.** COBOL scans a 10,000-entry table linearly; Python uses a `set`.
  Same semantics, O(1) lookup.
- **Input reading.** COBOL reads one byte per READ; Python reads 64 KiB chunks and splits on LF.
  The pending-line guard (`> 4,097` bytes) mirrors batch.cob 88 so memory stays bounded.
- **Error messages.** stderr wording differs slightly; stderr is not part of the interface.

## What had to stay identical (and how it was checked)

| Behavior | Evidence |
|---|---|
| CLI `INPUT OUTPUT TOTALS`, exit 0 / 2, no stdout | Stage 2 batch tests; fatal-path comparison (14 cases MATCH) |
| Validation order LENGTH → ID → AMOUNT → CONTRACT → FLAG; malformed contract = BAD_AMOUNT | ledger IF-* cases; `ValidationPrecedence` |
| Zero-reason order FULL → PRIMARY → DEDUCTIONS | ledger IF-FULL-1ST / IF-PRIM-1ST; `test_zero_reason_precedence` |
| `@` + 10-digit provisional IDs; duplicates fatal even when rejected | batch tests; fatal `duplicate-rejected-*` |
| Framing: LF, one CR stripped, last line without LF, blank line = BAD_LENGTH, empty file OK | batch tests; edge batch (mixed CRLF/LF, no final newline) |
| 4,096-byte line / 10,000-record limits | batch tests; fatal comparison |
| CSV bytes: header, 10-digit fields, 15-digit total, LF endings | curated, synthetic and edge outputs **byte-identical** (`summary.json`) |
| Integer cents, maxima | MAX-* cases; `test_maximums_are_exact_integers` |

## Translation traps (each one is guarded by a test)

1. **`float`.** `0.1 + 0.2 != 0.3`. COMP-3 is exact decimal; use `int` cents only.
2. **`int()` and `str.isdigit()` are not `IS NUMERIC`.** `int(" +1")`, `int("0_1")`, and
   `"١".isdigit()` all succeed. Use an explicit `b"0123456789"` byte set
   (`IsNumeric.test_python_pitfalls_this_avoids`).
3. **Decoding text first.** Reading the file as UTF-8 text would crash or normalise bytes and
   would convert `\r\n` silently. Read bytes; strip exactly one CR.
4. **`str.splitlines()`** splits on `\r`, `\x0b`, `\x0c`, `\x1c`… COBOL splits only on LF.
5. **Dropping the trailing empty line.** `b"a\n".split(b"\n")` yields a phantom empty last
   element; `b"a\n\n"` must yield one blank (BAD_LENGTH) record, `b"a\n"` none.
6. **Malformed contract reason.** It's tempting to report BAD_CONTRACT; COBOL reports
   BAD_AMOUNT (validate.cob 40–41). BAD_CONTRACT only means contract > charges.
7. **Duplicate check only for valid records.** COBOL checks every identifiable ID, including
   records rejected for amount/contract/flag (batch.cob 132).
8. **`full=Y` is checked first.** PAYMENT_IN_FULL wins even if primary or
   deductions also exceed the cap.
9. **Forgetting the contract branch.** CMS-EX3 becomes $1,500 instead of $500.
10. **`rstrip` vs `trim`.** COBOL `function trim` strips both sides; valid IDs never have
    leading spaces, so `rstrip(" ")` is equivalent here.
11. **Number formatting.** COBOL `pic 9(10)` in STRING is zero-padded; use `:010d` / `:015d`.

## Known untested differences

These were found by reading the code; no tested batch exercises them, and both are outside the
documented interface:

- **Path equality.** COBOL compares paths as `PIC X(1024)`: trailing spaces are insignificant
  and paths longer than 1,024 bytes are truncated before comparison (and before opening).
  Python compares full strings. Paths with trailing spaces or > 1,024 bytes may behave differently.
- **Partial output files on fatal errors.** Both programs leave partially written results
  files and no complete totals file; the README says to discard them. Their partial contents
  were not compared.
