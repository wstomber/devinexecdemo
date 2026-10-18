# Presentation readiness checklist

Recorded 2026-10-17 by Devin. Re-check anything marked PENDING on the day.

## Passed (verified, with evidence)

| Check | How it was verified | Result |
|---|---|---|
| Install from a clean clone | Fresh `git clone` (no `build/`), then `make demo-refresh` | PASSED: all 11 live steps exit 0 |
| Launch from a clean clone | `make demo` / `python3 demo/server.py` in the clean clone; `/api/evidence` served | PASSED |
| Live refresh writes a new folder | Each run creates `build/demo-runs/<UTC>/`; `evidence/rehearsal/` unchanged (`git status` clean) | PASSED |
| Live run duration | `make demo-refresh`, measured | about 5 seconds on the Devin VM |
| Starter tests `tests/` | `make test` | PASSED, 17 tests |
| Independent tests vs COBOL | `python3 -m unittest discover -s tests_policy -v` | PASSED, 16 tests |
| Independent tests vs Python | `MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v` | PASSED, 16 tests |
| Python unit tests (incl. 8 new app-evidence tests) | `python3 -m unittest discover -s tests_python -v` | PASSED |
| Strict comparison | `make compare CANDIDATE='python3 python/msp.py'`; `tools/verify.py compare` on curated | PASSED |
| Side-by-side | `tools/demo_compare.py` curated (30) and synthetic (1,000) | 0 mismatches, byte-identical |
| All 8 screens render, no errors | Browser check of every screen | PASSED |
| Search, filters, claim details, CMS-EX3 links, Run COBOL vs Python now and Reset buttons | Browser check | PASSED |
| A wrong result is shown as wrong | Planted a 1-cent change in a copy of a live run: app showed OVERALL FAILED, the row as MISMATCH, CMS-EX3 as $500.00 / $500.01 | PASSED (copy deleted afterwards) |
| Missing / malformed evidence never shows as a pass | `tests_python/test_demo_evidence.py` | PASSED |
| Maintainability Playbook fresh run | Child session, PR #4 | PASSED, PR #4 open |
| Migration Playbook fresh run from the COBOL-only starter | Separate child session, PR #5 | PASSED: 30 / 1,000 / 42 edge records, 0 mismatches, CMS-EX3 $500 |
| Security screen facts | Each row links to the published Cognition / AWS / FedRAMP source, checked 17 Oct 2026 | Unanswered items marked "Confirm with Cognition" |

## Pending / blocked

| Item | Status | What it means for the demo |
|---|---|---|
| PR #3 (review fixes), PR #4 (`--summary-json`), PR #5 (fresh rehearsal) | OPEN, not merged | Fine to show as open. PR #5 is never merged. |
| Security questions not covered by public docs: HIPAA BAA, FedRAMP timeline for Devin Cloud | Confirm with Cognition | Ask your Cognition contact before the interview. |
| Hosted preview link | Only works while the Devin session is awake | See "On presentation day". |
| Human review / intervention time | UNKNOWN | Not measured, so no time-saved claim. |
| Full 18-minute spoken rehearsal by the presenter | NOT_RUN | Timings in the guide are estimates, not measured. |

## On presentation day (what you do)

1. **30 minutes before:** in this Devin session, send: "Start the demo app". Devin starts it with `make demo-live`, checks that "▶ Start Devin live" shows as a button, and gives you the preview button. (Or, on a machine with GnuCOBOL: `make demo`, then open http://localhost:8765.)
2. Click through once. Press **▶ Run COBOL vs Python now** once to warm up; it should say PASSED and jump to 5 · Old vs new. Then press **Reset** so the audience starts blank.
3. **5 minutes before:** press **▶ Start Devin live** (first screen or screen 7). The card then shows the session status and an **Open Devin's session ↗** button; its pull request link appears when Devin opens one. If the card shows manual steps instead, follow them (app.devin.ai → new session → Playbook "MSP COBOL to Python with evidence" → paste the one-line prompt).
4. During the demo follow `docs/presentation/presenter-guide.md` (20-minute route, or the 15-minute route).
5. If anything fails, say so and use the purple SAVED REHEARSAL evidence or the GitHub fallback links in the guide.
