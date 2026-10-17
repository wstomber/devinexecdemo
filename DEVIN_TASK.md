# Devin handoff: MSP modernization, evidence, and native Playbooks

**Read docs/demo-brief.md first.** This is a Cognition interview presentation with
CMS as the selected customer scenario. We chose COBOL modernization from the
assignment's three themes and are using independent tests and exact comparisons
to make the result assessable. The business question is whether you can understand
an unfamiliar legacy payment rule, migrate it safely within this scope, and give
a human reviewable evidence. First produce actual rehearsal examples, then native
Playbooks for repeatable fresh/live runs. Do not invent CMS internal facts or
productivity claims. The $500 contractual-cap case is the main business story.
Begin your explanation with the customer problem, why that financial difference
matters, the three evidence layers, and what the human reviewer should assess;
then proceed with execution rather than stopping at an outline.

Start from this prepared repository on `main`, or the pinned starter commit supplied
by the presenter. Create a new working branch. Read README.md, docs/rules.md,
docs/cms-example-3.md, docs/demo-readiness.md, and docs/demo-runbook.md.
This is a synthetic educational CMS MSP application, not CMS production source.
Eligibility, covered-service determination, primary pricing, gross Medicare
pricing, and applicable deductible/coinsurance are upstream inputs.

Implement and execute the remaining work. Codex prepared and verified the COBOL
starting system. You own the Python migration, substantive new policy-derived
tests, complete policy/COBOL/test/Python rule map, demonstration comparison output,
and repeatable **native Devin Playbooks**. Do not describe planned work as executed.

## Stage 1: verify and explain the starting system

1. Record the starting commit, environment versions, and UTC session start. Run:

   ```sh
   make doctor
   make build baseline generate test capture-baseline
   ```

   Docker is available as documented in README.md. Python tooling uses only the
   standard library. Retain build/baseline/ and its commands.log and manifest.json.
   Compare its source and input hashes with docs/evidence/cobol-baseline/. Treat
   the checked-in capture as observed COBOL behavior, not a payment oracle.
2. Explain inputs, outputs, exact cents, record framing, validation, state reset,
   duplicate IDs, limits, zero reasons, counts, totals, and failure behavior.
3. Identify `calculate-prospective-payment` in cobol/payment.cob. Trace the
   `claim-has-contract` branch, replacement of `charge-basis`, and
   `min(claim-gross, charge-basis)`. Explain the difference between a contractual
   total acceptance amount and accepting the primary payment itself in full.

## Stage 2: establish independent tests BEFORE implementing Python

4. Read the included CMS §40.8.3 Example 3 excerpt and surrounding source rules.
   Derive a new set of expected payments by hand from those rules. Record each
   input, arithmetic, source/page, assumptions, and expected status/reason in new
   test files or a new expectation ledger. Do not derive expectations by copying
   either executable's outputs or merely relabeling the starter ledger. You may
   cross-check the existing independent ledger after documenting your derivation.
5. Include the published example plus cases where the contractual cap controls,
   gross or deductions control, limits are equal, and amounts differ by one cent.
   Include valid zeros, full payment, malformed/unsupported records, duplicate IDs,
   state reset, and maximum amounts. Explain interface assumptions separately
   from CMS policy.
6. Run these tests against the COBOL executable and retain the command, result,
   and source commit. Commit this passing tests-and-expectations stage BEFORE
   adding the Python implementation. Existing starter infrastructure tests do not
   count as substantive tests you created. If code and policy conflict, flag the
   discrepancy for review; do not rewrite the baseline or expected results to hide it.

## Stage 3: migrate and unit-test

7. Implement a small Python CLI at python/msp.py, preserving the three positional
   paths `INPUT OUTPUT TOTALS` and the documented fixed-width/CSV contract.
   Use integer cents or exact decimal arithmetic, never binary floating point.
   Preserve malformed versus valid-zero behavior, reason precedence, identifiers,
   record counts, totals, transport bounds, and fatal exits.
8. Run the tests established in Stage 2 against Python. Add focused Python unit
   tests for individual functions and boundaries. Investigate every failure and
   correct the implementation. Keep candidate tests separate from starter tests
   and report their exact command. Record any correction and its cause.
9. Produce a complete rule map: policy section/page -> COBOL paragraph and branch
   -> independently derived test IDs -> Python function/lines -> observed result.
   The starter rules.md is background interpretation, not your completed rule map.

## Stage 4: complete and execute the demonstration comparison

