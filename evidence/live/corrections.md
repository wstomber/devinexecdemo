# Corrections log

Every correction made during the live run, with its cause. No expected value
was changed to match program output.

## Stage 2 - independent tests (before any Python)

| # | What failed | Cause | Correction |
|---|---|---|---|
| 1 | Ledger serializer assertion: record not 92 bytes for `CWF-INV-ONFILE` | Test-authoring error: case ID was 14 characters; README allows 1-12. Some IDs also used `+`, which is not an allowed ID character. | Renamed `CWF-INV-ONFILE`->`CWF-INV-ON`, `CWF-DUP-C+1`->`CWF-DUP-CP1`, `CWF-DUP-C-1`->`CWF-DUP-CM1`, `CWF-DUP-D+1`->`CWF-DUP-DP1`, `CWF-DUP-D-1`->`CWF-DUP-DM1`; added an ID-format check to the ledger authoring step. Expected values unchanged. |
| 2 | `TypeError: 'Run' object is not callable` | Test-harness bug: class attribute named `run` shadowed `unittest.TestCase.run`. | Renamed to `batch_run`. |
| 3 | `test_4096_byte_line_is_one_invalid_record` (ending `b""`) exited 2 | Test-construction error: with no line ending, the 4,096 `X` bytes were joined to the next record, forming one 4,188-byte line, which README says is fatal. COBOL was right. | Dropped the `b""` ending from that mid-file subtest; the no-final-newline 4,096-byte case is covered by `test_4096_byte_last_line_without_newline`. |

After these, all 24 tests (119 ledger cases) pass against COBOL:
`evidence/live/stage2-cobol-tests.log`.

## Stage 3 - Python

| # | What failed | Cause | Correction |
|---|---|---|---|
| 4 | None. The first run of `python/msp.py` passed all 24 unchanged Stage 2 tests. | - | - |
| 5 | Before writing the CWF reader, probes of `build/msp-batch` (not committed; reproduced in Stage 4 edge batch) showed GnuCOBOL 3.1.2 LINE SEQUENTIAL behavior the README does not state: every CR byte in a CWF line is dropped (not only a trailing one), bytes after column 64 are ignored, short records are space-padded, tabs/NUL/form feed are data, and the first `B` record for an MBI wins. | Runtime behavior of `organization line sequential` reading into `PIC X(64)`. | `cwf_records()` in `python/msp.py` reproduces it; unit test `CwfFileTests`. Recorded as interface behavior to preserve, not policy. |
| 6 | Code clean-up before commit: a one-line `counts.get(...) and counts.__setitem__(...)` expression. | Readability only. | Replaced with an `if`. Tests re-run, pass. |
