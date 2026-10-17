# 06 — Maintenance and reproducibility guide

The sample is standard-library Python plus GnuCOBOL. Run the baseline build
before checks if `build/msp-batch` is missing or stale. Do not treat a passing
synthetic comparison as an independent policy oracle.

## Run the checks

From the repository root:

```sh
# Toolchain and baseline executable
make doctor
make build

# Independent Stage 2 ledger and interface suite, first against COBOL
MSP_COMMAND='build/msp-batch' python3 -m unittest discover -s tests_policy -v

# Then run the same independent suite against the Python candidate
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v

# Focused Python function and boundary tests
python3 -m unittest discover -s tests_python -v

# Rebuild curated and seeded synthetic input, then compare the candidate
make generate
python3 tools/verify.py baseline --command 'python3 python/msp.py' \
  --report evidence/live/python-baseline-report.json
make compare CANDIDATE='python3 python/msp.py'
python3 tools/verify.py compare --candidate 'python3 python/msp.py' \
  --input build/curated.dat --report evidence/live/curated-comparison-report.json
```

The presentation comparison retains the raw inputs/outputs plus Markdown and
CSV record-level views:

```sh
python3 tools/demo_compare.py --input build/curated.dat --name curated
python3 tools/demo_compare.py --input build/synthetic.dat --name synthetic
python3 tools/demo_compare.py --edge-cases --name edge
python3 tools/demo_compare.py --fatal
```

The curated and synthetic byte comparisons can be run directly:

```sh
cmp evidence/live/comparison/curated/cobol-results.csv \
    evidence/live/comparison/curated/python-results.csv
cmp evidence/live/comparison/curated/cobol-totals.csv \
    evidence/live/comparison/curated/python-totals.csv
cmp evidence/live/comparison/synthetic/cobol-results.csv \
    evidence/live/comparison/synthetic/python-results.csv
cmp evidence/live/comparison/synthetic/cobol-totals.csv \
    evidence/live/comparison/synthetic/python-totals.csv
```

The detailed baseline, policy, unit, verification, and comparison command logs
are under `evidence/live/`. Keep each command line, its output, and final
`exit=N` together when adding a retained log. `tools/demo_compare.py` is the
presentation wrapper; `tools/verify.py` remains the strict verifier.

## Add a rule or boundary safely

1. Establish whether the proposed behavior is a CMS-derived rule or a demo
   interface assumption. Record the source and interpretation in
   `docs/rules.md`; do not use a demo reason code as a CMS policy citation.
2. Add an independently reasoned case to `tests_policy/expectations.json`,
   including its source, exact input, arithmetic/validation explanation, and
   expected status, cents, and reason. Update the serialization support only
   as needed.
3. Run the independent suite against the COBOL baseline:
   `MSP_COMMAND='build/msp-batch' python3 -m unittest discover -s tests_policy -v`.
   If COBOL disagrees with the hand-derived ledger, investigate the rule and
   expected result before changing the Python port.
4. Add focused coverage to `tests_python/` for the function-level boundary,
   then run the independent suite against Python and
   `python3 -m unittest discover -s tests_python -v`.
5. Run baseline verification, `make compare`, and curated comparison. Use
   `demo_compare.py` when per-record outputs or fatal behavior need a retained
   side-by-side view. Resolve mismatches in the implementation; do not weaken
   comparisons or edit expected output to hide a mismatch.
6. Update the rule map with real source/test/function line numbers and link the
   new evidence logs. Keep unknown timestamps or human-review measurements
   marked `UNKNOWN`.

## Protected reference artifacts

For this exercise, do not modify:

- `cobol/`
- `fixtures/`
- `tools/verify.py`
- `tools/fixtures.py`
- `tools/capture_baseline.py`
- `tests/`
- `tests_policy/` (the Stage 2 independent tests)
- `docs/evidence/`

These files provide the original executable, independent expectations, and
baseline evidence against which the migration is reviewed. A maintenance task
that truly requires changing one of these should be separately scoped and
reviewed rather than folded into a Python migration.

## What the evidence does and does not establish

- The 29-case Stage 2 ledger/interface suite passed against COBOL before Python
  was added, and the unchanged suite passed against Python afterward.
- The 14 focused Python tests exercise selected validation, payment, framing,
  limits, duplicates, formatting, and CLI boundaries.
- A zero-mismatch side-by-side result shows agreement on the records in that
  batch. The seeded synthetic batch has no independent payment oracle.
- Curated and edge batches improve coverage but remain finite. Agreement does
  not prove CMS policy completeness, production suitability, or correctness on
  untested inputs.
- The program assumes upstream eligibility, coverage, pricing, and input
  allocation decisions. It is not a complete claims processor.
- The published Example 4 inconsistency is documented and excluded as an
  authoritative fixture in `docs/rules.md`.
- No PR, reviewer time, human intervention duration, or productivity
  comparison is inferred from these test results.
