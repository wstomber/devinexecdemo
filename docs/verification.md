# Executed verification

Verified 2026-10-17 on macOS using GnuCOBOL 3.2.0 and Python 3.12.14.
No GnuCOBOL or Docker was initially available. GnuCOBOL was built from the GNU
3.2 source archive into an isolated workspace prefix, using the installed GMP
library and CommandLineTools C compiler/SDK. No system installation or license
change was made. Docker was unavailable, so **the container build/run was not
executed locally**. The checked-in GitHub Actions workflow provides a Linux and
container verification path; consult its run status for remote evidence.

Executed the equivalents of these commands with explicit local `COBC` and
`PYTHON` overrides and the installed CommandLineTools environment:

```sh
make build baseline generate test
build/msp-batch build/synthetic.dat build/synthetic-results.csv build/synthetic-totals.csv
python3 tools/verify.py compare --report build/comparison-report.json
git diff --check
```

Results:

| Check | Observed result |
| --- | --- |
| Compile with `-free -Wall -debug` | Success, no warnings |
| Independent curated baseline | PASS: all 30 records match IDs/status/reason/exact cents |
| Curated counts | 12 PAID, 9 ZERO, 9 INVALID |
| Curated total | 10,000,450,202 cents |
| Batch/harness tests | 16 tests passed |
| Seeded input generation | 1,000 valid records, seed 20261017, deterministic |
| Synthetic execution and structural reconciliation | 271 PAID, 729 ZERO, 0 INVALID |
| Synthetic observed total (not an independent oracle) | 514,352,570,951 cents |
| No candidate supplied | Direct harness exit 2, result NOT_RUN, migration comparison NOT_RUN |
| Working diff whitespace check | Pass |

The infrastructure tests inject missing, duplicate, unexpected, wrong-ID,
malformed numeric, negative, unknown status/reason, incorrect header, and incorrect
total outputs. Every faulty output is rejected. Two additional comparisons alter
one cent with a correspondingly changed total, or change one valid zero reason to
another valid zero reason; both comparisons fail with exactly one discrepancy.
Temporary replay scripts only copy captured output and corrupt it. They contain
no payment logic and are deleted after the tests.

Tests also exercise a successful replay to check harness plumbing, using a
candidate command against curated expectations, crash/nonzero exit, missing
executable, missing output, timeout, blank and empty batches, CRLF, EOF without
newline, control bytes, duplicate IDs including identifiable invalid records,
oversized lines, missing input, unwritable output, the batch limit, serialization
validation, and the seeded batch. Curated expectations exercise the payment
boundaries. No unexecuted check is counted as passed.

`docs/evidence/` preserves the initial baseline report and explicit missing-candidate
report. They describe the starter at verification time; regenerate `build/` reports
for subsequent changes. **There is no Python payment implementation, no completed
Devin migration, and no Python-versus-COBOL migration parity result yet.**

The public source was retrieved and reviewed, including visual inspection of PDF
pages 78–84. Source retrieval metadata, exact page mapping, fixture rationales,
and the Example 4 inconsistency are recorded in rules.md. Policy coverage is
limited to that documented scope. Generated-input parity cannot prove policy
correctness, and no performance or production-readiness claims were measured.
