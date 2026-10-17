# Evidence index — MSP COBOL to Python with evidence

This index follows the seven presentation steps in
[`demo-runbook.md`](demo-runbook.md#click-path-and-evidence). Links point to
retained evidence and the corresponding local stage commits. The repository is
a synthetic educational example, not CMS production code.

## Seven-step presentation path

| Step | What to show | Evidence and links | Stage commit |
| --- | --- | --- | --- |
| 1. Baseline | Execute the original COBOL program and inspect its capture | [`stage1-baseline.log`](../evidence/live/stage1-baseline.log); [captured COBOL results and manifest](../evidence/live/cobol-baseline/); [hash check](../evidence/live/stage1-hash-check.txt) | Stage 1 `b1d2a1c` |
| 2. Explanation | Explain the COBOL payment basis and upstream assumptions | [COBOL explanation](migration/01-cobol-explanation.md); [`batch.cob`](../cobol/batch.cob); [`validate.cob`](../cobol/validate.cob); [`payment.cob`](../cobol/payment.cob); [rules and source review](rules.md) | Stage 1 `b1d2a1c` |
| 3. Pre-migration tests | Show independent ledger/interface tests passing against COBOL before Python | [`stage2-policy-tests-cobol.log`](../evidence/live/stage2-policy-tests-cobol.log); [ledger](../tests_policy/expectations.json); [interface tests](../tests_policy/test_batch_interface.py) | Stage 2 `08f0398` |
| 4. Python and test execution | Review the Python implementation and its tests | [`python/msp.py`](../python/msp.py); [focused unit tests](../tests_python/test_msp.py); [`stage3-policy-tests-python.log`](../evidence/live/stage3-policy-tests-python.log); [`stage3-unit-tests-python.log`](../evidence/live/stage3-unit-tests-python.log); [corrections record](../evidence/live/corrections.md) | Stage 3 `3f048a3` |
| 5. Comparison | Open the strict verification and per-record tables | [`stage4-python-baseline.log`](../evidence/live/stage4-python-baseline.log); [`stage4-make-compare.log`](../evidence/live/stage4-make-compare.log); [`stage4-curated-verification.log`](../evidence/live/stage4-curated-verification.log); [curated table](../evidence/live/comparison/curated/side-by-side.md); [synthetic table](../evidence/live/comparison/synthetic/side-by-side.md); [edge table](../evidence/live/comparison/edge/side-by-side.md); [fatal matrix](../evidence/live/comparison/fatal/fatal-paths.md) | Stage 4 `31cfe4ac0488a2755aab782aaf76d803cfb5442a` (amended) |
| 6. $500 case | Trace the contractual cap and the 50,000-cent result | [CMS-EX3 explanation](migration/01-cobol-explanation.md); [walkthrough](migration/04-legacy-walkthrough.md#cms-ex3-traced-through-the-payment-statements); ledger case `CMS-EX3`; matching row in the [curated table](../evidence/live/comparison/curated/side-by-side.md) | Stage 2 `08f0398`, Stage 3 `3f048a3`, amended Stage 4 `31cfe4a` |
| 7. Reviewable change | Review the implementation, tests, mapping, and limitations | [rule map](migration/02-rule-map.md); [COBOL primer](migration/03-cobol-primer.md); [walkthrough](migration/04-legacy-walkthrough.md); [translation guide](migration/05-cobol-to-python-guide.md); [maintenance guide](migration/06-maintenance-guide.md); [Stage 5 policy test](../evidence/live/stage5-policy-tests-python.log); [Stage 5 Python unit test](../evidence/live/stage5-unit-tests-python.log); [protected-path checks](../evidence/live/stage5-protected-diff-check.log); this index | Stage 5: this commit / PR head |

Stage SHAs are local repository history references: Stage 1
`b1d2a1cba66bb0644118efec2a2881f2db7bcd36`; Stage 2
`08f03984a055c9a16a871a062407c8ddb1592ef7`; Stage 3
`3f048a353389e6736eb00b82f868d90204003d2b`; amended Stage 4
`31cfe4ac0488a2755aab782aaf76d803cfb5442a`. Stage 5 is this documentation
commit (or the PR head once one exists).

## Recorded outcomes

- Stage 2 independent policy/interface tests: **29/29 PASS against COBOL**.
- The unchanged 29-test suite: **29/29 PASS against Python**.
- Focused Python unit tests: **14/14 PASS**.
- Stage 5 rerun: policy suite **29/29 PASS**, Python suite **14/14 PASS**;
  both protected-path diff checks were empty and passed.
- Python baseline verification: **PASS**.
- `make compare`: **PASS** on the 1,000-record seeded synthetic batch.
- Curated verification: **PASS**.
- Side-by-side results: **0 mismatches** for curated (30 records), synthetic
  (1,000), and edge (42).
- Fatal comparison: **9/9 MATCH**.
- CMS-EX3: **50,000 cents** in the independent ledger, COBOL result, and Python
  result; the curated per-record table shows the two outputs.

Evidence links: [COBOL policy run](../evidence/live/stage2-policy-tests-cobol.log),
[Python policy run](../evidence/live/stage3-policy-tests-python.log),
[Python unit run](../evidence/live/stage3-unit-tests-python.log),
[baseline verification](../evidence/live/stage4-python-baseline.log),
[synthetic comparison](../evidence/live/stage4-make-compare.log),
[curated verification](../evidence/live/stage4-curated-verification.log),
[curated side-by-side](../evidence/live/comparison/curated/side-by-side.md),
[synthetic side-by-side](../evidence/live/comparison/synthetic/side-by-side.md),
[edge side-by-side](../evidence/live/comparison/edge/side-by-side.md), and
[fatal matrix](../evidence/live/comparison/fatal/fatal-paths.md).
Stage 5 refresh: [policy tests](../evidence/live/stage5-policy-tests-python.log),
[Python unit tests](../evidence/live/stage5-unit-tests-python.log),
[protected-path diff check](../evidence/live/stage5-protected-diff-check.log), and
[unchanged policy-test diff check](../evidence/live/stage5-policy-diff-check.log).

## Session and reporting status

- Session: [https://app.devin.ai/sessions/237943a1ebdc487a92de2320fc5d281f](https://app.devin.ai/sessions/237943a1ebdc487a92de2320fc5d281f)
- Playbook identity used: **COMPLETE** — “MSP COBOL to Python with evidence”.
- Playbook ID: **UNKNOWN** — not recorded here.
- PR: **NOT_RUN** — to be added.
- Human review time: **UNKNOWN**.
- Human intervention time: **UNKNOWN**.

The session-event rows are appended to
[`templates/session-events.csv`](templates/session-events.csv). Stage command
timestamps use the corresponding commit timestamps; elapsed time and human
time remain blank or `UNKNOWN` because no measurements were recorded.

## Limits

These results establish agreement only for the recorded tests and batches. The
synthetic batch has no independent payment oracle; finite curated, edge, and
fatal suites are not proof of complete Medicare correctness. The application
implements a selected prospective-payment subset and assumes upstream
eligibility, coverage, pricing, and allocation. It is not CMS production code.
See [`rules.md`](rules.md) for source scope and the excluded Example 4
inconsistency.
