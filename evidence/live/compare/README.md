# Stage 4 comparison evidence (live run)

Every file here comes from actually running both programs. The commands and
their output are in `../stage4-comparison.log`. COBOL is `build/msp-batch`,
built from the unchanged `cobol/`. Python is `python3 python/msp.py`.

| Batch | Input | CWF | Records | Strict verifier (`tools/verify.py`) | Side-by-side | Raw files byte-identical |
| --- | --- | --- | ---: | --- | --- | --- |
| Curated (starter, 33) | `curated.dat` | `cwf.dat` | 33 | `curated-comparison-report.json` PASS; `python-baseline-report.json` (Python vs `fixtures/expected.json`) PASS | `curated-side-by-side.{md,csv}` 33 MATCH / 0 MISMATCH | YES |
| Seeded synthetic (seed 20261017) | `synthetic.dat` | `cwf.dat` | 1,000 | `synthetic-comparison-report.json` (`make compare`) PASS | `synthetic-side-by-side.{md,csv}` 1,000 / 0 | YES |
| Adversarial edge, ASCII (seed 20261020) | `edge.dat` | `edge-cwf.dat` | 3,029 | `edge-comparison-report.json` PASS | `edge-side-by-side.{md,csv}` 3,029 / 0 | YES |
| Adversarial edge, with non-ASCII bytes | `edge-bytes.dat` | `edge-bytes-cwf.dat` | 3,031 | Not run. The starter verifier decodes input as ASCII only and fails with a decode error | `edge-bytes-side-by-side.{md,csv}` 3,031 / 0 | YES |
| Fatal / usage paths | generated per scenario | — | 18 scenarios | — | `fatal-paths.{md,json}` 18 MATCH (exit 2, stderr, empty stdout; leftover outputs identical) | — |

The edge batches come from `tools/edge_batch.py`, which writes inputs only and
no expectations. They include:

- CR inside and at the end of a record, CR CR LF, a lone CR, a blank line, 92
  spaces, 92 NULs, a NUL in the ID, a tab in the MBI, lowercase IDs, Arabic-Indic
  digits and `É` (bytes variant only), and a 4,096-byte line;
- 2025-02-30 and year 0000;
- maximum amounts, CMS-EX3, and a final record with no newline;
- 3,000 seeded mutated records with random months 00–13 and days 00–32, and
  random byte damage at positions 7–92.

The edge CWF file exercises CRLF, a CR inside a record, a line longer than 64
bytes, a duplicate `B` MBI (first wins), an entitlement with from > to, trailing
spaces on an `H` record, history for an MBI not on file, and a CR-only final
segment.

Every outcome appears in the edge batch, including all seven invalid reasons,
all four payment reasons, `NOT_ENTITLED`, `DUPLICATE`, `MSP_PRIMARY_NOT_BILLED`
and `DISPOSITION_01`.

## Mismatch investigation

The final runs reported no record, totals or fatal-path mismatches. Two
differences came up during Stage 4 and were investigated to root cause (see
`../corrections.md` #3–#4):

1. **Fatal path, "input is a directory".** Both programs exited 2, but COBOL left
   OUTPUT truncated to the CSV header and TOTALS empty, while Python left the
   stale files untouched. Cause: GnuCOBOL `OPEN INPUT` succeeds on a directory
   and the first `READ` fails, so outputs are already open. Python's `open()`
   fails earlier. Classification: record handling (file-open order). Python now
   uses `os.open` and reads after opening the outputs. Rerun: leftovers are
   identical.
2. **First edge CWF file rejected by both programs (exit 2 / exit 2).** This was
   not a program difference. My generator wrote non-space bytes at positions
   45–64 of a `B` record, and then a 43-byte record. Both programs correctly
   treated the file as malformed. The generator was fixed.

## What this does and does not show

Agreement shows that the Python port behaves like this COBOL on these batches
(6,093 records plus 18 fatal scenarios), down to the byte. It does **not** prove
Medicare correctness. Both programs could share the same policy error. The
policy anchor is the separate Stage 2 ledger (`tests_policy/`), and it covers
only the cases it lists.
