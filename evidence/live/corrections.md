# Corrections log (live run)

Every correction made during this run, with its cause. Nothing was changed to make
a check pass by editing expectations to match observed output.

| # | Stage | What failed | Cause | Correction |
| --- | --- | --- | --- | --- |
| 1 | 2 (before Python) | `tests_policy` harness raised `AssertionError ('FULL-OVER-ALL', 'id')` on the first run against COBOL | Authoring error. 13 ledger case IDs were longer than the 12-byte ID field, so the serializer produced misaligned records. No program output was involved | Shortened those IDs (e.g. `FULL-OVER-ALL` -> `FULL-OVERALL`) in both `id` and `expect[0]`. Added an explicit `> 12` check to `harness.claim_line`. No expected status, reason or amount changed |
| 2 | 3 | None | `python/msp.py` passed all 23 Stage 2 tests (`MSP_COMMAND='python3 python/msp.py'`, unchanged) and all 29 unit tests on the first execution | None needed |

Design decisions taken *before* the first Python run, to match observed COBOL
runtime behavior (from probes of `build/msp-batch` with throwaway CWF files in
`/tmp`, recorded in `docs/migration/01-cobol-explanation.md`):

- CWF line-sequential read: every CR byte is dropped, the line is truncated to 64
  bytes and space-padded, and a trailing segment made only of CRs is EOF. These
  were probed because Python's `splitlines()` or `rstrip()` would differ.
- Outputs are opened (truncated) only after the CWF and input files load, and rows
  are written as they are produced. A fatal error therefore leaves the same kind
  of partial output the COBOL leaves. Stage 4 checks this.
