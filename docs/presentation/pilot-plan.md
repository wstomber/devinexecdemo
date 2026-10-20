## The idea

Run exactly what you just saw on the real thing: **one Medicare Secondary Payer (MSP) claim path through Common Working File (CWF) processing** — the MSP payment calculation and the CWF pre-payment edits that approve or reject the claim before payment is released. One slice, four weeks, on synthetic or de-identified claims. Security sets the rules in week 1 and tries to break them in week 3. CMS names the exact modules and repositories; nothing outside them is touched.

## In scope, and not

| In scope | Not in this pilot |
|---|---|
| The MSP secondary-payment COBOL module and the CWF pre-payment edits CMS names for MSP claims (entitlement, duplicate, MSP file), their copybooks, and the batch jobs (JCL) that run them | Other CWF edits (benefit-days and utilization, other payer rules, trailers) |
| A test region or copy that can run them on test claims and test CWF reference data | Production systems, production deployment, real beneficiary data |
| CMS Pub. 100-05, Ch. 5 MSP payment rules and Pub. 100-04, Ch. 27 CWF edit rules as the answer key | Rewriting the surrounding CWF platform or its host files |
| 3–5 real MSP change requests from the backlog | Contract or staffing changes for the current integrator |

## Four weeks

| Week | What Devin does on the CWF MSP slice | Platform owner's role | Done when |
|---|---|---|---|
| 1 · Guardrails, then understand it | Gets access to the named repositories only, in the deployment security chooses (Desktop / CLI, or Outposts so the code stays on CMS machines). Builds a DeepWiki of the slice: copybooks, record layouts, the payment rule, and the CWF edits that approve or reject the claim. Extracts every business rule into one rule map, each rule linked to the COBOL lines and the CMS manual section it comes from. Runs it in the test region and records today's results — payment, CWF decision and amount released — on a fixed set of test claims. | Names the repositories and test region in scope and grants access; agrees the network allowlist and security profile with the security team before Devin sees code. | Security sign-off; a CMS engineer confirms the DeepWiki and the rule map explain the slice correctly; baseline results saved. |
| 2 · Answer key, then one migrated slice | Writes test claims from the CMS manuals, with the expected payment, CWF decision and released amount worked out by hand, and checks the current COBOL against them first. Then migrates the payment calculation and the CWF edits to Python and compares old and new on every test claim. | Confirms the answer key reflects how the slice should behave; reviews every pull request alongside the integrator's engineers. | Current COBOL passes the answer key; old and new match on 100% of test claims; PR approved by a human. |
| 3 · Real changes, and try to break it | Takes 3–5 real MSP or CWF-edit change requests from the backlog, in the existing COBOL, each as a pull request with tests and an updated DeepWiki. | Picks the 3–5 change requests and sets the review bar; works with security as they red-team it (misleading instructions in files, audit-log checks, nothing leaves the allowlist). | Change requests reviewed by the integrator's engineers; red-team report written. |
| 4 · Measure and decide | Produces the results pack: the numbers below, every PR, the DeepWiki, the test evidence. | Owns the go / no-go, with the security findings and what a wider rollout would need. | Go / no-go on the next CWF edits. |

## What we measure

- **Time per change request:** ticket opened to change approved, compared with the same kind of MSP change in CMS's own ticket history. Taken from ticket and git timestamps, not estimated.
- **Correctness:** share of test claims where old and new agree exactly on the payment, the CWF decision and the amount released; answer-key tests passed.
- **Quality:** share of Devin's pull requests accepted, review rounds, and defects found after approval.
- **Knowledge:** whether an engineer new to the code can explain the payment rule and the CWF edits using only the DeepWiki.
- **Security:** red-team findings, and any blocked or unexpected network attempts in the logs.

## What CMS provides

- **An owner** for the MSP claim path, and read access to the MSP payment and CWF edit repositories: COBOL, copybooks, JCL.
- **A test region** (or a copy) that can run them with test CWF reference data, and a set of synthetic or de-identified test claims.
- **Two or three reviewers** from the team that maintains it today, including the integrator's engineers.
- **A security engineer** for weeks 1 and 3.
- **Decisions before week 1:** deployment model, data handling, and contract terms (including any BAA).
