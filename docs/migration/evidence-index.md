# Evidence index (live run) — the seven presentation steps of `docs/demo-runbook.md`

| Step | Open | Shows |
| --- | --- | --- |
| 1. Baseline | `evidence/live/stage1-baseline.log`, `evidence/live/baseline/curated-results.csv`, `evidence/live/stage1-hash-check.txt`, `evidence/live/environment.txt` | real COBOL run, 33 records with payment, CWF decision and released amount; hashes match the committed manifest |
| 2. Explanation | `docs/migration/01-cobol-explanation.md`, `03-cobol-primer.md`, `04-legacy-walkthrough.md` | contract branch before the min cap; CWF entitlement → duplicate → MSP; COBOL taught to new engineers |
| 3. Existing tests | Stage 2 commit, `tests_policy/expectations.json`, `evidence/live/stage2-tests-cobol.log`, `evidence/live/stage2-notes.md` | 99 hand-derived cases + batch tests passed against COBOL before any Python existed |
| 4. Python and tests | Stage 3 commit, `python/msp.py`, `tests_python/`, `evidence/live/stage3-*.log`, `evidence/live/corrections.md` | integer cents, byte validation, unchanged Stage 2 tests passing; every correction with cause |
| 5. Comparison | `evidence/live/stage4/README.md`, `stage4/{curated,synthetic,edge}/side-by-side.{md,csv}` + raw `cobol/` and `python/` outputs, `stage4/fatal/fatal-parity.md`, verifier logs | 0 mismatches on 33 + 1,000 + 2,099 records; 22/22 fatal paths; byte-identical CSVs |
| 6. $500 case | `CMS-EX3` in `01-cobol-explanation.md`, ledger, `02-rule-map.md` row 2, `04-legacy-walkthrough.md`, `stage4/curated/side-by-side.md` record 2 | $13,000 − $12,500 = $500, accepted, $500 released; $1,500 without the OTAF |
| 7. Reviewable change | the PR, this index, `02-rule-map.md`, `05-cobol-to-python-guide.md`, `06-maintenance-guide.md`, `docs/templates/session-events.csv` | Python, tests, mapping, tooling, reproducible inputs, timings, limits |

Limits: synthetic educational module; parity ≠ Medicare correctness; human review time UNKNOWN.
