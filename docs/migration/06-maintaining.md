# Maintaining the migrated program

This page is for whoever changes `python/msp.py` next, possibly years from now,
with no access to the people who wrote either version.

## Where the knowledge lives

| Question | Look here |
|---|---|
| What is the business rule and where did it come from? | `docs/rules.md`, `docs/cms-example-3.md`, `docs/migration/02-rule-map.md` (Source column) |
| Is a behavior CMS policy or just this interface's convention? | `02-rule-map.md`; `tests_policy/expectations.json` → `interface_assumptions` |
| What did the legacy code do, exactly? | `cobol/` (unchanged), `04-legacy-walkthrough.md` |
| What COBOL concepts do I need to read it? | `03-cobol-primer.md` |
| Why is the Python written this way? | `05-cobol-to-python.md` |
| What evidence shows it works? | `docs/migration/evidence-index.md` |

## Safe change procedure

1. **Classify the change.** Is it a policy change (it changes a payment) or an
   interface change (format, reason codes, limits)? Write down the source.
2. **Tests first.** Add or modify cases in `tests_policy/expectations.json`
   with hand-derived arithmetic and a source citation. Run them; they should
   fail against the current code. Commit that before changing the code.
3. **Change `python/msp.py`.** Keep amounts as `int` cents. Keep the order of
   the `validate` and `calculate` checks unless the change is meant to change
   precedence.
4. **Run all three layers.**
   ```sh
   MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
   python3 -m unittest discover -s tests_python -v
   make compare CANDIDATE='python3 python/msp.py'
   python3 tools/demo_compare.py --input build/curated.dat --out build/cmp-curated
   ```
5. **Interpret parity correctly.** If the change is intentional, COBOL parity
   is *expected* to break for the affected records only. Say so in the PR,
   listing which records differ and why. Unrelated records must still match.
6. **Update the rule map** row(s) and, if a COBOL construct is involved, the
   walkthrough.

## Invariants to keep

- No `float` anywhere in the payment path.
- Bytes in, ASCII out; no text-mode reading of the input.
- `Claim` and `Result` stay immutable; no state is carried between records.
- A fatal condition raises `FatalBatchError`, and totals are never written for
  a failed batch.
- Exit codes: 0 success, 2 usage or fatal.

## Keeping the COBOL around

Keep `cobol/` and the baseline evidence for as long as anyone may need to ask
"what did the old system do?". The comparison tooling (`tools/verify.py`,
`tools/demo_compare.py`) is how that question is answered with evidence
instead of memory.
