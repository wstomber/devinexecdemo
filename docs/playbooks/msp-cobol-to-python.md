# MSP COBOL to Python with evidence

## Overview
Migrate the synthetic CMS Medicare Secondary Payer (MSP) COBOL claim module in
`wstomber/devinexecdemo` to Python, starting from the COBOL-only starter. The module
calculates the MSP secondary payment, then runs a small synthetic CWF pre-payment
check (entitlement, duplicate, MSP primary billed) that decides whether the
calculated payment is released. Prove the
result with three separate evidence layers, explain the legacy code to engineers
who have never read COBOL, and leave a PR for human review. This is a synthetic
educational example. Do not invent CMS internal architecture, staffing, history,
or productivity/performance claims.

## What's Needed From User
- Nothing beyond the session prompt. The default start point is the starter commit
  `be0b00ec5a2369d50a34d351694b187ae2300fe4` (branch `demo/starter-be0b00e`). Use a different commit only if the
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
   - inputs/outputs, the 92-byte record (MBI and service date included) and the
     CWF reference file (`B` beneficiary and `H` history records);
   - exact cents, framing, and the 4,096-byte/10,000-record limits;
   - validation precedence, state reset, and duplicate IDs;
   - zero-reason precedence, totals, and fatal behavior;
   - the `claim-has-contract` branch and `min(claim-gross, charge-basis)`;
   - why the $13,000 OTAF is not the $12,500 primary accepted in full;
   - the CWF check in `cobol/cwf.cob`: its order (entitlement, duplicate, MSP
     primary not billed), why only valid claims are sent, and calculated vs
     released amounts.

   Commit.
3. **Stage 2 – independent tests BEFORE any Python.** Hand-derive a ledger
   (`tests_policy/expectations.json`) from Pub. 100-05 Ch. 5 §40.8–40.8.3, the CWF
   pre-payment rules (Pub. 100-04 Ch. 27 §20; Pub. 100-05 Ch. 5 §10.1, see
   `docs/rules.md`) and the README interface. Write your own synthetic CWF
   reference data for the ledger; do not reuse `fixtures/cwf.json`. Give every case a source citation
   and its arithmetic. Never copy values from COBOL output or
   `fixtures/expected.json`. Separate policy cases from interface assumptions.
   Include:
   - CMS-EX3 ($500), the same inputs without an OTAF ($1,500), and CMS-EX1;
   - each of the four limits controlling, equal limits, and one-cent boundaries;
   - valid zeros vs malformed records, and every rejection reason plus its precedence;
   - maximums, and state reset after a rejected record;
   - every CWF outcome with its boundaries: entitlement start/end dates, MBI not on
     file, duplicate vs one-cent/one-day different, MSP period start/end, primary 0
     vs paid, check precedence, ZERO claims still sent to CWF, CMS-EX3 accepted and
     $500 released, and malformed MBI/service date (`BAD_MBI`, `BAD_DATE`).

   Add batch tests for:
   - CRLF and a missing final newline, empty input, duplicate IDs, a missing or
     malformed CWF file;
   - 4,096/4,097-byte lines, 10,000/10,001 records, and usage errors.

   Make the runner select its program with `MSP_COMMAND`, defaulting to
   `build/msp-batch`. Run it against COBOL, save the log, and **commit before
   creating any Python file**.
4. **Stage 3 – Python.** Write `python/msp.py` with the same CLI
   (`INPUT CWF OUTPUT TOTALS`), stdlib only, and integer cents. Keep the validation and
   reason precedence, `@`+10-digit provisional IDs, framing, limits, exact CSV
   formatting, the CWF check order and the released amount, and exit code 2 on
   fatal errors (including a malformed CWF reference record). Run the Stage 2 tests with
   `MSP_COMMAND='python3 python/msp.py'`, unchanged. Add focused unit tests in
   `tests_python/`. Log every correction, with its cause, in
   `evidence/live/corrections.md`. Commit.
5. **Stage 4 – comparison.** Run:
   - `python3 tools/verify.py baseline --command 'python3 python/msp.py'`;
   - `make compare CANDIDATE='python3 python/msp.py'`;
   - `python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/curated.dat`.

   Produce a per-record side-by-side (CSV + Markdown: record, ID, both calculated
   payments, both statuses/reasons, both CWF decisions/reasons, both released
   amounts, MATCH/MISMATCH, counts, totals) for the curated and
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
     `payment.cob` and `cwf.cob`;
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
- CMS-EX3 = 50,000 cents calculated, `ACCEPTED`, and 50,000 cents released in the
  policy ledger, COBOL output, and Python output.

## Advice and Pointers
- Use `int` cents. Never `float`. Validate with an explicit ASCII digit set, not
  `str.isdigit()` or `int()` (they accept `+`, spaces, `_` and Unicode digits).
- Read the input as bytes. A blank line is a `BAD_LENGTH` record. A malformed
  contract is `BAD_AMOUNT`, not `BAD_CONTRACT`. A duplicate identifiable ID is
  fatal even on a rejected record.
- A CWF rejection is not a payment-calculation result: keep `payment_cents` as
  calculated and set only `released_cents` to 0. CWF duplicates are matched
  against the `H` history records, not against other claims in the batch.
- Parity shows equivalence to the COBOL on the tested batches. It is not proof of
  Medicare correctness. Say so.

## Forbidden Actions
- Do not modify the starter files listed in Specifications, and do not edit
  evidence to force a pass.
- Do not write Python before the Stage 2 commit.
- Do not merge the PR. Do not push to `main`.
- Do not invent CMS facts, timings, or human time.
