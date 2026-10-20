# Presenter guide: Migration Evidence app

Written for a non-technical presenter. You click; the app shows real evidence.

## Before you start (5 minutes before)

1. Open the app (see "Starting the app" below). The first screen is "The problem".
2. Optional: press **▶ Start Devin live** (on "The problem" screen, or screen 6) so Devin is already working when you show it. Then press **Open Devin's session ↗** to show it working.
   Show its pull request when it finishes, but **don't merge it**: it targets the COBOL-only starter branch, and merging it there means the next live run starts from finished code. If one is merged by mistake, reset `demo/starter-be0b00e` to `be0b00e`.
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
| 0–2 | The problem | Point at the 4 steps. | Old COBOL that few engineers still read; a wrong rule pays real money. Each claim is priced first, then CWF approves or rejects it, and only approved claims are paid. Devin explained it, tested it, migrated it, and proved it. |
| 2–4 | 1 · COBOL baseline | Press **▶ Run COBOL vs Python now** (top right, ~7 s). When it finishes the app jumps to 5 · Old vs new showing the fresh LIVE results. | Devin first ran the original as the yardstick. |
| 4–6 | 2 · Devin explains COBOL | Point at the highlighted lines, then scroll to the CWF check; mention DeepWiki. | Devin found the exact line that applies the provider's contract, and explained the three CWF checks that decide whether it gets paid. |
| 6–9 | 3 · Tests came first | Point at "Tests came first: VERIFIED FROM GIT"; click any row to see its hand-worked answer. | The right answers were worked out from the CMS manual and checked against COBOL before any Python existed. |
| 9–12 | 4 · Python + unit tests | Read the 10 step rows top to bottom (1–6 payment, 7–10 CWF); point at the CMS-EX3 column ending at $500 released. | Same rules in readable Python, exact cents, held to the same tests. |
| 12–14 | 5 · Old vs new | Choose "LIVE · synthetic (1000)"; click **Mismatches only** (empty); click **Rejected by CWF**; type a claim ID such as CMS-EX3 into the search box if asked about a specific claim. | Every claim matches on the payment, the CWF decision and the amount released, and a separate strict checker confirms it. |
| 16–18 | 6 · Review & repeat | Open PR #2 and PR #5; show the Playbook card. | Everything is reviewable, and a separate Devin session repeated the whole migration from scratch (PR #5). |
| +2 (optional) | 6 · Review & repeat | Open PR #4. | Devin also maintained it afterwards: a new feature, tests first, outputs unchanged. |
| 18–20 | 7 · Security FAQ | Scroll to the section the question belongs to (compliance, architecture, data, network, identity, audit) and answer from it; each answer links its Cognition source. | No real data was used; every answer is from Cognition's published docs (ZDR with the model labs, Outposts, Devin Connect), and anything unpublished says "Confirm with Cognition". |
| +2 (if asked about next steps) | 8 · Pilot plan | Say: "Same steps, on one real CWF MSP claim path: the payment calculation and the CWF edits." Walk the four weeks; point at the "Platform owner's role" column and the in-scope table. | The pilot is one named CWF claim path, not a platform rewrite; security sets the rules in week 1 and tries to break them in week 3; nothing touches real data. |

## 15-minute route

The problem (1 min) → 1 · Baseline, press Run COBOL vs Python now (2) → 3 · Tests came first (2) → 5 · Old vs new (3) → 6 · Review & repeat (2) → 7 · Security FAQ (2).

## Try to break it (screen 5)

Invite the interviewer to pick one of the four mistakes ("Pay a claim CWF rejected" shows the CWF step being checked too). About 7 seconds later the red box shows what caught it. Press **Undo** to go back to green. Line: "Pick any mistake a rewrite could make; watch the checks catch it."

## Ask the DeepWiki live (screen 2)

Let the interviewer type their own question at https://app.devin.ai/wiki/wstomber/devinexecdemo. These were tested on 2026-10-18 and answered correctly, with file references (the links show the saved answers):

1. "What is a COBOL copybook, and how is claim.cpy used in this repo?" ([answer](https://app.devin.ai/search/api_c270c01b-544f-431d-adf1-e6c96510b032))
2. "How do the COBOL and Python keep exact cents? What does PIC 9(10) mean?" ([answer](https://app.devin.ai/search/api_2fc755dc-93c6-446a-92e4-0f355fc4eaa4))
3. "Walk me through how claim CMS-EX3 gets paid $500, in the COBOL and in the Python." ([answer](https://app.devin.ai/search/api_f6d0ca42-1e3e-4e8e-a749-24a3f8214996))
4. "What happens if a claim has no contract amount, or the contract field has a typo in it?" ([answer](https://app.devin.ai/search/api_cae40504-95ac-4c82-b16e-fca9aebacc74))
5. "What does GOBACK do in COBOL and what is the Python equivalent here?" ([answer](https://app.devin.ai/search/api_06b5dd04-7c68-4a06-8cc9-16579819f6bc))
6. "If CMS changed the MSP payment rule, which files would an engineer change and which tests would catch a mistake?" ([answer](https://app.devin.ai/search/api_7c069a5e-2230-4c06-a9c5-0f2b9b59952e))
7. "Why were the tests written from the CMS manual before the Python was written, and where is that visible in the git history?" ([answer](https://app.devin.ai/search/api_c6d0d02f-b9bd-404f-a967-479838c36e46))

Avoid: "What happens if the contract field is all dashes or has bad characters?" Its first sentence wrongly lumped all-dashes in with errors; all-dashes means "no contract". The answer takes about 15 seconds; fill the pause by saying "this is the wiki Devin generated from the code".

## If something goes wrong

- **A security question you can't answer:** say "I'll confirm that with Cognition". Rows marked "Confirm with Cognition" on screen 7 are exactly those.
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
- The CWF step is three illustrative checks on synthetic data, not all of CWF; the reject codes are this demo's own (only "accepted as is", 01, is a CWF code).
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

**Start Devin live** (optional): set `DEVIN_API_KEY` to a Devin service-user key (role with `UseDevinSessions`), then run `make demo-live`. It refuses to start without the key, so the button can't quietly fall back to manual steps. The startup line `Start Devin live: ready` confirms it.
The server calls the Devin API v3 to create a session with the Playbook `playbook-f242f29f76f8440ea96928dfeec1d441`, starting from
`demo/starter-be0b00e`; the key never leaves the server. The latest launched session is kept in `build/devin-runs/latest.json`
(delete it to reset the card). Without the key the card shows the manual steps instead. Org can be overridden with `DEVIN_ORG_ID`.
