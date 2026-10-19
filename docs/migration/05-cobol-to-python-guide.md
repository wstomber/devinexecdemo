# 05 — COBOL → Python: what changed, what stayed identical, translation traps

## What changed (structure only)
| COBOL | Python (`python/msp.py`) |
| --- | --- |
| four separately compiled programs sharing `claim-interface` through `CALL … USING` | functions in one module (`validate`, `calculate_payment`, `cwf_check`, `process_line`) that mutate one `Claim` object |
| `initialize claim-interface` | a new `Claim(record_no)` for each record |
| fixed tables (`occurs 1000`, `occurs 10000`) with linear search | `dict` (first B per MBI via `setdefault`), `set` for history and seen IDs; the size limits are enforced by counters |
| COMP-3 packed decimal | Python `int` (unbounded, exact) |
| `stop run` from deep inside a paragraph | `raise Fatal`, caught once in `run` → exit 2 |

## What had to stay identical (and is checked byte-for-byte)
* The CLI (`INPUT CWF OUTPUT TOTALS`), path distinctness on 1,024-byte space-padded fields, exit codes 0/2 only, nothing on stdout.
* Byte framing: LF, one trailing CR, blank line = record, EOF flush, 4,096/4,097 bounds, 10,000 records.
* Validation and zero-reason precedence, `@`+10-digit IDs, duplicate-ID fatality even for INVALID records.
* The payment formula and the CWF check order. `payment_cents` stays the calculated amount and only `released_cents` depends on CWF.
* The CSV text: headers, zero-padded widths (10 digits for rows and counts, 15 for totals), LF endings.
* File-effect order on fatal errors: CWF loaded first (outputs untouched), then input, results, totals; a partial results file, header included, if a later record is fatal (`evidence/live/comparison/fatal-paths.md`).
* GnuCOBOL 3.1.2 LINE SEQUENTIAL quirks on the CWF file (CR dropped anywhere, bytes past 64 ignored, directory = empty reference).

## Translation traps (each one is covered by a test)
1. **`str.isdigit()` / `int()`** accept `٣`, `²`, `+5`, ` 5`, `1_0`. Use an explicit ASCII digit set (`is_digits`). Tests: AMT-*, U:test_only_ascii_digits_are_numeric, edge batch E-ARABIC/E-FULLWIDTH/E-SUPERSCR.
2. **Text mode I/O** would translate `\r\n`, decode bytes and reject non-UTF-8 input. Read raw bytes with `os.read`.
3. **`splitlines()`** treats `\r`, `\x0b`, `\x0c`, `\x1c`… as line breaks. Split on `\n` only.
4. **A blank line is not EOF**: it is a BAD_LENGTH record.
5. **One CR, not `rstrip()`**: `\r\r\n` must stay 93 bytes. For the CWF file, however, *all* CRs are dropped (runtime quirk).
6. **Floats**: never. `int` cents throughout (U:test_no_float_in_source).
7. **The malformed contract reason** is BAD_AMOUNT, because the class test runs before the range test.
8. **Duplicate IDs** must include identifiable INVALID records (from BAD_AMOUNT onward) but exclude `@` IDs.
9. **ZERO claims go to CWF** and count as accepted or rejected.
10. **CWF duplicates** match against H history, not other claims in the batch.
11. **Range checks and EBCDIC**: use set membership, not `"A" <= c <= "Z"` (see 03-cobol-primer.md).
12. **Opening a directory**: `open()` raises at once, but COBOL opens it and then fails on READ (input) or sees EOF (CWF). Using `os.open` + `os.read` reproduces both outcomes.
13. **Path aliases** (`./o.csv` vs `o.csv`) are *not* detected by COBOL. Python compares the same normalized strings and does not resolve paths, so it neither adds nor removes protection.

## Not reproduced (documented, outside the tested contract)
* GnuCOBOL file-name mapping (`DD_name`/`dd_name`/environment-variable lookup for names without a slash, `COB_FILE_PATH`). Callers in this repo always pass explicit paths.
* The exact wording of stderr diagnostics (libcob's "implicit CLOSE" warnings, the file-status digits). Only the exit code and the file effects are part of the contract.
