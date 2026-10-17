# Optional maintainability exercise: JSON batch summary

**Synthetic product exercise, not a CMS policy change.** Leave this unimplemented
in the starter. Devin performs it after completing and verifying the migration.

Customer-style request: consumers want a JSON summary alongside the existing CSV
files. Add an optional `--summary-json PATH` flag to the Python CLI. The original
three positional paths and invocation without flags must continue to work.

The JSON object must contain integer fields `records`, `paid`, `zero`, `invalid`,
and `payment_cents`, with the same values as the existing totals CSV. It must use
the batch's actual counters and total, not a new payment calculator. Require a
separate destination that does not overwrite input or existing CSV outputs. Define
and test failure behavior when JSON cannot be written; never silently report
success for a requested but missing summary.

Devin must first add tests for the new acceptance conditions, then implement the
feature on a new branch/commit after the migration. Verify no-flag compatibility,
JSON/CSV equality, exact integer cents, empty and mixed-validity batches, and write
failure behavior. Run the original unit tests and both curated and 1,000-record
COBOL/Python comparisons again. Payment outputs must remain identical.

Retain a feature PR/diff, commands, test results, old/new invocation examples, and
human intervention/review timing. The CMS-EX3 row must still pay 50,000 cents.
Create and test the native Devin maintainability Playbook specified in
DEVIN_TASK.md. Do not call this an implemented feature or a tested Playbook until
Devin has actually executed the work.
