# 05 — COBOL → Python guide

`python/msp.py` is a single stdlib-only module. CLI:
`python3 python/msp.py INPUT CWF RESULTS TOTALS` (same as `build/msp-batch`).

## What changed

| COBOL | Python |
|---|---|
| Four programs (`batch`, `validate`, `payment`, `cwf`) linked by `CALL` | Functions `run_batch`, `validate`, `calculate_payment`, `cwf_check` |
| `claim-interface` passed by reference and `INITIALIZE`d | A new `Claim` object per record |
| Packed decimal `COMP-3` | Python `int` |
| 1,000-entry `B`/`H` arrays scanned linearly | `B` list (first match wins, same as the scan) and an `H` set of `(mbi, dos, charges)` |
| 10,000-entry seen-ID array | `set` |
| Byte-at-a-time read loop | `readline(4098)` with the same limits |
| `fatal-io` / `stop run` | `Fatal` exception → `main` returns 2 |

## What had to stay identical

- Output bytes: headers, field order, `%010d` record/amount fields, `%015d`
  totals, LF endings, trimmed text fields. Verified byte-identical on all
  three comparison batches.
- Validation order and the reason set before each check.
- Provisional IDs `@` + 10-digit record number; real ID once the ID passes,
  even if a later check fails.
- Duplicate-ID fatal for any identifiable ID.
- Framing: LF delimiter, one trailing CR removed, last line without LF counts,
  blank line = a `BAD_LENGTH` record, >4,096 bytes fatal, >10,000 records fatal.
- Payment arithmetic and zero-reason order.
- CWF order, inclusive boundaries, duplicate against `H` history only,
  released = payment only when ACCEPTED.
- CWF reference parsing and its fatal cases, including GnuCOBOL LINE
  SEQUENTIAL details (CR bytes dropped, bytes past column 64 ignored, short
  records space-padded).
- Exit 2 and nothing on stdout for every fatal path. The first stderr line
  matches; COBOL's `; file status ii/oo/tt` suffix and libcob warnings are not
  reproduced.

## Translation traps (and how they were handled)

1. **Floats.** Never. All amounts are `int` cents.
2. **`int()` / `str.isdigit()` are too permissive** (`" +1_0 "`, Unicode
   digits). `is_numeric` uses an explicit ASCII digit set.
3. **Read bytes, not text.** Decoding would reject or reinterpret 0xFF, NUL and
   UTF-8; COBOL treats them as bytes. Only a validated ID is decoded.
4. **Blank line is a record**, not something to skip.
5. **Malformed contract is `BAD_AMOUNT`**, because the NUMERIC test precedes the
   range test.
6. **Duplicate ID on a rejected record is still fatal.**
7. **1-based reference modification**: `cwf-record(45:20)` is `rec[44:64]`.
8. **Space-padded comparisons**: COBOL compares padded fields, so the ID check
   allows trailing spaces only; paths are compared after truncation to 1,024
   bytes and trailing-space removal (`cobol_path`).
9. **`claim-reason` is set before each test**: a translation that sets the reason
   after the test would report the wrong reason when an earlier field fails.
10. **CWF rejection ≠ zero payment**: keep `payment_cents`, zero only
    `released_cents`. `ZERO` claims are still sent to CWF.
11. **Line-length boundary**: COBOL's buffer is 4,097 bytes so a 4,096-byte line
    plus CR fits; a 4,098th byte is fatal before LF is seen.
12. **Collation**: explicit character sets, not range comparisons (see the primer).
13. **Totals width**: Python ints do not overflow; the input format bounds them
    (max 10,000 × 9,999,999,999 fits 15 digits).

## Known non-reproduced details

- Partial output files on fatal errors are not byte-matched (the contract says
  discard them).
- GnuCOBOL file-status codes in the fatal message.
- Paths longer than 1,024 bytes are truncated in both, but OS behavior on such
  names was not tested.
