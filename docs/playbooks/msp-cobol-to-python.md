# MSP COBOL to Python with evidence

## Overview
Migrate the synthetic CMS Medicare Secondary Payer (MSP) COBOL payment module in
`wstomber/devinexecdemo` to Python, starting from the COBOL-only starter. Prove the
result with three separate evidence layers, explain the legacy code to engineers
who have never read COBOL, and leave a PR for human review. This is a synthetic
educational example. Do not invent CMS internal architecture, staffing, history,
or productivity/performance claims.

## What's Needed From User
- Nothing beyond the session prompt. The default start point is the starter commit
  `37ceca17f110536d55261d5d19aa187781dd8851`. Use a different commit only if the
  prompt names one.
- Any human time spent reviewing or intervening, if the user wants it recorded.
  Otherwise record it as UNKNOWN, never 0.

## Procedure
1. **Set up.** Clone `wstomber/devinexecdemo` and check out the starter commit.
   Create `devin/<unix-ts>-msp-python-migration-live`. Read `DEVIN_TASK.md`,
   `docs/demo-brief.md`, `README.md`, `docs/rules.md`, `docs/cms-example-3.md`,
   `docs/demo-readiness.md`, `docs/demo-runbook.md`. If `cobc` is missing, install
   GnuCOBOL (`sudo apt-get install -y gnucobol gcc make`). Record tool versions and
   the start time in `evidence/live/environment.txt`.
2. **Stage 1 – baseline + explanation.** Run `make doctor` and
   `make build baseline generate test capture-baseline`. Save the log and
   `build/baseline/` under `evidence/live/`. Check the hashes against
   `docs/evidence/cobol-baseline/manifest.json`. Write
   `docs/migration/01-cobol-explanation.md` explaining:
   - inputs/outputs and the 73-byte record;
   - exact cents, framing, and the 4,096-byte/10,000-record limits;
   - validation precedence, state reset, and duplicate IDs;
   - zero-reason precedence, totals, and fatal behavior;
   - the `claim-has-contract` branch and `min(claim-gross, charge-basis)`;
   - why the $13,000 OTAF is not the $12,500 primary accepted in full.

   Commit.
3. **Stage 2 – independent tests BEFORE any Python.** Hand-derive a ledger
   (`tests_policy/expectations.json`) from Pub. 100-05 Ch. 5 §40.8–40.8.3
   (`docs/rules.md`) and the README interface. Give every case a source citation
   and its arithmetic. Never copy values from COBOL output or
   `fixtures/expected.json`. Separate policy cases from interface assumptions.
   Include:
   - CMS-EX3 ($500), the same inputs without an OTAF ($1,500), and CMS-EX1;
   - each of the four limits controlling, equal limits, and one-cent boundaries;
   - valid zeros vs malformed records, and every rejection reason plus its precedence;
   - maximums, and state reset after a rejected record.

   Add batch tests for:
   - CRLF and a missing final newline, empty input, duplicate IDs;
   - 4,096/4,097-byte lines, 10,000/10,001 records, and usage errors.

   Make the runner select its program with `MSP_COMMAND`, defaulting to
   `build/msp-batch`. Run it against COBOL, save the log, and **commit before
   creating any Python file**.
4. **Stage 3 – Python.** Write `python/msp.py` with the same CLI
   (`INPUT OUTPUT TOTALS`), stdlib only, and integer cents. Keep the validation and
   reason precedence, `@`+10-digit provisional IDs, framing, limits, exact CSV
   formatting, and exit code 2 on fatal errors. Run the Stage 2 tests with
   `MSP_COMMAND='python3 python/msp.py'`, unchanged. Add focused unit tests in
   `tests_python/`. Log every correction, with its cause, in
   `evidence/live/corrections.md`. Commit.
5. **Stage 4 – comparison.** Run:
   - `python3 tools/verify.py baseline --command 'python3 python/msp.py'`;
   - `make compare CANDIDATE='python3 python/msp.py'`;
   - `python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/curated.dat`.

   Produce a per-record side-by-side (CSV + Markdown: record, ID, both payments,
   both statuses/reasons, MATCH/MISMATCH, counts, totals) for the curated and
   synthetic batches and an adversarial edge batch. Also compare the fatal paths.
   Keep both programs' raw outputs. Investigate every mismatch to its root cause.
   Commit.
6. **Documentation for maintainers.** Write:
   - `docs/migration/02-rule-map.md` (policy → COBOL lines → tests → Python → result,
     with a policy/interface source column);
   - a COBOL primer for engineers who have never read COBOL, taught with this code's
     DIVISIONs, paragraphs/PERFORM, PIC and COMP-3, copybooks, LINKAGE/CALL by
     reference, INITIALIZE, NUMERIC, STRING, file status, and EBCDIC collation;
   - a line-by-line legacy walkthrough including CMS-EX3 traced through
     `payment.cob`;
   - a COBOL→Python guide covering what changed, what had to stay identical, and
     the translation traps;
   - a maintenance guide;
   - `docs/migration/evidence-index.md` with the seven presentation steps from
     `docs/demo-runbook.md`.

   Append actual commands and events to `docs/templates/session-events.csv`.
7. **Reviewable change.** Push and open a PR against `main` titled
   `[live run] MSP COBOL → Python with evidence`. List the evidence and its limits
   in the description. Do not merge.

## Specifications
- `cobol/`, `fixtures/`, `tools/verify.py`, `tools/fixtures.py`, `tests/` and
  `docs/evidence/` are unchanged (`git diff --stat <starter>..HEAD -- <paths>` is
  empty).
- The Stage 2 commit precedes the first commit containing `python/`.
- The independent tests pass against both COBOL and Python. Comparisons report 0
  mismatches, or every mismatch is explained and resolved.
- CMS-EX3 = 50,000 cents in the policy ledger, COBOL output, and Python output.

## Advice and Pointers
- Use `int` cents. Never `float`. Validate with an explicit ASCII digit set, not
  `str.isdigit()` or `int()` (they accept `+`, spaces, `_` and Unicode digits).
- Read the input as bytes. A blank line is a `BAD_LENGTH` record. A malformed
  contract is `BAD_AMOUNT`, not `BAD_CONTRACT`. A duplicate identifiable ID is
  fatal even on a rejected record.
- Parity shows equivalence to the COBOL on the tested batches. It is not proof of
  Medicare correctness. Say so.

## Forbidden Actions
- Do not modify the starter files listed in Specifications, and do not edit
  evidence to force a pass.
- Do not write Python before the Stage 2 commit.
- Do not merge the PR. Do not push to `main`.
- Do not invent CMS facts, timings, or human time.
