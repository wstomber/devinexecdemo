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
