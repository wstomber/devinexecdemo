## The idea

Run exactly what you just saw on the real thing: the **Medicare Secondary Payer (MSP) payment logic used in Common Working File (CWF) claims processing**. One module, four weeks, on synthetic or de-identified claims. Security sets the rules in week 1 and tries to break them in week 3. CMS names the exact module and repository; nothing outside it is touched.

## In scope, and not

| In scope | Not in this pilot |
|---|---|
| The MSP secondary-payment COBOL module CMS names, its copybooks, and the batch job (JCL) that runs it | Other CWF edits (eligibility, utilization, other payer rules) |
| A test region or copy that can run the module on test claims | Production systems, production deployment, real beneficiary data |
| CMS Pub. 100-05, Ch. 5 MSP payment rules as the answer key | Rewriting the surrounding CWF platform |
| 3–5 real MSP change requests from the backlog | Contract or staffing changes for the current integrator |

## Four weeks

| Week | What Devin does on the CWF MSP module | Security's role | Done when |
|---|---|---|---|
| 1 · Guardrails, then understand it | Gets access to the one MSP repository only, in the deployment security chooses (Desktop / CLI, or Outposts so the code stays on CMS machines). Builds a DeepWiki of the module: copybooks, record layouts, the payment rule, how CWF calls it. Runs the module in the test region and records today's results on a fixed set of test claims. | Writes the network allowlist and security profile; signs off before Devin sees code. | Security sign-off; a CMS engineer confirms the DeepWiki explains the module correctly; baseline results saved. |
| 2 · Answer key, then one migrated slice | Writes test claims from the CMS manual, with the expected payment worked out by hand, and checks the current COBOL against them first. Then migrates the payment calculation to Python and compares old and new on every test claim. | Reviews every pull request alongside the integrator's engineers. | Current COBOL passes the answer key; old and new match on 100% of test claims; PR approved by a human. |
| 3 · Real changes, and try to break it | Takes 3–5 real MSP change requests from the backlog, in the existing COBOL, each as a pull request with tests and an updated DeepWiki. | Red-teams it: plants misleading instructions in files, checks the audit logs, confirms nothing leaves the allowlist. | Change requests reviewed by the integrator's engineers; red-team report written. |
| 4 · Measure and decide | Produces the results pack: the numbers below, every PR, the DeepWiki, the test evidence. | Presents the security findings and what a wider rollout would need. | Go / no-go on the next CWF module. |

## What we measure

- **Time per change request:** ticket opened to change approved, compared with the same kind of MSP change in CMS's own ticket history. Taken from ticket and git timestamps, not estimated.
- **Correctness:** share of test claims where old and new pay exactly the same; answer-key tests passed.
- **Quality:** share of Devin's pull requests accepted, review rounds, and defects found after approval.
- **Knowledge:** whether an engineer new to the module can explain the payment rule using only the DeepWiki.
- **Security:** red-team findings, and any blocked or unexpected network attempts in the logs.

## What CMS provides

- **An owner** for the MSP module, and read access to its repository: COBOL, copybooks, JCL.
- **A test region** (or a copy) that can run the module, and a set of synthetic or de-identified test claims.
- **Two or three reviewers** from the team that maintains it today, including the integrator's engineers.
- **A security engineer** for weeks 1 and 3.
- **Decisions before week 1:** deployment model, data handling, and contract terms (including any BAA).
