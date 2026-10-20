# Evidence index — live run

Live Devin run of the "MSP COBOL to Python with evidence" playbook.
Session: https://app.devin.ai/sessions/13ea9ad019f14a98a95daac201b6db47.
Starter: `be0b00ec5a2369d50a34d351694b187ae2300fe4` (`demo/starter-be0b00e`).
Branch: `devin/1792527310-msp-python-migration-live`. Synthetic educational
example; not CMS production code. Parity is shown only for the tested batches.

| Step ([runbook](../demo-runbook.md)) | Open | Shows |
|---|---|---|
| 1. Baseline | [`stage1-baseline.log`](../../evidence/live/stage1-baseline.log), [`cobol-baseline/curated-results.csv`](../../evidence/live/cobol-baseline/curated-results.csv), [`manifest.json`](../../evidence/live/cobol-baseline/manifest.json), [`stage1-hash-check.txt`](../../evidence/live/stage1-hash-check.txt), [`environment.txt`](../../evidence/live/environment.txt) | Real COBOL run, 33 curated records (15 PAID / 9 ZERO / 9 INVALID; 21 ACCEPTED / 3 REJECTED), hashes equal to `docs/evidence/cobol-baseline/manifest.json` |
| 2. Explanation | [`01-cobol-explanation.md`](01-cobol-explanation.md), [`03-cobol-primer.md`](03-cobol-primer.md), [`04-legacy-walkthrough.md`](04-legacy-walkthrough.md); `cobol/payment.cob` `calculate-prospective-payment`, `cobol/cwf.cob` `check-claim` | Contract branch replaces the charge basis before `min(gross, basis)`; CWF checks entitlement, duplicate, MSP billing; only valid claims are sent |
| 3. Existing tests | Stage 2 commit `Stage 2: independent policy ledger and batch tests (pass against COBOL)`; [`tests_policy/`](../../tests_policy/README.md); [`stage2-cobol-tests.log`](../../evidence/live/stage2-cobol-tests.log) | 119 hand-derived cases (48 policy, 71 interface) + batch tests, all passing on COBOL before any `python/` file existed |
| 4. Python and tests | Stage 3 commit; [`python/msp.py`](../../python/msp.py); [`tests_python/`](../../tests_python/test_msp_units.py); [`stage3-python-tests.log`](../../evidence/live/stage3-python-tests.log); [`corrections.md`](../../evidence/live/corrections.md) | Stdlib, integer cents; unchanged Stage 2 tests pass; every correction and its cause |
| 5. Comparison | [`stage4-verify.log`](../../evidence/live/stage4-verify.log); [`comparison/README.md`](../../evidence/live/comparison/README.md); `curated/`, `synthetic/`, `edge/` `side-by-side.md`; [`fatal/fatal-paths.md`](../../evidence/live/comparison/fatal/fatal-paths.md) | `tools/verify.py` PASS ×3; 33/33, 1,000/1,000, 3,000/3,000 MATCH, byte-identical outputs; 21/21 fatal paths MATCH |
| 6. $500 case | `CMS-EX3`: [`01-cobol-explanation.md` §7.2](01-cobol-explanation.md), ledger case `CMS-EX3` and `EX3-NO-OTAF`, [rule map row 3](02-rule-map.md), [walkthrough](04-legacy-walkthrough.md#cms-ex3-traced), `comparison/curated/side-by-side.md` record 2 | $13,000 OTAF − $12,500 primary = $500; CWF ACCEPTED, $500 released; without OTAF $1,500; $1,556 deductible is input |
| 7. Reviewable change | The PR into `demo/starter-be0b00e`; this index; [`02-rule-map.md`](02-rule-map.md); [`05-cobol-to-python-guide.md`](05-cobol-to-python-guide.md); [`06-maintenance-guide.md`](06-maintenance-guide.md); [`session-events.csv`](../templates/session-events.csv) | Python, tests, mapping, comparison tooling (`tools/side_by_side.py`), retained inputs/outputs, actual timestamps, limits |

## Reproduce

```sh
make doctor build baseline generate test
python3 -m unittest discover -s tests_policy -v                                   # COBOL
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
python3 -m unittest discover -s tests_python -v
python3 tools/verify.py baseline --command 'python3 python/msp.py'
make compare CANDIDATE='python3 python/msp.py'
python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/curated.dat
python3 tools/side_by_side.py --out build/side-by-side      # fresh copy; committed copy is evidence/live/comparison
```

## Limits

- Parity is equivalence to this COBOL on the tested batches, not proof of
  Medicare correctness. The COBOL baseline is observed behavior, not a policy oracle.
- The policy ledger covers the cited published examples and boundaries; interface
  cases encode the README demo contract. CWF codes are demo-defined.
- The synthetic and edge batches have no independent payment oracle.
- Human review/intervention time: UNKNOWN. No efficiency or speed-up is claimed.