10. The core verifier already exists and has infrastructure fault-injection tests.
    Preserve it. Complete the demonstration workflow in NEW files: retain both
    executables' outputs, call the existing verifier, and generate a readable
    side-by-side CSV/Markdown table with record number, claim ID, COBOL payment,
    Python payment, both statuses/reasons, and explicit MATCH/MISMATCH indicators.
    Include counts and batch totals. Do not substitute a table for strict checks.
11. Execute and retain all three evidence layers separately:

    ```sh
    make build baseline generate test capture-baseline
    # Also run your independently derived tests and focused Python unit tests.
    python3 tools/verify.py baseline --command 'python3 python/msp.py' \
      --report build/python-baseline-report.json
    make compare CANDIDATE='python3 python/msp.py'
    python3 tools/verify.py compare --candidate 'python3 python/msp.py' \
      --input build/curated.dat --report build/curated-comparison-report.json
    # These executions preserve the real curated outputs for the presentation:
    build/msp-batch build/curated.dat build/cobol-results.csv build/cobol-totals.csv
    python3 python/msp.py build/curated.dat build/python-results.csv build/python-totals.csv
    ```

    Retain synthetic outputs as well. The core verifier uses temporary files;
    its JSON alone does not preserve the per-claim files needed for the demo.
12. Investigate EVERY difference. Save a reproducible input and classify its cause
    as calculation, rounding, validation, record handling, or another stated cause.
    Record resolution and rerun evidence. Use exact cents; do not add tolerances.
    Matching 1,000 synthetic records expands coverage, not policy correctness.

## Required visible case: CMS-EX3

Show this same stable ID in the explanation, pre-migration tests, Python unit
coverage, rule map, and comparison report:

- Covered/billed charges: $15,000; gross Medicare payable: $14,000.
- Primary payment: $12,500; obligatory provider acceptance: $13,000.
- Remaining deductible: $1,556, labeled **historical example input**; coinsurance $0.
- Secondary payment: **$500**. Ignoring the acceptance limit would produce $1,500.
- Primary payment itself was not accepted in full (`full=N`).

## Stage 5: create completed examples AND reusable native Devin Playbooks

13. Complete one real rehearsal migration and retain a reviewable example: starting
    and result commits, your Devin session link/ID, actual commands and exit codes,
    new tests, rule map, outputs, comparison reports, and a PR or reviewable branch.
    Add an example index and an exact seven-step presentation guide. Do not label
    an example complete until the migration and evidence have actually executed.
14. Create and save native Devin Playbooks in the user's Devin workspace:

    - **MSP COBOL to Python with evidence**: parameterize repository, pinned
      starter ref, new branch, candidate command, seed, and evidence directory;
      automate the stages above, including tests before implementation and the
      separate reviewable commits.
    - **MSP synthetic maintainability change**: use the optional exercise in
      docs/follow-up-exercise.md, starting from a completed migration. Preserve
      prior CSV behavior and prove unchanged payment parity with new feature tests.

    Each Playbook needs prerequisites, inputs, ordered actions, commands, expected
    artifacts, success/failure conditions, and fresh-run instructions. Return the
    actual saved Playbook names, links/IDs, and versions. Markdown instructions in
    this repo are a handoff specification, not proof a native Playbook exists.
    If your workspace lacks Playbook creation access, report NOT_CREATED and leave
    ready-to-paste definitions; do not claim they were saved or tested.
15. Test a fresh live-style run from the SAME PINNED starter commit on a new branch
    or worktree. Do not reuse the rehearsal's Python files or recorded results as
    evidence of this fresh run. A presenter may show the completed rehearsal as
    a prebuilt example, then launch a new Playbook run live and report its current
    status honestly. Record each session separately.
16. Use docs/templates/session-events.csv for real commands/events and human
    intervention/review timing. Unknown human time stays unknown, not zero.
    Do not claim efficiency gains without a comparable measured manual baseline.
17. Prepare a reviewable code change with Python, new tests/expectations, rule map,
    new comparison presentation tooling, reproducible results, timing record,
    Playbook identities, and replay instructions. Open a PR if supported; otherwise
    leave a branch and ready-to-use PR description. Report unexecuted checks and
    remaining risks. Claim consistency only for the tested, documented scope.

## Preserve the starting evidence

Do not modify existing cobol/, fixtures/, tools/verify.py, tools/fixtures.py,
tools/capture_baseline.py, starter tests, or docs/evidence/ to obtain a pass.
Add code, tests, maps, and comparison wrappers in new files. Keep the original
monetary interface and policy unchanged. The optional maintainability exercise
is synthetic and must be labeled that way. No dashboard, deployment, fabricated
performance claims, or staged application defects are needed.
