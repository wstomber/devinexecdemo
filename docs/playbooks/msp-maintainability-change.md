# MSP synthetic maintainability change

## Overview
Show that the migrated Python MSP module in `wstomber/devinexecdemo` can be
safely maintained. Implement the synthetic `--summary-json` option from
`docs/follow-up-exercise.md`, tests first, without changing any existing CSV
output. This is a synthetic exercise, not a CMS requirement.

## What's Needed From User
- The branch or PR containing the finished migration (`python/msp.py`). Default:
  `main` if it contains `python/msp.py`, otherwise the most recent migration
  branch `devin/*-msp-python-migration`.

## Procedure
1. Clone the repo, check out the migration branch, and create
   `devin/<unix-ts>-msp-summary-json`. Install GnuCOBOL if `cobc` is missing. Read
   `docs/follow-up-exercise.md`, `docs/migration/06-maintaining.md` and
   `docs/migration/02-rule-map.md`.
2. Re-run the existing evidence and save the log: `make build generate`,
   `MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy`,
   `python3 -m unittest discover -s tests_python`, and
   `make compare CANDIDATE='python3 python/msp.py'`.
3. **Tests first.** Write tests for the exact JSON contract in
   `docs/follow-up-exercise.md`: field names, types, the integer-cents total,
   behavior when the option is absent, a fatal batch, and the option combined with
   positional paths, an empty batch, a mixed-validity batch, a destination equal to
   any positional path (rejected, exit 2), and an unwritable JSON destination
   (exit 2; never report success without the summary). Run them, confirm they
   fail for the right reason, and commit.
4. Implement the option in `python/msp.py` only. The positional CLI and both CSVs
   must stay byte-identical when the option is absent and when it is present.
5. Re-run every layer. Then show that the CSVs are unchanged: run
   `python3 tools/demo_compare.py --input build/curated.dat` and the synthetic
   batch with `--python 'python3 python/msp.py --summary-json build/s.json'`. Both
   must still be byte-identical to the COBOL, and CMS-EX3 must still pay 50,000
   cents. Record old/new invocation examples.
6. Update the rule map and maintenance guide. Record the commands in
   `docs/templates/session-events.csv`. Open a PR titled
   `[maintainability] --summary-json for python/msp.py`, describing what changed
   and the parity evidence. Do not merge.

## Specifications
- The test commit precedes the implementation commit.
- All prior tests pass. COBOL parity stays at 0 mismatches. The JSON totals equal
  `totals.csv`.
- The COBOL and the starter files are unchanged.

## Forbidden Actions
- Do not change the CSV format, the reason codes, or the payment logic.
- Do not modify `cobol/`, `fixtures/`, `tools/verify.py` or the starter tests.
- Do not merge.
