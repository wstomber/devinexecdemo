# Evidence index and seven-step presentation guide

Saved rehearsal: a fresh Devin session running the native Playbook from starter
`demo/starter-be0b00e` (commit `be0b00e`):
https://app.devin.ai/sessions/a3533bd2e40d4c81a8a9df1e852c235e, pull request
https://github.com/wstomber/devinexecdemo/pull/23. Stage commits: Stage 1 `85238e3`,
Stage 2 `7e33cf0`, Stage 3 `68cd058`, Stage 4 `3ec97cc`, docs `18e3c1b`
(`evidence/rehearsal/PROVENANCE.md`). Toolchain in `evidence/rehearsal/environment.txt`.

Each claim is processed in CMS's documented order: the MSP payment is calculated,
then the synthetic CWF pre-payment check accepts or rejects it, and only an accepted
claim releases its payment.

## Seven steps (`docs/demo-runbook.md`)

| # | Step | Show this | What it proves | Commit |
|---|---|---|---|---|
| 1 | Baseline | `evidence/rehearsal/stage1-baseline.log`, `stage1-cobol-baseline/manifest.json` | The unchanged COBOL builds and runs. Curated: 33 records, 15 paid / 9 zero / 9 invalid, 10,001,694,602 cents calculated; CWF 21 accepted / 3 rejected; 10,000,450,202 cents released. Synthetic: 1,000 records, 271 paid / 729 zero; CWF 736 accepted / 264 rejected | `85238e3` |
| 2 | Explanation | `docs/migration/01-cobol-explanation.md`, then `03-cobol-primer.md` and `04-legacy-walkthrough.md` | The legacy program is understood: the `claim-has-contract` branch, the OTAF-vs-payment distinction, and the CWF check order in `cobol/cwf.cob` | `85238e3` |
| 3 | Tests before migration | `tests_policy/expectations.json`, `stage2-pre-migration-tests/cobol-run.log` | Hand-derived payment and CWF cases (policy citations and arithmetic, none copied from COBOL output) passed against COBOL before any Python existed | `7e33cf0` |
| 4 | Python and tests | `python/msp.py`, `tests_python/`, `stage3-python/` | The same independent tests pass against Python; focused unit tests cover the payment and `cwf_check`; corrections are logged | `68cd058` |
| 5 | Comparison | `stage4-comparison/curated/side-by-side.md`, `synthetic/side-by-side.md`, `edge/side-by-side.md`, `fatal-parity.md`, `comparison-report.json` | Per-record MATCH on calculated payment, CWF decision and released amount: 33 + 1,000 + 2,099 records, byte-identical outputs; 22 fatal paths match | `3ec97cc` |
| 6 | CMS-EX3 | `docs/cms-example-3.md`; `curated/side-by-side.md`; `04-legacy-walkthrough.md` "CMS-EX3 through the code" | $13,000 OTAF − $12,500 primary = **$500.00**, CWF accepts it, $500 released, in policy, tests, COBOL and Python; the look-alikes EX3-NOT-ENT, EX3-DUP and EX3-MSP-NOBL release $0 | `3ec97cc` |
| 7 | Reviewable change | the PR, `02-rule-map.md`, `05-cobol-to-python.md`, `06-maintaining.md` | Each rule traced from policy → COBOL → test → Python → result; the PR is left unmerged for human review | PR #23 |

## What the evidence does and does not show

- Layers A + B show the Python implements the documented policy formula and
  interface on the tested cases.
- Layer C shows the Python is a drop-in replacement for this COBOL on the
  tested batches.
- None of it shows complete Medicare MSP correctness. The scope is the
  synthetic formula in `docs/rules.md`. This is not CMS production code, and
  no CMS system, staffing, or performance facts are claimed.

## Reproduce

```sh
make doctor && make build baseline generate test capture-baseline
python3 -m unittest discover -s tests_policy -v                     # vs COBOL
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
python3 -m unittest discover -s tests_python -v
make compare CANDIDATE='python3 python/msp.py'
python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/curated.dat --report build/curated-comparison-report.json
python3 tools/demo_compare.py --input build/curated.dat --out build/cmp/curated
python3 tools/demo_compare.py --edge-cases --out build/cmp/edge
```

Timing and human involvement: `docs/templates/session-events.csv`. Human
review time is recorded as UNKNOWN unless the reviewer reports it.

The Python-only `--summary-json` maintainability exercise and its baseline,
acceptance-test, parity, and invocation evidence are in
`evidence/maintainability-summary-json/`.
