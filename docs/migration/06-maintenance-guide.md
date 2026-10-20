# 06 — Maintenance guide

## Layout

| Path | Purpose |
|---|---|
| `python/msp.py` | Production translation (stdlib only) |
| `tests_policy/` | Independent ledger + batch tests; run against any implementation via `MSP_COMMAND` |
| `tests_python/` | Unit tests of `python/msp.py` functions |
| `tools/side_by_side.py` | COBOL vs Python per-record comparison and fatal paths |
| `cobol/`, `fixtures/`, `tools/verify.py`, `tools/fixtures.py`, `tests/`, `docs/evidence/` | Starter reference; do not edit |
| `evidence/live/` | Retained evidence of this run |

## Everyday commands

```sh
python3 -m unittest discover -s tests_python -v
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
make build generate && python3 tools/side_by_side.py --out build/side-by-side   # needs cobc
```

## Changing a rule

1. Write down the source (policy section or interface decision) and add or
   change cases in `tests_policy/expectations.json` with `kind`, `source` and
   `arithmetic`. Derive expected values by hand, never from program output.
2. Change `python/msp.py` (the matching function is listed in
   [02-rule-map.md](02-rule-map.md)).
3. Add a focused unit test in `tests_python/`.
4. Update the rule map row.
5. If COBOL is still the reference, an intentional behavior change will make
   the COBOL fail the new ledger case and the side-by-side report MISMATCH;
   record that as an intended divergence rather than editing evidence.

## Where things live in `msp.py`

- Record layout offsets: `validate` (0–12 ID, 12–62 amounts, 62–72 contract,
  72 flag, 73–84 MBI, 84–92 DOS).
- Payment: `calculate_payment`. CWF decision: `cwf_check`.
- CWF file format: `cwf_records`, `load_cwf`. Input framing: `read_lines`.
- Limits: module constants `MAX_LINE`, `MAX_RECORDS`, `MAX_REFERENCE_RECORDS`.
- Output format: `format_result` and the totals write in `run_batch`.

## Rules of thumb

- Keep amounts as `int`; widen output formats only with the interface contract.
- Keep the validation order; set the reason before each check.
- Any new character class: explicit sets, not `isdigit`/`isalpha`/range compares.
- Fatal errors: raise `Fatal`, never write CSV to stdout.
- Performance: one pass, O(1) duplicate and history lookups. One observed run of
  10,000 valid records on the session VM took 0.12 s (Python) and 1.26 s (COBOL)
  wall clock, including process start. A single observation, not a benchmark.

## Not covered / open

- Real CMS pricing and CWF edits are out of scope; CWF codes are demo-defined.
- Pub. 100-05 Example 4 is excluded (see `docs/rules.md`).
- Partial outputs after a fatal error are not cleaned up (same as COBOL); the
  caller must discard them on exit 2.
