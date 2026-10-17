# Evidence index and seven-step presentation guide

Rehearsal run in Devin session
https://app.devin.ai/sessions/227ede5941704863b4c28458ebdba9ff, from starter
commit `37ceca1`, on branch `devin/1760736000-msp-python-migration`.
Toolchain: GnuCOBOL 3.1.2.0, Python 3.10.12, GCC 11.4.0, GNU Make 4.3
(`evidence/rehearsal/environment.txt`).

## Seven steps (`docs/demo-runbook.md`)

| # | Step | Show this | What it proves | Commit |
|---|---|---|---|---|
| 1 | Baseline | `evidence/rehearsal/stage1-baseline.log`, `stage1-cobol-baseline/manifest.json` | The unchanged COBOL builds and runs here. Curated: 30 records, 12 paid / 9 zero / 9 invalid, 10,000,450,202 cents. Synthetic: 1,000 records, 271 / 729 / 0, 514,352,570,951 cents. Hashes match the retained starter baseline | `28520cd` |
| 2 | Explanation | `docs/migration/01-cobol-explanation.md`, then `03-cobol-primer.md` and `04-legacy-walkthrough.md` | The legacy program is understood, including the `claim-has-contract` branch and the OTAF-vs-payment-in-full distinction | `28520cd` + docs |
| 3 | Tests before migration | `tests_policy/expectations.json`, `stage2-pre-migration-tests/cobol-run.log` | 48 hand-derived cases (with policy citations and arithmetic, none copied from COBOL output) passed against COBOL **before any Python existed** | `f49e97d` |
| 4 | Python and tests | `python/msp.py`, `tests_python/test_msp_units.py`, `stage3-python/` | The same independent tests passed against Python on the first run; 20 focused unit tests pass. One test-authoring defect was corrected (`corrections.md`) | `dd83cd0` |
| 5 | Comparison | `stage4-comparison/curated/side-by-side.md`, `synthetic/side-by-side.md`, `edge/side-by-side.md`, `fatal-parity.md`, `comparison-report.json` | Per-record MATCH on 30 + 1,000 + 24 records, byte-identical outputs and totals, identical fatal behavior. Zero mismatches, so there were none to investigate | `7b411e5` |
| 6 | CMS-EX3 | `docs/cms-example-3.md`; `curated/side-by-side.md` CMS-EX3 section; `04-legacy-walkthrough.md` "CMS-EX3 through the code" | $13,000 OTAF − $12,500 primary = **$500.00** in policy, tests, COBOL and Python. Ignoring the OTAF gives $1,500 (EX3-NO-OTAF), a $1,000 overpayment | — |
| 7 | Reviewable change | the PR, `02-rule-map.md`, `05-cobol-to-python.md`, `06-maintaining.md` | Each rule traced from policy → COBOL → test → Python → result; the PR is left unmerged for human review | PR |

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
