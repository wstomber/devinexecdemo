# Evidence index — live run (MSP COBOL → Python)

**Label: CURRENT LIVE EXECUTION** of the Playbook "MSP COBOL to Python with evidence".
Session: https://app.devin.ai/sessions/7a07c2b03acb4b889bbf84b73d0bcbf9 (`devin-7a07c2b03acb4b889bbf84b73d0bcbf9`).
Start (UTC): 2026-10-19T20:09:11Z. Starter: `be0b00ec5a2369d50a34d351694b187ae2300fe4` (`demo/starter-be0b00e`).
Branch: `devin/1792440476-msp-python-migration-live`. Human intervention/review time: **UNKNOWN** (not measured by Devin).

| Field | Status | Where |
| --- | --- | --- |
| Stage 1 commit (baseline + explanation) | COMPLETE | `47cd2def8c6f19a6f52b212c0ef0a005a94563f7` |
| Pre-migration test commit (Stage 2, before any `python/`) | COMPLETE | `88f9ff1f31b8c3436689c8441357ce8e85dcfcc5` |
| Python + unit tests (Stage 3) | COMPLETE | `844197d367810a53f3d6090752d94696f0700eba` |
| Comparison (Stage 4) | COMPLETE | `df4c3ab0b73258a7b7ddc762ae19c0f5095c577b` |
| Result SHA / PR | COMPLETE | head of this branch; PR into `demo/starter-be0b00e` |
| Mismatch resolutions | COMPLETE: 0 mismatches; verifier ASCII limit explained | `evidence/live/corrections.md` |
| Human review / intervention time | UNKNOWN | `docs/templates/session-events.csv` |

## Seven-step click path (docs/demo-runbook.md)

| Step | Open | What it shows |
| --- | --- | --- |
| 1. Baseline | `evidence/live/stage1-baseline.log`, `evidence/live/baseline/curated-results.csv`, `evidence/live/baseline/manifest.json`, `evidence/live/baseline-hash-check.txt` | Real COBOL run: 33 curated records (15 PAID, 9 ZERO, 9 INVALID; CWF 21 accepted, 3 rejected; 10,001,694,602 cents calculated, 10,000,450,202 released). Every hash matches `docs/evidence/cobol-baseline/` |
| 2. Explanation | `docs/migration/01-cobol-explanation.md`, `cobol/payment.cob` lines 12-38, `cobol/cwf.cob` lines 17-52; primer `03-cobol-primer.md`; walkthrough `04-legacy-walkthrough.md` | The contract branch replaces the charge basis before the min cap; then entitlement → duplicate → MSP billed |
| 3. Pre-migration tests | commit `88f9ff1`, `tests_policy/expectations.json` (92 cases: 34 policy, 58 interface), `tests_policy/cwf_reference.json`, `evidence/live/stage2-tests-cobol.log` | 23 tests (92 ledger records) passed against COBOL; `python/` did not exist yet |
| 4. Python and tests | `python/msp.py`, `tests_python/test_msp_units.py`, `evidence/live/stage3-tests-python.log`, `evidence/live/stage3-unit-tests.log`, `evidence/live/corrections.md`, `05-cobol-to-python-guide.md` | Stage 2 tests unchanged: 23/23 pass on Python; 29 unit tests pass; 35 runtime probes identical; no Python logic correction was needed |
| 5. Comparison | `evidence/live/stage4-comparison.log`, `evidence/live/comparison/{curated,synthetic,edge,edge-ascii}/side-by-side.md` (+ `.csv`, both raw outputs), `evidence/live/comparison/fatal-paths.md`, `evidence/live/verifier-reports/` | `verify.py baseline` PASS; `make compare` (1,000 synthetic) PASS; curated compare PASS; edge-ascii compare PASS; side-by-side: curated 33, synthetic 1,000, edge 120 records, all with 0 mismatches and byte-identical CSVs; 17/17 fatal paths identical |
| 6. $500 case | ledger `CMS-EX3`/`EX3-NO-OTAF`; `01-cobol-explanation.md` §OTAF; `04-legacy-walkthrough.md` trace; `02-rule-map.md` row 2; `comparison/curated/side-by-side.md` row 2 | $13,000 OTAF − $12,500 primary = $500 calculated, CWF ACCEPTED, $500 released (COBOL = Python = ledger). Ignoring the OTAF gives $1,500. $1,556 is historical input |
| 7. Reviewable change | the PR, `02-rule-map.md`, this index, `06-maintenance-guide.md`, `docs/templates/session-events.csv` | Python, tests, rule map, comparison tooling (`tools/compare_report.py`), reproducible inputs, limitations |

## Limits of this evidence
* Parity establishes equivalence to the COBOL on the tested batches (curated, seeded synthetic, adversarial edge, and the fatal paths). It is **not** proof of Medicare correctness, and both programs could share a policy error.
* The ledger checks the scoped rules as this repository interprets them. Reason codes, layouts and limits are demo-defined.
* `tools/verify.py` cannot read non-ASCII input, so the full edge batch was compared only by `tools/compare_report.py`.
* Only GnuCOBOL 3.1.2 on Ubuntu 22.04 was exercised. The Docker/CI paths were not run in this session.
* No timing or efficiency claim is made.
