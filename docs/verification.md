# Executed verification

Latest re-verification: Ubuntu Linux 6.8 with GnuCOBOL 3.1.2.0 and Python 3.10.12
(`make build baseline generate test capture-baseline`), including the CWF
pre-payment step and its malformed-reference, MBI and date-of-service tests. The
table below shows that run. The original preparation notes follow.

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
build/msp-batch build/synthetic.dat build/cwf.dat build/synthetic-results.csv build/synthetic-totals.csv
python3 tools/verify.py compare --report build/comparison-report.json
git diff --check
```

Results:

| Check | Observed result |
| --- | --- |
| Compile with `-free -Wall -debug` | Success, no warnings |
| Independent curated baseline | PASS: all 33 records match IDs/status/reason/exact cents/CWF decision/released cents |
| Curated counts | 15 PAID, 9 ZERO, 9 INVALID; CWF 21 ACCEPTED, 3 REJECTED |
| Curated totals | 10,001,694,602 cents calculated; 10,000,450,202 cents released |
| Batch/harness tests | 20 tests passed |
| Seeded input generation | 1,000 valid records, seed 20261017, deterministic |
| Synthetic execution and structural reconciliation | 271 PAID, 729 ZERO, 0 INVALID; CWF 736 ACCEPTED, 264 REJECTED |
| Synthetic observed totals (not an independent oracle) | 485,289,809,347 cents calculated; 344,091,123,732 released |
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

The first Ubuntu CI run with GnuCOBOL 3.1.2 exposed silent truncation of oversized
LINE SEQUENTIAL input that the local 3.2 runtime rejected. The reader now uses
fixed one-byte sequential reads and explicit line-length enforcement, preserving
the same interface across both versions. The regression tests cover 4,096-byte
and 4,097-byte lines with LF, CRLF, and no final newline. All 20 tests pass
locally after this correction; consult the PR checks for the Linux/container
result on the final commit.

`docs/evidence/` preserves the initial baseline report and explicit missing-candidate
report. They describe the starter at verification time; regenerate `build/` reports
for subsequent changes. **There is no Python payment implementation, no completed
Devin migration, and no Python-versus-COBOL migration parity result yet.**

The public source was retrieved and reviewed, including visual inspection of PDF
pages 78–84. Source retrieval metadata, exact page mapping, fixture rationales,
and the Example 4 inconsistency are recorded in rules.md. Policy coverage is
limited to that documented scope. Generated-input parity cannot prove policy
correctness, and no performance or production-readiness claims were measured.

## Demo preparation and retained execution

The preparation update adds `make doctor` and `make capture-baseline`. Executed
both locally, reran all 17 infrastructure tests and the 30 independent curated
expectations, and captured the full curated/synthetic input and output files.
Two separate captures had identical input/output/report hashes. The retained
CMS-EX3 output is exactly 50,000 cents. A deliberately failing executable made
capture return 1 with a FAIL manifest, and a missing compiler made doctor fail.

The immutable starting capture is in docs/evidence/cobol-baseline/. Its source
commit is a964d7085bc8bb5bb0d144e2fb3dbc1964bfc540, the published COBOL source
state before the new evidence/preparation files are committed. Source hashes
record the actual files used. No baseline payment source, curated expectations,
or existing verifier checks were changed for this preparation.

The included CMS excerpt, seven-step runbook, readiness checklist, timing template,
and optional synthetic follow-up are starting conditions. New policy-derived tests,
Python, the complete migration rule map, retained dual-executable presentation
reports, completed Devin examples, and native Devin Playbooks remain unexecuted
Devin work. This environment has no connected Devin execution capability. CI
checks fresh capture hashes and builds/runs the Docker environment; consult the
preparation commit's workflow result for those remote checks.
