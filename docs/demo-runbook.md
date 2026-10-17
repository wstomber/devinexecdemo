# Seven-step demonstration: completed example and fresh live run

This is a synthetic educational MSP application derived from public CMS rules.
It is not CMS production code. Claim consistency only for the tested scope.

Use two modes. First let Devin actually complete a rehearsal and save a reviewable
example. During the presentation you may show that completed example, then launch
its tested native Devin Playbook on a fresh branch from the same pinned starter
commit. Label each screen as recorded rehearsal, current live execution, or planned
work. A saved transcript is not evidence that a new live session has completed.

Before Devin begins, record the prepared starter commit with `git rev-parse HEAD`.
Keep that immutable SHA in the Playbook and session record. Later, main may contain
the completed migration; a live modernization run must still start from the pinned
COBOL-only commit. Use a fresh checkout/worktree, not a destructive reset or a
checkout contaminated by rehearsal Python files.

## Click path and evidence

| Step | Click / command | What the audience should see |
| --- | --- | --- |
| 1. Baseline | `make doctor build baseline generate test capture-baseline`; open `build/baseline/curated-results.csv` and `manifest.json` | Real COBOL execution, 30 stable records, expected counts and totals; no Python candidate yet |
| 2. Explanation | Devin's source explanation; open `cobol/payment.cob`, `calculate-prospective-payment` | Contract branch replaces charge basis before the minimum cap; eligibility and pricing are upstream |
| 3. Existing tests | Open Devin's separate pre-migration test commit and its executed test log | Independently derived expectations existed and passed against COBOL BEFORE Python was implemented |
| 4. Python and tests | Open Devin's Python diff, focused unit tests, and actual execution log | Exact arithmetic, function boundaries, invalid/zero distinction, and test results; corrections explained |
| 5. Comparison | Run the existing verifier plus Devin's new presentation wrapper; open both retained CSVs and its side-by-side table | Claim IDs, both payments, both statuses/reasons, MATCH/MISMATCH, counts and totals on curated and 1,000 seeded records |
| 6. $500 case | Filter/open `CMS-EX3` in source explanation, pre-migration tests, rule map, and comparison | $13,000 acceptance minus $12,500 primary leaves $500; ignoring acceptance would produce $1,500; $1,556 is historical input |
| 7. Reviewable change | Open Devin's PR or branch/description, evidence index, rule map, and native Playbook | Python, tests, completed mapping, new comparison presentation tooling, reports, reproducible inputs, real timing, limitations |

The explanation, substantive tests, Python, complete rule map, side-by-side table,
completed example, and native Playbook are **Devin deliverables**, not starter
artifacts. The existing 17 tests exercise starter/batch/harness infrastructure and
do not satisfy Devin's obligation to create policy-derived tests.

## Commands and baseline facts

```sh
make doctor build baseline generate test capture-baseline
# No candidate yet: this must report NOT_RUN and exit nonzero.
make compare
# After Devin implements python/msp.py:
python3 tools/verify.py baseline --command 'python3 python/msp.py' \
  --report build/python-baseline-report.json
make compare CANDIDATE='python3 python/msp.py'
python3 tools/verify.py compare --candidate 'python3 python/msp.py' \
  --input build/curated.dat --report build/curated-comparison-report.json
build/msp-batch build/curated.dat build/cobol-results.csv build/cobol-totals.csv
python3 python/msp.py build/curated.dat build/python-results.csv build/python-totals.csv
```

Run Devin's independent tests and Python unit-test command too. Devin must add
commands to retain synthetic outputs and generate the presentation table. The
core harness deletes its temporary outputs; its JSON report alone does not give
the side-by-side view required for step 5.

Curated baseline: 12 PAID, 9 ZERO, 9 INVALID; total 10,000,450,202 cents.
The seeded synthetic batch expands coverage and has no independent payment oracle.
Its observed counts and total are in the retained manifest, not policy truth.
The complete published case is in docs/cms-example-3.md; its fixture ID is CMS-EX3.

## Rehearsal and live readiness gates

A completed rehearsal is ready to show only when Devin supplies its session ID,
starting/result commits, successful command logs, its independently derived tests,
Python unit results, curated and synthetic comparisons, all difference resolutions,
and a reviewable change. Use a small index linking each of the seven screens.

A Playbook is ready for a live attempt only after it is actually saved in Devin
and run from a fresh starter checkout. Record its actual name, ID/link, version,
parameters, and fresh-session results. If Playbook creation or execution is not
available, mark NOT_CREATED or NOT_RUN and state the missing access. Do not call
these repository instructions an installed or tested native Devin Playbook.

Use docs/templates/session-events.csv for commands, outcomes, human intervention,
and review time. Keep unknown timing unknown. Efficiency is unproven without a
comparable manually completed baseline. Do not imply a speedup from elapsed agent
time alone. A synthetic optional maintainability request is specified in
docs/follow-up-exercise.md; it must be shown as a separate exercise after migration.

There are no staged application defects or invented benchmark claims. The temporary
replay stubs in starter tests only verify that the comparison infrastructure detects
bad output; they are not a Python migration or customer-facing performance proof.
