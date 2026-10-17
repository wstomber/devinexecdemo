# Read first: the business problem and demonstration idea

## Background and purpose

The presenter is preparing a **customer-facing Devin presentation for a Cognition
interview**. The assignment is to choose a customer and demonstrate one of three
themes: COBOL/legacy modernization, combining two ERP systems, or improving test
coverage. The selected customer scenario is **the Centers for Medicare & Medicaid
Services (CMS)**, and the selected theme is **COBOL modernization**, using testing
and exact output comparison as the evidence that the migration worked.

This repository is the working starting environment for that presentation. It is
not a discovered CMS codebase or evidence of CMS's actual internal architecture.
No CMS project approval or production source has been supplied. Codex built the small synthetic COBOL system from public
payment rules. Devin is supposed to perform the substantive modernization and
produce the reviewable evidence. Keep those authorship boundaries visible.

## The customer problem we are illustrating

The scenario is a team responsible for a long-lived payment application. A change
to its implementation can alter money owed even if the replacement appears to
work on ordinary claims. Business rules, contractual exceptions, input validation,
and batch handling all need to survive the change. Reviewers need an understandable
connection from public policy to source code, tests, and observed results.

The business question is: **Can Devin understand an unfamiliar legacy program,
make its behavior and assumptions reviewable, establish independent tests, migrate
it, and provide enough evidence for a human to evaluate the result?**

The proposed customer value is more understandable rules, safer changes, repeatable
verification, and a clearer review process. These are demonstration hypotheses,
not verified claims about CMS's current problems or measured Devin productivity.
Do not invent CMS project history, staffing constraints, costs, modernization
plans, procurement interest, or performance improvements.

## Why this application and this example

The application calculates a small scoped Medicare Secondary Payer (MSP) payment
after another insurer has paid. It accepts covered charges, gross Medicare payable,
primary payment for covered services, applicable deductible/coinsurance, an optional
lower obligatory acceptance amount, and a full-payment indicator.

Eligibility, coverage determination, primary and Medicare pricing, and applicable
deductions have already been established upstream. We are demonstrating one
payment module, with fictional claims and stable IDs, rather than rebuilding a
claims system. The public source is CMS Pub. 100-05, Chapter 5, §§40.8–40.8.3;
see rules.md and the included cms-example-3.md excerpt for provenance and limits.

The memorable case is **CMS-EX3**. Charges are $15,000, gross Medicare payable
$14,000, primary payment $12,500, and the provider's obligatory total acceptance
amount $13,000. The remaining deductible is $1,556, a **historical example input**,
and coinsurance is $0. The scoped payment is **$500**. Ignoring the acceptance
limit would yield **$1,500**, a $1,000 overstatement in this example.

That difference makes understanding the rule visible to a business audience. It
also gives a technical reviewer a specific paragraph, independent calculation,
test, and comparison row to inspect. The primary payment itself was not accepted
as full payment: the $13,000 amount is the contractual total, and `full=N`.
Do not introduce a bug to stage this contrast; the existing COBOL handles it.

## What the audience should learn from Devin's work

The audience includes the Cognition interview evaluators, with CMS as the selected
customer scenario. Explain financial consequences in plain language, while keeping
source, tests, and reports available for technical review. Do not assume that an
actual CMS stakeholder has endorsed this scenario or these assumptions.

Show three different kinds of evidence and say what each establishes:

1. Independent expectations derived from published rules anchor business behavior.
2. Python function and boundary tests exercise the replacement's implementation.
3. Identical-batch comparisons establish agreement between executables on tested
   claims, including exact cents, statuses/reasons, record counts, and totals.

Agreement alone cannot prove that both implementations interpreted policy correctly.
The 30 curated cases and deterministic 1,000-record batch cover a defined scope;
they do not establish complete Medicare correctness or complete system equivalence.
Keep ambiguous rules and code/policy conflicts visible for human review.

## The presentation and reusable-workflow idea

First have Devin actually complete a rehearsal: explanation, new tests before
implementation, Python migration, comparisons, and a reviewable code change.
Retain real session links, commands, outputs, commits, and reports. These become
the prebuilt examples that can be opened reliably during the presentation.

Then have Devin save and test native Playbooks so the workflow can be launched
again from a clean, pinned starter commit. The seven-step click path is:
**baseline -> explanation -> pre-migration tests -> Python and test execution ->
comparison -> $500 case -> reviewable change**. See demo-runbook.md for the screens
and commands. Clearly label saved rehearsal evidence and the current live run.

One Playbook covers migration with evidence. The optional second demonstrates
maintainability through a synthetic request for a JSON summary alongside unchanged
CSV behavior; see follow-up-exercise.md. That request is not a new CMS policy.
Devin owns creating and executing the Playbooks; repository instructions are not
proof that native Playbooks or completed examples already exist.

The presenter should be able to show what Devin did, what a human reviewed or
corrected, and how to repeat the work. Record real intervention and review time,
but do not claim efficiency gains without a comparable measured manual baseline.
There is no promised live completion time or invented benchmark.

## Definition of a useful result

A useful result is a working Python replacement with independently derived tests
established before migration, focused unit tests, an auditable rule map, retained
side-by-side outputs, investigated differences, a reviewable PR/branch, and actual
saved/tested Playbook identities. It also includes a concise evidence index that
lets the presenter follow the click path without searching through a long session.

Read DEVIN_TASK.md for execution requirements and demo-readiness.md for ownership
and readiness gates. Preserve the starter's independent expectations and verifier.
Make the financial reasoning and review evidence understandable, not merely the
fact that code was translated from one language to another.
