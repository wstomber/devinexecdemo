# Corrections log (live run)

Every correction made during this run, with its cause. Nothing was changed to make
a check pass by editing expectations to match observed output.

| # | Stage | What failed | Cause | Correction |
| --- | --- | --- | --- | --- |
| 1 | 2 (before Python) | `tests_policy` harness raised `AssertionError ('FULL-OVER-ALL', 'id')` on the first run against COBOL | Authoring error. 13 ledger case IDs were longer than the 12-byte ID field, so the serializer produced misaligned records. No program output was involved | Shortened those IDs (e.g. `FULL-OVER-ALL` -> `FULL-OVERALL`) in both `id` and `expect[0]`. Added an explicit `> 12` check to `harness.claim_line`. No expected status, reason or amount changed |
| 2 | 3 | None | `python/msp.py` passed all 23 Stage 2 tests (`MSP_COMMAND='python3 python/msp.py'`, unchanged) and all 29 unit tests on the first execution | None needed |
| 3 | 4 (fatal-path comparison) | "input is a directory": both exit 2, but COBOL left OUTPUT = header and TOTALS = empty, while Python left the stale files | GnuCOBOL `OPEN INPUT` succeeds on a directory and the `READ` fails after the outputs are open. Python `open()` raised before the outputs were opened | `run()` now opens input with `os.open` (which succeeds on a directory), opens and truncates the outputs, writes the header, then reads (`read_all`). Reran unit, Stage 2 and all comparisons: leftovers now identical |
| 4 | 4 (edge generator) | COBOL and Python both exited 2 on the first edge CWF file | Authoring error in `tools/edge_batch.py`: a `B` record had non-spaces at 45–64, and the fix attempt produced a 43-byte record. Both programs were right to reject it | Fixed the generator literal. Added an `--ascii` mode, because `tools/verify.py` cannot decode non-ASCII input, and kept a separate non-ASCII batch for side-by-side only |

Design decisions taken *before* the first Python run, to match observed COBOL
runtime behavior (from probes of `build/msp-batch` with throwaway CWF files in
`/tmp`, recorded in `docs/migration/01-cobol-explanation.md`):

- CWF line-sequential read: every CR byte is dropped, the line is truncated to 64
  bytes and space-padded, and a trailing segment made only of CRs is EOF. These
  were probed because Python's `splitlines()` or `rstrip()` would differ.
- Outputs are opened (truncated) only after the CWF and input files load, and rows
  are written as they are produced. A fatal error therefore leaves the same kind
  of partial output the COBOL leaves. Stage 4 checks this.
