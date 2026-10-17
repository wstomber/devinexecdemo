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
   python3 -m unittest tests_python.test_summary_json -v
   python3 -m unittest discover -s tests_python -v
   make compare CANDIDATE='python3 python/msp.py'
   python3 tools/demo_compare.py --input build/curated.dat --out build/cmp-curated
   ```
5. **Interpret parity correctly.** If the change is intentional, COBOL parity
   is *expected* to break for the affected records only. Say so in the PR,
   listing which records differ and why. Unrelated records must still match.
6. **Update the rule map** row(s) and, if a COBOL construct is involved, the
   walkthrough.

## Worked example: `--summary-json`

This is an **interface change**, not a CMS policy change: the Python CLI adds
an optional JSON summary while keeping the three positional paths and CSV
format unchanged. It is Python-only; COBOL has no equivalent output, so parity
is checked on the result and totals CSVs. The acceptance tests are added and
run before the implementation:

```sh
make build generate
make test
python3 -m unittest discover -s tests_policy -v
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
python3 -m unittest tests_python.test_summary_json -v
python3 -m unittest discover -s tests_python -v
make compare CANDIDATE='python3 python/msp.py'
make compare CANDIDATE='python3 python/msp.py --summary-json build/compare-s.json'
python3 tools/demo_compare.py --input build/curated.dat --out evidence/maintainability-summary-json/curated
python3 tools/demo_compare.py --input build/curated.dat --python 'python3 python/msp.py --summary-json build/s-curated.json' --out evidence/maintainability-summary-json/curated-with-flag
python3 tools/demo_compare.py --input build/synthetic.dat --python 'python3 python/msp.py --summary-json build/s.json' --out evidence/maintainability-summary-json/synthetic-with-flag
python3 tools/demo_compare.py --input build/synthetic.dat --out evidence/maintainability-summary-json/synthetic
python3 tools/demo_compare.py --edge-cases --out evidence/maintainability-summary-json/edge
```

The run logs, before/after CSVs, JSON summaries, invocation examples, and
curated, synthetic, and edge-case comparisons are retained in
`evidence/maintainability-summary-json/`. The four demo comparisons report
zero record mismatches and byte-identical CSV outputs; the CMS-EX3 result
remains `0000050000` cents.

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
