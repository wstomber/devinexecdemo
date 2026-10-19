# Stage 1: what the COBOL program does, explained by Devin

Author: Devin (rehearsal session
[227ede59…](https://app.devin.ai/sessions/227ede5941704863b4c28458ebdba9ff)).
Starter commit: `be0b00ec5a2369d50a34d351694b187ae2300fe4` (`demo/starter-be0b00e`). This is a synthetic
educational MSP module derived from public CMS rules. It is not CMS production code.

## The customer problem in one paragraph

A long-lived payment program decides how much Medicare owes as **secondary payer**
after another insurer has already paid. Rewriting it in a new language is risky.
The new program can look correct on ordinary claims and still change the amount
owed when a contractual exception applies. Reviewers therefore need to trace each
rule from the published policy to the old code, the tests, the new code, and the
observed results. They should not have to trust a translation.

## Why the $500 case matters (CMS-EX3)

CMS Pub. 100-05, Ch. 5, §40.8.3 Example 3 (PDF pp. 83–84) has these inputs:
- Charges $15,000 and gross Medicare payable $14,000.
- Primary payer paid $12,500.
- The provider is **obligated to accept $13,000** as payment in full (the OTAF).
- The $1,556 deductible is a **historical example input**. Coinsurance is $0.

Medicare pays the lowest of four limits:

| Limit | Arithmetic | Result |
| --- | --- | ---: |
| Gross − primary | 14,000 − 12,500 | 1,500 |
| Gross − deductions | 14,000 − 1,556 | 12,444 |
| **Charge basis (OTAF) − primary** | **13,000 − 12,500** | **500** |
| Charge basis (OTAF) − deductions | 13,000 − 1,556 | 11,444 |

Payment: **$500**. If the program ignored the contractual acceptance amount and
used the $15,000 charges, the lowest limit would be $1,500. That overpays by
$1,000 on this one claim. The $13,000 is the *total* the provider must accept.
It does not mean the $12,500 primary payment was itself accepted as payment in
full, so the claim has `full=N`. A migration that dropped one branch would
produce a plausible but wrong number. That is why the tests below exist.

## The three kinds of evidence, and what each one establishes

1. **Independent policy expectations** (`tests_policy/`, written and run against
   COBOL *before* any Python existed). These tie expected results to the
   published rules. This is the only layer that says anything about policy.
2. **Python unit tests** (`tests_python/`). These exercise the new implementation
   function by function: limits, zero reasons, validation, and framing.
3. **Executable comparison** (the existing `tools/verify.py` plus the new
   `tools/demo_compare.py`). The same batches go through both programs. The
   check requires an exact match on cents, statuses, reasons, record counts,
   and totals.
   - Agreement shows the two programs behave the same on the tested inputs.
   - It does *not* show that both programs read the policy correctly.

## What a human reviewer should assess

- Is each hand-derived expectation in `tests_policy/expectations.json` faithful
  to the cited CMS text? Check the CMS-EX3 arithmetic above and the
  interface/policy split.
- Are the interface decisions acceptable? These include reason precedence, the
  demo reason codes, contract-equal-to-charges, and explicit zero contracts.
  They are demo choices, not CMS policy.
- Does `python/msp.py` keep exact integer-cent arithmetic? Does it reject
  malformed records without treating them as valid zeros?
- Does the comparison report show MATCH on every row, plus matching counts and
  totals? Are the scope limits stated honestly?

## Program structure

| File / paragraph | Responsibility |
| --- | --- |
| `cobol/batch.cob` `main` | Argument count (exactly 4: INPUT CWF OUTPUT TOTALS), distinct paths, load the CWF reference file (`load-cwf`/`parse-cwf`), open files, header rows, byte-by-byte read loop, totals row |
| `batch.cob` `finish-line` | Strip one trailing CR, abort if the line exceeds 4,096 bytes, process the record |
| `batch.cob` `process-record` | Enforce the 10,000-record limit, **`initialize claim-interface`** (state reset), assign the provisional ID `@` + 10-digit record number, validate, check for duplicate IDs, calculate, then call `cwf-check` for valid claims only, count, write |
| `cobol/validate.cob` `validate-record` | Length → ID → numeric class tests → contract range → flag → MBI → service date |
| `cobol/payment.cob` `calculate-prospective-payment` | Payment in full, charge basis, cap, primary/deduction zero reasons, payment |
| `cobol/cwf.cob` `check-claim` | CWF pre-payment check after pricing: entitlement on the service date, duplicate of a posted claim, MSP primary not billed; else accepted and the payment released |
| `cobol/copybooks/claim.cpy` | 92-byte raw layout, parsed packed-decimal (`comp-3`) fields and CWF result fields |
| `cobol/copybooks/cwf.cpy` | CWF reference tables: up to 1,000 beneficiaries and 1,000 posted claims |

## Inputs and record framing

- Each record is exactly **92 ASCII bytes**, followed by LF or CRLF, with no header.
  - The fields are: ID (12), charges, gross, primary, deductible, coinsurance,
    and contract (10 digits of cents each), the `full` flag (1), the synthetic
    beneficiary identifier MBI (11) and the date of service `YYYYMMDD` (8).
  - The contract field is exactly `----------` when absent.
- The program reads one byte at a time:
  - LF ends a record, and one CR before the LF is removed.
  - A final record without a newline is still processed.
  - A blank physical line is an *invalid record*, not end of file.
  - Lines up to 4,096 bytes are judged as records (anything other than 92 bytes
    gives `BAD_LENGTH`). A line over 4,096 bytes is **fatal**.
- An empty file is a valid zero-record batch.

## Outputs and exact cents

- `RESULTS.csv` has the header
  `record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents`
  and one row per record. `payment_cents` is what was calculated;
  `released_cents` is what CWF lets through (zero unless `ACCEPTED`).
  - `record_no` and `payment_cents` are zero-padded to 10 digits, because COBOL
    `pic 9(10)` is written via `STRING`.
  - The verifier treats them as unsigned integers.
- `TOTALS.csv` has the header
  `records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents` and
  one row: 10-digit counters and 15-digit totals.
- All money is unsigned integer cents in packed decimal, so there is no rounding
  anywhere.
  - The deductible + coinsurance sum is 11 digits wide, so two maximum values
    (`9,999,999,999`) cannot overflow.
  - The `payment-total` field is 15 digits.

## Validation and reason precedence (`validate-record`)

Validation stops at the first failure, in this order:

| Order | Check | Reason |
| --- | --- | --- |
| 1 | Length ≠ 92 | `BAD_LENGTH` |
| 2 | ID is all spaces, contains a character outside `A–Z 0–9 - _`, or has an embedded space | `BAD_ID` |
| 3 | Any of the five required amounts fails the COBOL `NUMERIC` class test, or the contract is neither `----------` nor numeric | `BAD_AMOUNT` |
| 4 | Contract > charges | `BAD_CONTRACT` |
| 5 | Flag not `Y`/`N` | `BAD_FLAG` |
| 6 | MBI not 11 of `A–Z 0–9` | `BAD_MBI` |
| 7 | Service date not 8 digits, month 01–12, day 01–31 | `BAD_DATE` |

- The claim ID is copied out *only after* the ID check passes.
  - `BAD_LENGTH` and `BAD_ID` rows therefore keep the reserved identity
    `@0000000NNN`.
  - Every later rejection keeps its real ID, so it still takes part in the
    duplicate-ID check.
- Invalid records get status `INVALID` with payment 0. They are counted as
  `invalid`, and the batch continues.

## Payment calculation (`calculate-prospective-payment`)

```cobol
if raw-full = "Y"            -> ZERO / PAYMENT_IN_FULL
move claim-charges to charge-basis
if claim-has-contract = 1    -> move claim-contract to charge-basis   *> OTAF replaces charges
compute payment-cap = function min(claim-gross, charge-basis)
if claim-primary >= payment-cap -> ZERO / PRIMARY_AT_CAP
compute deductions = claim-deductible + claim-coinsurance
if deductions >= payment-cap    -> ZERO / DEDUCTIONS_AT_CAP
compute claim-payment = payment-cap - max(deductions, claim-primary)
                                -> PAID / SECONDARY_PAYABLE
```

- **The `claim-has-contract` branch.** When a contract is supplied, the program
  *replaces* covered charges with it as the charge basis. It is not subtracted,
  and it is not an extra limit. This matches §40.8.2: "the amount the provider
  is obligated to accept … is considered … the hospital's charges".
- **`min(claim-gross, charge-basis)`, then `− max(T, P)`.** This is an algebraic
  shortcut for the four §40.8.2/§40.8.3 limits, `min(G−P, G−T, B−P, B−T)`. The
  zero branches run first, so unsigned packed fields never go negative.
- **Contract amount vs payment in full.** `full=Y` means the *received primary
  payment* was accepted or required as payment in full, so Medicare pays nothing
  (§40.8). A contract amount with `full=N` is only a lower charge basis. In
  CMS-EX3, $13,000 is the contract amount and the $12,500 primary payment was
  *not* accepted in full.
- **Zero-reason precedence is a demo interface decision.** The order is:
  payment in full, then primary at cap, then deductions at cap. So an all-zero
  claim reports `PRIMARY_AT_CAP` (0 ≥ 0).

## State reset, duplicates, limits, failure behavior

- `initialize claim-interface` runs for **every** record. Without it, a rejected
  record's parsed contract (`claim-has-contract`) could leak into the next claim.
- Duplicate *identifiable* IDs are **fatal**: exit 2, with a message on stderr.
  This includes rejected records that already passed the ID check.
  `@`-identities never collide.
- Each of these also exits 2 through `fatal-io`, and partial outputs must be
  discarded:
  - the 10,001st record;
  - a line over 4,096 bytes;
  - a wrong argument count;
  - identical path strings;
  - any file open, read, write, or close failure.
- Exit 0 means the batch ran, even when some records were invalid. There are no
  other exit codes.

## Observed baseline (this session)

The baseline commands were `make doctor`, then
`make build baseline generate test capture-baseline`. All of them exited 0.
- Log: `evidence/rehearsal/stage1-baseline.log`.
- Retained capture: `evidence/rehearsal/stage1-cobol-baseline/`.
- Environment: GnuCOBOL 3.1.2.0, Python 3.10.12, GCC 11.4.0.
- Curated batch: 30 records (12 PAID, 9 ZERO, 9 INVALID), totalling
  10,000,450,202 cents.
- Synthetic batch: seed 20261017, 1,000 records (271 PAID, 729 ZERO, 0 INVALID),
  totalling 514,352,570,951 cents.
- The `files_sha256` and `source_files_sha256` in the new manifest are **identical**
  to `docs/evidence/cobol-baseline/manifest.json`. The capture reproduces exactly.

This is observed COBOL behavior. It is not a payment oracle.

## The CWF pre-payment check (`cobol/cwf.cob`)

CMS Pub. 100-04 Ch. 27 §20 describes the order: the contractor prices the claim,
then sends it to the Common Working File for pre-payment validation and
authorization, then pays or denies. After `calculate-payment`, `batch.cob` calls
`cwf-check` for every valid (`PAID` or `ZERO`) claim. Invalid claims are written
as `NOT_SENT` / `CLAIM_INVALID`. The checks run in order and the first failure
wins (each ends in `goback`):

1. `NOT_ENTITLED`: the MBI is not in the beneficiary table, or the service date
   is outside the inclusive entitlement period (`99999999` = open-ended).
2. `DUPLICATE`: a posted claim (`H` record) has the same MBI, service date and
   charges.
3. `MSP_PRIMARY_NOT_BILLED`: the MSP period from Medicare's MSP file covers the
   service date, but the claim shows a primary payment of 0.

Otherwise the claim is `ACCEPTED` with `DISPOSITION_01` (CWF's "accepted as is")
and `claim-released` = `claim-payment`. A rejected claim keeps its calculated
payment for review, but releases 0. CMS-EX3 is accepted and releases $500; the
look-alikes `EX3-NOT-ENT`, `EX3-DUP` and `EX3-MSP-NOBL` calculate a payment but
release $0. The reject codes are demo-defined; this is three illustrative checks,
not all of CWF.
