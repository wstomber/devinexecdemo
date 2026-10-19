# Demo readiness and ownership

Codex prepares a functioning legacy system and demo conditions. Devin performs
the modernization, derives substantive tests, produces evidence, and creates and
tests native Devin Playbooks. No Python payment replacement is in this starter.

## Starting package

| Requirement | Status / location |
| --- | --- |
| Runnable COBOL, shared copybook, record contract | Ready: cobol/ and README.md |
| Reproducible compiler/Python/test environment | Ready: Dockerfile and installation commands; Python standard library only |
| Exact compile/run commands | Ready: `make doctor build baseline generate test capture-baseline` |
| Fictional stable claims, deterministic input | Ready: 33 curated cases; seeded 1,000-record generator; synthetic CWF reference file (fixtures/cwf.json) |
| Actual retained baseline outputs and inputs | Ready after capture: docs/evidence/cobol-baseline/; new captures under build/baseline/ |
| Committed starting state | Record the preparation commit SHA before starting Devin; source hashes and the prior source commit are retained in the capture manifest |
| CMS §40.8.3 Example 3 excerpt | Ready: docs/cms-example-3.md, official link, pages, retrieval date, PDF hash |
| Module boundary | Ready: payment calculation plus three CWF pre-payment checks (entitlement, duplicate, MSP primary billed); coverage, primary/gross pricing and deductions supplied upstream |
| Existing independent expectation ledger | Ready: fixtures/expected.json; keep unchanged; observed output is not its source |
| New policy-derived tests before migration | Pending: Devin creates, runs against COBOL, and commits separately BEFORE Python |
| Python replacement and focused unit tests | Pending: Devin |
| Complete policy -> COBOL -> new tests -> Python rule map | Pending: Devin; docs/rules.md is starter background |
| Strict comparison verifier | Ready: tools/verify.py; preserve checks |
| Retained dual outputs and side-by-side presentation workflow | Pending: Devin adds new wrapper/report files and executes both batches |
| Completed rehearsal examples | Pending: actual Devin runs, PRs/branches and evidence index; no fabricated examples |
| Native Playbooks and fresh live-style executions | Pending: Devin saves and tests them in its workspace, reporting IDs/versions |
| Optional maintainability change | Specified only: docs/follow-up-exercise.md; synthetic, not implemented |
| Human intervention/review record | Empty template only: docs/templates/session-events.csv; Devin/presenter record actual time |

## Keep the three kinds of evidence distinct

A. Independent business-rule evidence: the starter ledger has hand-worked published
and synthetic expectations. Devin must derive additional expectations from public
rules before coding, retain arithmetic/source references, and run those tests
against COBOL before migrating. It must not turn observed output into an oracle.

B. Python unit evidence: Devin adds tests for individual functions, exact limits,
zero outcomes, malformed input, contractual caps, equal limits, state handling, and
one-cent precision, then reports actual execution. Starter infrastructure tests
are not a replacement for this work.

C. Executable comparison evidence: Devin runs identical curated and synthetic
records through both executables, preserves raw outputs, runs strict checks, and
adds the visible per-claim table. It investigates every discrepancy and retains
reproducible inputs. Agreement establishes consistency on tested inputs, not
complete system or Medicare-policy equivalence.

## Reusable Playbook acceptance criteria (Devin-owned)

Create two native Playbooks: **MSP COBOL to Python with evidence** and **MSP synthetic
maintainability change**. Each needs a saved ID/link/version, parameters, prerequisites,
ordered steps, commands, expected artifacts, failure/review conditions, and a fresh
run demonstrating it works. Parameterize repository, pinned starter ref, new branch,
candidate command, seed, and evidence directory. A repository Markdown file is a
portable specification, not proof of native Playbook creation.

For each completed example, Devin must index the seven-step click path and retain:
its session ID, starter/result SHAs, pre-migration test commit, actual commands,
results and raw outputs, rule map, all mismatch resolutions, Playbook identity,
PR or branch with description, and human review/intervention records. Mark each
field COMPLETE, NOT_RUN, NOT_CREATED, UNKNOWN, or BLOCKED as appropriate. Never
replace unknown timing with zero or present planned activity as executed evidence.

Rehearse first. Later, launch the same Playbook live from the pinned COBOL-only
starter in a fresh branch/worktree. Saved rehearsal evidence remains useful even
if a live run is still in progress, provided the presenter labels it accurately.

## Environment and retained evidence

The base system has already passed Linux and Docker CI:
[main baseline verification](https://github.com/wstomber/devinexecdemo/actions/runs/39062912317).
The preparation change also runs `make doctor capture-baseline` in CI and uploads
fresh baseline files as artifacts. Check that change's CI before beginning Devin.

`make capture-baseline` records actual commands/exit codes, compiler/Python versions,
input/output hashes, source hashes, counts and totals, and UTC capture time. It
checks the retained curated output against independent expectations and structurally
reconciles the synthetic output. The manifest explicitly says migration comparison
NOT_RUN. In an image/source export without Git metadata, source_commit is null and
hashes remain available; pin the originating checkout commit separately.

The checked-in capture was made before its evidence commit, so source_commit names
the preceding committed COBOL source state; actual source hashes identify the code
used. Later captures legitimately have different timestamps, runtime metadata, and
command paths. Input/output hashes must match for the same baseline source and seed.
Do not overwrite the committed capture to hide a behavior difference.
