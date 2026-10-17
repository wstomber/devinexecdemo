# Evidence index — live run

| Item | Value |
|---|---|
| Devin session | https://app.devin.ai/sessions/7909f87127ea43d3af55ee357ca75c3c (ID `7909f87127ea43d3af55ee357ca75c3c`) |
| Mode | **Current live execution** (fresh branch from the pinned starter; no rehearsal files reused) |
| Native Playbook run | "MSP COBOL to Python with evidence" (supplied by the session prompt) |
| Second Playbook ("MSP synthetic maintainability change") | NOT_CREATED in this session (out of this run's scope) |
| Starter | `demo/starter-37ceca1` = `37ceca17f110536d55261d5d19aa187781dd8851` |
| Branch | `devin/1792278045-msp-python-migration-live` |
| PR | into `demo/starter-37ceca1` (not `main`); not merged |
| Environment | [evidence/live/environment.txt](../../evidence/live/environment.txt) |
| Human intervention / review time | UNKNOWN |

## Commits (each stage separately reviewable)

| Stage | Commit | Content |
|---|---|---|
| 1 | `a81c994` | COBOL baseline run, retained outputs, hash check, explanation |
| 2 | `d085746` | Independent ledger + batch tests, run against COBOL — **before any Python file** |
| 3 | `57aafd3` | `python/msp.py`, unit tests, Stage 2 tests re-run unchanged |
| 4 | `5bf829f` | Comparisons and side-by-side reports |
| 5 | (this commit) | Rule map, primer, walkthrough, guides, this index, session events |

## Seven presentation steps (docs/demo-runbook.md)

| Step | Open | What it shows |
|---|---|---|
| 1. Baseline | [stage1-baseline.log](../../evidence/live/stage1-baseline.log), [baseline/curated-results.csv](../../evidence/live/baseline/curated-results.csv), [baseline/manifest.json](../../evidence/live/baseline/manifest.json), [stage1-hash-check.txt](../../evidence/live/stage1-hash-check.txt) | Real COBOL run: curated 30 records, 12 PAID / 9 ZERO / 9 INVALID, 10,000,450,202 cents; synthetic 1,000; all hashes match the checked-in manifest |
| 2. Explanation | [01-cobol-explanation.md](01-cobol-explanation.md), [04-legacy-walkthrough.md](04-legacy-walkthrough.md), [03-cobol-primer.md](03-cobol-primer.md); `cobol/payment.cob` 20–24 | Contract branch replaces the charge basis before `min(claim-gross, charge-basis)` |
| 3. Existing tests | Commit `d085746`; [tests_policy/](../../tests_policy/); [stage2-tests-vs-cobol.log](../../evidence/live/stage2-tests-vs-cobol.log) | 31 policy + 34 interface ledger cases with citations and arithmetic, plus batch tests: 25 tests OK against COBOL before Python existed |
| 4. Python and tests | [python/msp.py](../../python/msp.py), [tests_python/test_msp.py](../../tests_python/test_msp.py), [stage3-tests-policy-vs-python.log](../../evidence/live/stage3-tests-policy-vs-python.log), [stage3-tests-python.log](../../evidence/live/stage3-tests-python.log), [corrections.md](../../evidence/live/corrections.md) | Same 25 tests OK unchanged; 23 unit tests OK; no Python corrections were needed |
| 5. Comparison | [stage4-verify-commands.log](../../evidence/live/stage4-verify-commands.log); side-by-side [curated](../../evidence/live/compare/curated/side-by-side.md), [synthetic](../../evidence/live/compare/synthetic/side-by-side.md), [edge](../../evidence/live/compare/edge/side-by-side.md), [fatal](../../evidence/live/compare/fatal/fatal-paths.md); raw `cobol-*.csv` / `python-*.csv` in each directory | Starter verifier PASS ×3; 0 mismatches on 30 + 1,000 + 3,075 records, outputs byte-identical; 14 fatal/usage cases MATCH |
| 6. $500 case | Ledger `CMS-EX3` / `EX3-NO-OTAF`; [04 walkthrough](04-legacy-walkthrough.md#paymentcob--calculate-prospective-payment-cms-ex3-line-by-line); [rule map P5](02-rule-map.md); curated side-by-side record 2 | $13,000 OTAF − $12,500 primary = $500 (50,000 cents) in ledger, COBOL and Python; ignoring OTAF gives $1,500; $1,556 is a historical input |
| 7. Reviewable change | This PR; [02-rule-map.md](02-rule-map.md); [05-cobol-to-python.md](05-cobol-to-python.md); [06-maintenance-guide.md](06-maintenance-guide.md); [session-events.csv](../templates/session-events.csv) | Python, tests, rule map, comparison tooling (`tools/side_by_side.py`), reports, reproducible inputs, timings, limitations |

## Reproduce

```sh
git checkout devin/1792278045-msp-python-migration-live
make doctor build baseline generate test
python3 -m unittest discover -s tests_policy -v
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
python3 -m unittest discover -s tests_python -v
make compare CANDIDATE='python3 python/msp.py'
python3 tools/side_by_side.py --make-edge build/edge.dat   # seed 20261018, deterministic
for b in curated synthetic edge; do python3 tools/side_by_side.py --input build/$b.dat --name $b; done
python3 tools/side_by_side.py --fatal
```

## Limits

- Parity = equivalence to this COBOL on the tested batches, not proof of Medicare correctness.
- Synthetic educational module; no CMS production code, architecture, or staffing facts.
- The synthetic and edge batches have no independent payment oracle (COBOL is the oracle there);
  only the ledger is independently derived.
- Untested differences (path-string edge cases, partial output contents on fatal errors) are
  listed in [05-cobol-to-python.md](05-cobol-to-python.md#known-untested-differences).
- No timing or productivity comparison with manual work is claimed; human time is UNKNOWN.
