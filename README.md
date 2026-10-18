# Medicare Secondary Payer COBOL modernization starter

A small, runnable batch application for a Cognition interview demonstration to CMS:
establish a verified COBOL baseline, ask Devin to migrate it to Python, and review
tests and exact output comparisons. **The Python payment implementation is
intentionally absent.** Python here only serializes fixtures and verifies outputs.

Read the [business and presentation brief](docs/demo-brief.md) first for the
interview background, customer problem being illustrated, reason for choosing this
example, intended audience, and the rehearsal-to-live Playbook idea.

This is a **synthetic educational application derived from public rules**. It is
not CMS production source code, a complete claims processor, or a replica of CWF,
FISS, or MSPPAY. Reason codes and file formats are demo-defined, not CMS codes.
No patient data is used.

## Scope

Implements a representative subset of the prospective-payment formula in the
[CMS MSP Manual, Pub. 100-05, Chapter 5, §§40.8–40.8.3](https://www.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Downloads/msp105c05.pdf).
Upstream processing has established Medicare eligibility and secondary-payer
responsibility, identified covered services, and supplied gross Medicare payment,
applicable deductible, and coinsurance. A proper primary claim has been filed.

The application chooses covered charges or a supplied lower contractual acceptance
amount as its charge basis, applies the gross-payment and charge limits, honors
payment in full, and floors payment at zero. See [rules and source review](docs/rules.md).
The historical $1,556 deductible in the two published examples is fixture data,
not a current rate lookup or an application default.

Excluded: eligibility, diagnosis coding, DRG pricing, annual rates, beneficiary
liability, recovery, sequestration, utilization accounting, and other adjustments.
Percentage-of-charge and PIP methods are outside the selected scope.

## Run locally

Requires GnuCOBOL 3.1+ with a working C compiler, Make, and Python 3.9+.

```sh
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y gnucobol gcc make python3
# macOS alternative: install Apple's command line tools, then
brew install gnucobol python make

make build
make baseline
make generate
make test
make doctor
make capture-baseline
```

`make baseline` checks the executable against 30 independently specified records
in `fixtures/expected.json`. It reports migration comparison as `NOT_RUN`.
`make generate` serializes the curated inputs and creates 1,000 seeded valid
synthetic records plus readable JSON in `build/`. The synthetic batch expands
input coverage; it does not independently establish policy correctness.

`make doctor` checks the compiler and Python. No pip packages are required.
`make capture-baseline` retains actual input, per-claim CSV, totals, commands,
runtime metadata, source/input/output hashes, and a verification manifest in
`build/baseline/`. The committed starting capture is in
`docs/evidence/cobol-baseline/`. It is observed COBOL behavior, not a new policy
oracle. CI captures fresh baseline artifacts and also tests the Docker image.

```sh
# Before Devin supplies a candidate: explicitly NOT_RUN, nonzero exit
make compare
# After migration (example path to be created by Devin)
python3 tools/verify.py baseline --command 'python3 python/msp.py' \
  --report build/python-baseline-report.json
make compare CANDIDATE='python3 python/msp.py'
# Also compare malformed curated input, not just valid synthetic input
python3 tools/verify.py compare --candidate 'python3 python/msp.py' \
  --input build/curated.dat --report build/curated-comparison-report.json
make clean
```

Commands are tokenized with `shlex.split`, executed without a shell, and receive
three appended paths. Quote paths containing spaces within the command string.
`PYTHON`, `COBC`, `COBFLAGS`, and `BASELINE` are Make overrides. Harness timeout
defaults to 10 seconds and can be changed with `--timeout`.

## Run with Docker

```sh
docker build -t msp-starter .
docker run --rm -v "$PWD:/app" msp-starter make build baseline generate test capture-baseline
# Once Devin adds the candidate:
docker run --rm -v "$PWD:/app" msp-starter \
  make compare CANDIDATE='python3 python/msp.py'
```

The image compiles and runs tests during build. The bind mount retains reports in
the checkout. `make clean` before switching between host and container builds so
that an executable from another platform is never reused. CI checks both local
Linux commands and the Docker image; it does not pretend a missing migration ran.

## Architecture and interfaces

| File | Responsibility |
| --- | --- |
| `cobol/batch.cob` | File handling, reset for each record, dispatch, IDs, counts, totals |
| `cobol/validate.cob` | Length, ID, numeric class checks, contract range, indicator |
| `cobol/payment.cob` | Prospective-payment calculation using exact packed decimals |
| `cobol/copybooks/claim.cpy` | Raw fields and shared parsed interface |
| `tools/fixtures.py` | JSON-to-fixed-width serialization and seeded input generation |
| `tools/verify.py` | Execute, validate, check curated expectations, compare implementations |
| `tools/capture_baseline.py` | Retain real COBOL input/output and runtime provenance; no payment calculation |
| `tests/test_verification.py` | Batch and harness fault injection; no Python policy oracle |

Each implementation must accept this command-line contract:

```sh
build/msp-batch INPUT.dat RESULTS.csv TOTALS.csv
```

Input is ASCII, exactly 73 bytes per claim excluding LF (CRLF is also accepted).
There is no header. The fixture utility consumes readable integer-cent JSON:

```sh
python3 tools/fixtures.py --source fixtures/curated.json --output build/curated.dat
```

| Positions (1-based) | Width | Field | Encoding |
| --- | ---: | --- | --- |
| 1–12 | 12 | Claim ID | 1–12 uppercase ASCII letters, digits, `_` or `-`; right-pad spaces |
| 13–22 | 10 | Covered charges | Zero-padded unsigned integer cents |
| 23–32 | 10 | Gross Medicare payable before deductions | Same |
| 33–42 | 10 | Primary payment for covered services | Same |
| 43–52 | 10 | Applicable deductible | Same |
| 53–62 | 10 | Applicable coinsurance | Same |
| 63–72 | 10 | Lower contractual acceptance amount | Same, or exactly `----------` for absent |
| 73 | 1 | Primary payment accepted/obligated as payment in full | Exactly `Y` or `N` |

Each amount is 0–9,999,999,999 cents ($99,999,999.99). Explicit zero contract is
present and yields a zero cap; absent contract uses charges. Contract equal to
charges is allowed; contract above charges is invalid. Deductible plus coinsurance
uses 11 digits, so two maximum values cannot overflow. Gross may exceed charges;
primary or deductions may exceed caps and produce a valid zero payment.

The batch supports at most 10,000 records. Its maximum sum is
99,999,999,990,000 cents, within the 15-digit total. IDs must be unique within a
batch, including identifiable rejected records. Invalid ID/length uses reserved
identity `@` plus a ten-digit record number; `@` cannot occur in a valid input ID.
Input records do not carry a sequence number; the driver assigns it.

Malformed records up to 4,096 bytes receive `INVALID`, zero payment, and a stable
reason; processing continues. A blank physical line is an invalid record, not EOF.
Lines beyond 4,096 bytes, duplicate identifiable IDs, record-limit violations,
usage errors, and file failures abort with exit 2; discard partial outputs.
An empty file is a successful zero-record batch. Numeric validation precedes
arithmetic. Rejection precedence is length, ID, required/optional numeric fields,
contract range, then flag. Validation always precedes payment-in-full evaluation.

Use distinct input/output/totals paths, including resolved symlinks and aliases;
outputs are replaced. The executable rejects identical path strings; callers
must avoid aliases referring to the same file. Diagnostics go to stderr;
CSV goes only to files. Exit 0 means batch execution succeeded, even when
individual records are invalid. There are no other application exit codes.

Results CSV has exact header `record_no,claim_id,status,payment_cents,reason`.
Totals CSV has header `records,paid,zero,invalid,payment_cents` and one data row.
Unsigned digit strings may include leading zeros; amounts are interpreted exactly
as integer cents. Status is `PAID`, `ZERO`, or `INVALID`. Payment reasons, in order,
are `PAYMENT_IN_FULL`, `PRIMARY_AT_CAP`, `DEDUCTIONS_AT_CAP`, then
`SECONDARY_PAYABLE`. Invalid reasons are `BAD_LENGTH`, `BAD_ID`, `BAD_AMOUNT`,
`BAD_CONTRACT`, and `BAD_FLAG`. These are **demo interface codes**.

The harness rejects missing, duplicate, unexpected, malformed, or inconsistent
rows; compares IDs, statuses, reasons and integer payments; and reconciles counts
and sums. It treats crashes, timeouts, missing files, and nonzero exits as failures.
Reports are JSON and terminal summaries are concise. Exit 0 is pass, 1 is failure,
and 2 is missing candidate/CLI usage. `make` itself normally exits 2 on any failed
recipe, so use the report or direct harness invocation for precise distinctions.

## What the evidence means

Curated expectations were specified from published examples and hand-worked
synthetic boundaries, separately from the executable. They provide limited
business-rule evidence. Executable-to-executable parity establishes agreement
on the records tested; both programs could still share the same policy error.
Neither passing all fixtures nor matching 1,000 random records proves complete
Medicare correctness. There is no Python reference payment implementation.

Start the demonstration with [the runbook](docs/demo-runbook.md), then give Devin
[DEVIN_TASK.md](DEVIN_TASK.md). Actual build/test evidence and limitations are
recorded in [verification](docs/verification.md).

The [readiness and ownership checklist](docs/demo-readiness.md) separates this
prepared starter from Devin's remaining work. The [included CMS Example 3
excerpt](docs/cms-example-3.md) anchors the visible $500 case. Devin must create
new substantive tests before migration, complete the policy/COBOL/test/Python
mapping, retain dual outputs and a side-by-side report, and save/test native
Devin Playbooks for migration and the [synthetic follow-up](docs/follow-up-exercise.md).
Those Playbooks and completed migration examples do not exist merely because
their specifications are checked into this repo. Use a pinned starter commit for
fresh live runs, and record actual work plus human review/intervention time.

## Presentation app (Migration Evidence)

```sh
make demo          # compiles COBOL, generates batches, serves http://localhost:8765
make demo-live     # same, but refuses to start unless DEVIN_API_KEY is set (Start Devin live)
make demo-refresh  # runs every live check once into build/demo-runs/<UTC>/ (terminal only)
```

Requires `python3` 3.10+, `make`, `git`, and GnuCOBOL 3.x (`sudo apt-get install -y gnucobol gcc make`). No other packages.
Presenter guide: `docs/presentation/presenter-guide.md`. Readiness checklist: `docs/presentation/readiness-checklist.md`.
