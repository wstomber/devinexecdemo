# Evidence index: live Playbook run (MSP COBOL → Python with evidence)

Label: **CURRENT LIVE EXECUTION**. This is not the saved rehearsal. It is a
synthetic educational example that makes no CMS production claims.

| Field | Value | Status |
| --- | --- | --- |
| Devin session | https://app.devin.ai/sessions/90a0699b3e534e32ac9203f6d33b4084 | COMPLETE |
| Playbook | "MSP COBOL to Python with evidence" (native Playbook, launched by the requester). This session did not read its ID or version | UNKNOWN |
| Starter commit | `be0b00ec5a2369d50a34d351694b187ae2300fe4` (`demo/starter-be0b00e`) | COMPLETE |
| Branch | `devin/1792509400-msp-python-migration-live` | COMPLETE |
| Stage 1 commit | `78f377e` baseline + explanation | COMPLETE |
| **Pre-migration test commit** | `dbff9d7`. Precedes the first commit containing `python/` (`04e532c`) | COMPLETE |
| Stage 3 commit | `04e532c` Python + unit tests | COMPLETE |
| Stage 4 commit | `a09ba2d` comparisons | COMPLETE |
| Result commit / PR | The head of the branch above, and the PR into `demo/starter-be0b00e` | COMPLETE |
| Starter files unchanged | `git diff --stat be0b00e..HEAD -- cobol fixtures tools/verify.py tools/fixtures.py tools/capture_baseline.py tests docs/evidence` is empty | COMPLETE |
| Mismatch resolutions | `evidence/live/compare/README.md`, `evidence/live/corrections.md` | COMPLETE |
| Human intervention / review time | Not observed by this session | UNKNOWN |

## Seven-step click path (docs/demo-runbook.md)

| Step | Open | What it shows |
| --- | --- | --- |
| 1. Baseline | `evidence/live/stage1-baseline.log`, `evidence/live/baseline/curated-results.csv`, `evidence/live/baseline/manifest.json`, `evidence/live/baseline-hash-check.txt` | Real COBOL run on this VM. 33 curated records: 15 PAID / 9 ZERO / 9 INVALID, 10,001,694,602 cents calculated, 21 accepted / 3 rejected, 10,000,450,202 released. Every source and output hash equals the committed capture |
| 2. Explanation | `docs/migration/01-cobol-explanation.md`, then `cobol/payment.cob` l.20–24 and `cobol/cwf.cob` | The contract replaces the charge basis before `min(gross, basis)`. CWF then checks entitlement, duplicate and MSP primary billing |
| 3. Existing tests | commit `dbff9d7`, `tests_policy/expectations.json`, `evidence/live/stage2-tests-vs-cobol.log` | 107 hand-derived cases (policy vs interface, with sources and arithmetic) and 18 batch tests, passing against COBOL **before** Python existed |
| 4. Python and tests | `python/msp.py`, `tests_python/test_msp.py`, `evidence/live/stage3-python-tests.log`, `evidence/live/corrections.md` | Stage 2 tests run unchanged with `MSP_COMMAND='python3 python/msp.py'`: 23/23 OK. Unit tests: 29/29 OK. Every correction and its cause is logged |
| 5. Comparison | `evidence/live/stage4-comparison.log`, `evidence/live/compare/README.md`, `*-side-by-side.md`, raw `*-cobol-*.csv` / `*-python-*.csv`, `fatal-paths.md` | Strict verifier PASS on curated, synthetic 1,000 and edge 3,029. Side-by-side shows 0 mismatches on all four batches, and the files are byte-identical. 18 fatal paths MATCH |
| 6. $500 case | ledger `CMS-EX3` / `EX3-NO-OTAF`; `04-legacy-walkthrough.md`; `02-rule-map.md`; `curated-side-by-side.md` row 2 | $13,000 OTAF − $12,500 primary = $500 (50,000 cents). CWF accepts it and 50,000 is released. Without the OTAF the payment would be $1,500. The $1,556 deductible is a historical example input |
| 7. Reviewable change | the PR, this index, `02-rule-map.md` | Python, tests, rule map, comparison tooling (`tools/side_by_side.py`, `tools/edge_batch.py`, `tools/compare_fatal.py`), reproducible inputs, limitations |

## Maintainer documentation

`03-cobol-primer.md` (COBOL for non-COBOL engineers), `04-legacy-walkthrough.md`,
`05-cobol-to-python-guide.md`, `06-maintenance-guide.md`.

## Limits

Parity shows equivalence to this COBOL on the tested batches only. It is not proof
of Medicare correctness. Both programs could share a policy error. The policy
anchor is the Stage 2 ledger, and only for the cases it lists. Open review items
are `DATE-NO-CAL` (2025-02-30 accepted), the scope of the demo CWF rules, and
path aliasing. No efficiency or timing claims are made.
