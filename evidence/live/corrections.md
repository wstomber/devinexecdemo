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

## Stage 4 - comparison harness (`tools/side_by_side.py`)

No correction was made to `python/msp.py` in Stage 4. All corrections were to the new comparison harness.

| # | What failed | Cause | Correction |
|---|---|---|---|
| 7 | Edge batch: COBOL (correctly) exited 2, "invalid CWF reference record" | Harness-authoring error: three quirk CWF `B` records had a 10-byte MBI, which shifted the date columns. | Rebuilt the quirk records from explicit 11-byte MBIs, with a length assertion. |
| 8 | Fatal paths `duplicate-valid-id` / `duplicate-rejected-id`: both programs exited 0 | Harness-authoring error: the hand-typed record was 91 bytes, so both programs saw `BAD_LENGTH` provisional IDs (no duplicate). Both programs agreed. | Build the record from explicit fields with a 92-byte assertion. Both now exit 2 with `duplicate claim ID`. |
| 9 | Fatal paths `missing-input`, `missing-cwf`, `results-dir-missing`, `line-4098-no-lf`: first stderr lines differed | Not a behavior difference: both exit 2 with no stdout. On these paths COBOL prints only its generic line plus `; file status ii/oo/tt` (GnuCOBOL file-status codes), which Python has no equivalent for. | The fatal comparison compares the first stderr line up to `; file status`. Full stderr of both programs is kept in `evidence/live/comparison/fatal/`. |
| 10 | Edge batch exercised few PAID / DUPLICATE / MSP outcomes (70 / 1 / 5 of 3,000) | Coverage, not a failure: uniform random amounts rarely produce payable claims. | 35% of edge records now use a payable shape aimed at the CWF history dates. Re-run: 388 PAID, 14 DUPLICATE, 30 MSP_PRIMARY_NOT_BILLED. |

Final Stage 4 result: curated 33/33, synthetic 1000/1000, edge 3000/3000 MATCH with byte-identical results and totals files; fatal paths 21/21 MATCH.
