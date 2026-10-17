# 06 — Maintenance guide for `python/msp.py`

## Run it

```sh
python3 python/msp.py INPUT.dat RESULTS.csv TOTALS.csv     # exit 0 ok, 2 fatal (discard outputs)
```

Python ≥ 3.8, standard library only (tested with 3.10.12). Input format: README.md.

## Test it (all three layers)

```sh
python3 -m unittest discover -s tests_python -v                                   # unit tests
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v # independent ledger + batch tests
make build generate                                                                 # COBOL oracle + batches
make compare CANDIDATE='python3 python/msp.py'                                      # starter verifier
python3 tools/side_by_side.py --make-edge build/edge.dat
for b in curated synthetic edge; do python3 tools/side_by_side.py --input build/$b.dat --name $b; done
python3 tools/side_by_side.py --fatal
```

`tests_policy/` with no `MSP_COMMAND` runs against `build/msp-batch` (needs `cobc`).
`side_by_side.py` writes to `evidence/live/compare/`; commit regenerated reports only when
they are the evidence for a reviewed change.

## Where a change goes

| Change | Edit | Must also update |
|---|---|---|
| Payment formula / zero reason | `calculate_payment` | ledger case with citation + arithmetic **first**, then rule map |
| New validation rule | `validate_record` (keep precedence order explicit) | ledger interface case, `ValidationPrecedence`, README |
| Record layout | slice constants, `RECORD_LENGTH` | README, `tools/fixtures.py` users, ledger `build_record` |
| Output columns | `format_result` / headers | `tools/verify.py` schema (starter file — coordinate), docs |
| Limits | `MAX_LINE_BYTES`, `MAX_RECORDS` | batch tests at limit and limit+1 |

Workflow for any behaviour change: write/adjust the hand-derived expectation and test first,
see it fail, change the code, then re-run all three layers. Once behaviour intentionally
diverges from COBOL, the COBOL comparison stops being an oracle for that rule — record the
divergence in the rule map and in `05-cobol-to-python.md`.

## Invariants not to break

- Money is `int` cents; no `float`, no `Decimal` rounding modes, no division.
- Raw fields are validated with `is_numeric` before `int()`.
- Input is bytes; split only on LF; strip one CR.
- Validation order LENGTH → ID → AMOUNT → CONTRACT → FLAG; zero order FULL → PRIMARY → DEDUCTIONS.
- Every identifiable ID is checked for duplicates, valid or not.
- Exit 2 on any fatal condition; nothing on stdout.

## Limits of what the evidence shows

Parity shows the Python is equivalent to this COBOL on the tested batches (curated 30,
synthetic 1,000, adversarial edge 3,075 records, 14 fatal/usage cases) plus the independent
ledger. It is **not** proof of Medicare correctness: eligibility, MSP type, pricing and OTAF
determination are upstream and out of scope, and this is a synthetic educational module, not
CMS production code.
