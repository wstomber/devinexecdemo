# Presenter guide: Migration Evidence app

Written for a non-technical presenter. You click; the app shows real evidence.

## Before you start (5 minutes before)

1. Open the app (see "Starting the app" below). The first screen is "The problem".
2. Optional: press **▶ Start Devin live** (on "The problem" screen, or screen 7) so Devin is already working when you show it. Then press **Open Devin's session ↗** to show it working.
3. Keep this guide on a second screen or printed. The app itself shows nothing presenter-only, so everything on screen is fine for the audience to see.

## Colours and labels

| Label | Means |
|---|---|
| **SAVED REHEARSAL** (purple) | Evidence Devin produced earlier and saved in the repo. |
| **CURRENT LIVE EXECUTION** (blue) | Produced by pressing "Run COBOL vs Python now" today. |
| PASSED / MATCH (green) | Checked and correct. |
| FAILED / MISMATCH (red) | Something went wrong. Say so; do not hide it. |
| RUNNING (blue) | Still in progress. |
| NOT_RUN / UNKNOWN (grey) | Not run yet, or the evidence is missing. Never a pass. |

## 20-minute route

| Time | Screen | Do | Say (one line) |
|---|---|---|---|
| 0–2 | The problem | Point at the 4 steps. | Old COBOL nobody can read; a wrong rule pays real money. Devin explained it, tested it, migrated it, and proved it. |
| 2–4 | 1 · COBOL baseline | Press **▶ Run COBOL vs Python now** (top right, ~7 s). When it finishes the app jumps to 5 · Old vs new showing the fresh LIVE results. | Devin first ran the original as the yardstick. |
| 4–6 | 2 · Devin explains COBOL | Point at the highlighted lines; mention DeepWiki. | Devin found the exact line that applies the provider's contract. |
| 6–9 | 3 · Tests came first | Point at "Tests came first: VERIFIED FROM GIT"; click the CMS-EX3 row. | The right answers were worked out from the CMS manual and checked against COBOL before any Python existed. |
| 9–12 | 4 · Python + unit tests | Compare the two code boxes; open "Corrections". | Same rule in readable Python, exact cents, passed the same tests first time. |
| 12–14 | 5 · Old vs new | Choose "LIVE · synthetic (1000)"; click **Mismatches only** (empty); click **Find CMS-EX3**. | Every claim matches, and a separate strict checker confirms it. |
| 14–16 | ★ CMS-EX3 $500 | Walk the four limits top to bottom. | $13,000 − $12,500 = $500. Missing the contract rule would pay $1,000 too much. |
| 16–18 | 6 · Security & data | Scroll to "Questions we expect"; answer from the table. | No real data was used; here is what Cognition publishes (ZDR with the model labs, Outposts), and what we will confirm with Cognition. |
| 18–20 | 7 · Review & repeat | Open PR #2 and PR #5; show the Playbook card. | Everything is reviewable, and a separate Devin session repeated the whole migration from scratch (PR #5). |
| +2 (optional) | 7 · Review & repeat | Open PR #4. | Devin also maintained it afterwards: a new feature, tests first, outputs unchanged. |
| +2 (if asked about next steps) | 8 · Pilot plan | Walk the four weeks; point at the "Security's role" column. | Security sets the rules in week 1 and tries to break them in week 3; nothing touches real data. |

## 15-minute route

The problem (1 min) → 1 · Baseline, press Run COBOL vs Python now (2) → 3 · Tests came first (2) → 5 · Old vs new (3) → ★ CMS-EX3 (3) → 6 · Security & data (2) → 7 · Review & repeat (2).

## If something goes wrong

- **A security question you can't answer:** say "I'll confirm that with Cognition". Rows marked "Confirm with Cognition" on screen 6 are exactly those.
- **Start blank:** press **Reset** (top right, next to the run button) to clear live results; the saved rehearsal evidence is untouched.
- **"Run COBOL vs Python now" shows FAILED:** say "the live run failed; here is the saved rehearsal". Every screen still shows the purple SAVED REHEARSAL evidence. Click "steps" (top right) to show which step failed.
- **The app will not open:** use the GitHub fallback links:
  - Order of the work: https://github.com/wstomber/devinexecdemo/pull/2/commits
  - Claim-by-claim table: https://github.com/wstomber/devinexecdemo/blob/main/evidence/rehearsal/stage4-comparison/curated/side-by-side.md
  - DeepWiki: https://app.devin.ai/wiki/wstomber/devinexecdemo
- **The live Devin session is still running at the end:** that's expected. A full migration takes longer than the demo; show how far it got.
- **"Start Devin live" shows a red error, or only manual steps:** the app has no working Devin API key. Use the manual steps shown in the same card (app.devin.ai → new session → Playbook → paste the prompt).

## What not to claim

- Not CMS production code; a synthetic, educational example based on public CMS rules.
- "Match" means identical on the tested batches, not complete Medicare correctness.
- No speed, cost, or time-saved claims (human review time was not measured).

## Starting the app (technical, for whoever sets it up)

Requirements: Linux or macOS with `python3` (3.10+), `make`, `git`, and GnuCOBOL (`cobc`, 3.x). On Ubuntu:
`sudo apt-get install -y gnucobol gcc make python3`. No Python packages, npm, or database are needed.

```sh
git clone https://github.com/wstomber/devinexecdemo && cd devinexecdemo
make demo            # compiles COBOL, generates batches, serves http://localhost:8765
make demo-refresh    # optional: run every live check once from the terminal, no browser
```

Each live run (button or `make demo-refresh`) writes a new folder under `build/demo-runs/<UTC time>/`
with every command, exit code and full output. Saved rehearsal evidence under `evidence/rehearsal/` is never modified.
PR and Playbook status shown on screen comes from `demo/status.json` and is labelled with the time it was recorded.

**Start Devin live** (optional): set `DEVIN_API_KEY` to a Devin service-user key (role with `UseDevinSessions`) before `make demo`.
The server calls the Devin API v3 to create a session with the Playbook `playbook-f242f29f76f8440ea96928dfeec1d441`, starting from
`demo/starter-37ceca1`; the key never leaves the server. The latest launched session is kept in `build/devin-runs/latest.json`
(delete it to reset the card). Without the key the card shows the manual steps instead. Org can be overridden with `DEVIN_ORG_ID`.
