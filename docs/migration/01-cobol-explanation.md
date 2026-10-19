# 01 — What the legacy COBOL does (Stage 1 explanation)

Synthetic educational example. This is not CMS production code and does not describe
how CMS systems are built. Policy references: CMS Pub. 100-05 Ch. 5 §§10.1, 40.8–40.8.3
and Pub. 100-04 Ch. 27 §20, as excerpted and interpreted in `docs/rules.md` and
`docs/cms-example-3.md`. The demo reason codes, file layouts, limits and exit codes are
interface decisions of this repository, not CMS codes.

Starter commit: `be0b00ec5a2369d50a34d351694b187ae2300fe4` (branch `demo/starter-be0b00e`).
Stage 1 run log: `evidence/live/stage1-baseline.log`; capture: `evidence/live/baseline/`;
hash check against `docs/evidence/cobol-baseline/manifest.json`: `evidence/live/baseline-hash-check.txt`
(all 8 input/output hashes and all 13 source hashes MATCH). Runtime file-handling probes:
`evidence/live/cobol-probes.sh` and `.log`.

## The customer problem in one paragraph

A payment program decides how much Medicare pays after another insurer (the primary payer)
has paid. A replacement that "works" on ordinary claims can still change money owed on
the unusual ones: a contractual acceptance amount, a claim that is already paid, a person
whose entitlement ended. CMS-EX3 shows the stakes: ignoring the provider's $13,000
obligated acceptance amount would pay **$1,500** instead of **$500**, a $1,000
overstatement on one claim. The reviewer needs to see, separately, (1) expectations
derived from the public rule, (2) tests of the new code's functions, and (3) exact
executable-to-executable comparison, and should judge whether those three layers, with
their stated limits, are enough to accept the change.

## Programs and data flow

| File | Role |
| --- | --- |
| `cobol/batch.cob` (`msp-batch`) | Main program: arguments, CWF load, byte-by-byte framing, per-record reset, ID/duplicate handling, dispatch, CSV output, counts, totals, fatal exit |
| `cobol/validate.cob` (`validate-claim`) | Field validation in fixed precedence; converts text to packed decimals |
| `cobol/payment.cob` (`calculate-payment`) | MSP prospective payment (`calculate-prospective-payment`) |
| `cobol/cwf.cob` (`cwf-check`) | Synthetic CWF pre-payment check |
| `cobol/copybooks/claim.cpy` | Shared record layout: raw 92 bytes + parsed fields + results |
| `cobol/copybooks/cwf.cpy` | In-memory CWF reference tables (≤1,000 `B`, ≤1,000 `H`) |

```
msp-batch INPUT CWF RESULTS.csv TOTALS.csv
  load-cwf (CWF file → tables)            fatal on any malformed line
  open INPUT, RESULTS, TOTALS              fatal on any file error
  for each LF-terminated line:
     reset claim-interface; provisional ID "@"+10-digit record number
     validate-claim  → VALID or INVALID+reason
     duplicate-ID check (identifiable IDs only, even if INVALID) → fatal
     VALID → calculate-payment → PAID/ZERO + reason + payment
     PAID/ZERO → cwf-check → ACCEPTED/REJECTED + reason + released
     INVALID → NOT_SENT / CLAIM_INVALID, released 0
     write CSV row, add to counts/totals
  write totals, close, exit 0
```

## Inputs

### The 92-byte claim record (`claim.cpy` lines 2–16)

| Bytes | Field | Rule (validate.cob) |
| --- | --- | --- |
| 1–12 | claim ID | 1–12 of `A–Z 0–9 - _`, left-justified, right-padded with spaces; no embedded/leading spaces |
| 13–22 | covered charges C | exactly 10 ASCII digits = integer cents |
| 23–32 | gross Medicare payable G | same |
| 33–42 | primary payment P | same |
| 43–52 | deductible D | same |
| 53–62 | coinsurance K | same |
| 63–72 | contract (OTAF) A | 10 digits, or exactly `----------` = absent |
| 73 | payment-in-full flag | exactly `Y` or `N` |
| 74–84 | MBI (synthetic) | 11 of `A–Z 0–9` |
| 85–92 | date of service | 8 digits, month `01`–`12`, day `01`–`31` (no calendar check: `20250230` is valid) |

### The CWF reference file (`batch.cob` `load-cwf`/`parse-cwf`, lines 189–240)

Read as GnuCOBOL LINE SEQUENTIAL into a 64-byte record (`cwf-record pic x(64)`).

| Type | Layout (1-based) | Fatal if |
| --- | --- | --- |
| `B` beneficiary, 44 bytes | 1 `B`; 2–12 MBI; 13–20 entitled from; 21–28 entitled to (`99999999` = open); 29–36 MSP from; 37–44 MSP to (`----------------` = no MSP period) | bytes 45–64 not spaces; MBI all spaces; 13–28 not 16 digits; 29–44 neither 16 `-` nor 16 digits; 1,001st `B` |
| `H` posted claim, 30 bytes | 1 `H`; 2–12 MBI; 13–20 date of service; 21–30 charges (cents) | bytes 31–64 not spaces; MBI all spaces; 13–30 not 18 digits; 1,001st `H` |
| anything else (incl. blank line) | — | always fatal |

Only digit-class is checked for CWF dates (no month/day check). Observed GnuCOBOL 3.1.2
LINE SEQUENTIAL behavior (`evidence/live/cobol-probes.log`): every CR byte in a line is
dropped (so CRLF works), bytes after the 64th are silently discarded, TAB/NUL/FF are kept
as data, an empty file or a file of only CR is a valid empty reference, a missing final
newline is fine, and a CWF path that is a directory reads as an empty reference (exit 0,
every valid claim `NOT_ENTITLED`). The last point is a runtime quirk flagged for human
review; it fails safe (nothing is released).

## Outputs

`RESULTS.csv` header `record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents`;
`TOTALS.csv` header `records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents`
plus one row. Lines end in LF. Every number is a zero-padded display field because the
COBOL `STRING`s `PIC 9(n)` items: record_no / payment / released are 10 digits; counts are
10 digits; the two totals are 15 digits. Example: `0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000`.
Nothing is written to stdout; diagnostics go to stderr.

## Exact cents

All money is integer cents. Text is moved to `PIC 9(10) COMP-3` (packed decimal) only
after a NUMERIC class test (`validate.cob` 34–50), so there is no rounding and no binary
floating point anywhere. `deductions` and `reduction-amount` are `PIC 9(11)` so
`D + K` up to 19,999,999,998 cannot overflow. Totals are `PIC 9(15)`; the maximum,
10,000 × 9,999,999,999 = 99,999,999,990,000, fits.

## Framing and limits (`batch.cob` 94–135)

* The input is opened as a sequential file of **1-byte records**, so the program sees raw
  bytes (no runtime newline translation). LF (`x"0A"`) ends a line. At EOF a non-empty
  partial line is processed, so a missing final newline is fine; an empty file is a
  successful zero-record batch.
* `finish-line` removes **one** trailing CR (CRLF support). `\r\r\n` leaves 1 CR → `BAD_LENGTH`.
* A blank line is a record of length 0 → `INVALID/BAD_LENGTH`, not EOF.
* Transport bound: up to 4,096 bytes (after CR removal) is a malformed-but-processed
  record; the buffer holds 4,097 so that `4,096 bytes + CR` is still accepted. A line
  longer than 4,096 aborts with exit 2 (the byte loop aborts as soon as the 4,098th byte arrives).
* At most 10,000 records: the 10,001st record is fatal (`process-record` 137–140) —
  even if it is blank.

## Validation precedence and state reset (`validate.cob` 10–73)

First failure wins, in this order: `BAD_LENGTH` (length ≠ 92) → `BAD_ID` → `BAD_AMOUNT`
(any of C, G, P, D, K not 10 digits, then contract neither sentinel nor 10 digits) →
`BAD_CONTRACT` (A > C) → `BAD_FLAG` → `BAD_MBI` → `BAD_DATE`. Consequences:

* A malformed contract is `BAD_AMOUNT`, not `BAD_CONTRACT`; `BAD_CONTRACT` only means a
  well-formed contract above charges. `---------0` is malformed.
* Numeric class tests run before any numeric MOVE, so garbage never becomes a number.
  The class test is the ASCII digits `0`–`9` only: spaces, signs, `.`, TAB, NUL fail.
* `initialize claim-interface` (batch 143) clears raw **and** parsed fields — including
  `claim-has-contract` — for every record, so a contract or amount from a previous or a
  rejected record can never leak into the next one.

## Claim IDs and duplicates (`batch.cob` 144–158)

Before validation the ID is set to `@` + the 10-digit record number (`STRING "@" record-count`).
`validate-claim` replaces it with the input ID only once the ID passes. So `BAD_LENGTH`
and `BAD_ID` rows carry `@0000000021`-style IDs; every later rejection carries the real ID.
`@` is not a legal ID character, so the provisional IDs cannot collide with real ones.
Any repeat of a real (non-`@`) ID — including on a record that is otherwise INVALID — is
fatal (exit 2) with `duplicate claim ID`.

## Payment calculation: `calculate-prospective-payment` (`payment.cob` 12–38)

```
13  payment = 0; status = ZERO
16  if full = "Y"                    → PAYMENT_IN_FULL           (§40.8)
20  charge-basis = claim-charges
21  if claim-has-contract = 1
22      charge-basis = claim-contract   (OTAF replaces charges, §40.8.2)
24  payment-cap = min(claim-gross, charge-basis)
25  if primary >= payment-cap        → PRIMARY_AT_CAP
29  deductions = deductible + coinsurance
30  if deductions >= payment-cap     → DEDUCTIONS_AT_CAP
34  reduction = max(deductions, primary)
35  payment = payment-cap - reduction → PAID / SECONDARY_PAYABLE
```

This is the §40.8.3 A rule "Medicare pays the lowest of G−P, G−(D+K), B−P, B−(D+K)",
rewritten as `min(G, B) − max(D+K, P)` where B = A if present else C. The two zero
branches come first so the unsigned packed fields are never subtracted below zero; they
also fix the zero-reason precedence: `PAYMENT_IN_FULL` → `PRIMARY_AT_CAP` → `DEDUCTIONS_AT_CAP`.
An all-zero claim is therefore `PRIMARY_AT_CAP` (0 ≥ 0). A PAID payment is always ≥ 1 cent.

### Why the $13,000 OTAF is not "the $12,500 primary accepted in full"

The provider agreed to accept **$13,000 in total** for the services (the obligated-to-accept
amount, OTAF). §40.8.3 Example 3 says Medicare treats that $13,000 as the charges. The
primary insurer paid only $12,500 of it. "Accepted as payment in full" in §40.8 means the
provider accepts *the primary payment itself* as the whole payment — that would be `full=Y`
and Medicare would pay $0. Here the provider is still owed up to $13,000, so `full=N` and:

| Limit | Arithmetic | Result |
| --- | --- | --- |
| G − P | 14,000 − 12,500 | 1,500 |
| G − D | 14,000 − 1,556 | 12,444 |
| A − P | 13,000 − 12,500 | **500** |
| A − D | 13,000 − 1,556 | 11,444 |

Code trace: `charge-basis` 1,500,000 → 1,300,000 (line 22); `payment-cap` = min(1,400,000,
1,300,000) = 1,300,000; 1,250,000 < cap; deductions 155,600 < cap; reduction = max(155,600,
1,250,000) = 1,250,000; payment = **50,000 cents**. Without line 21–22, cap = 1,400,000 and
payment = 150,000 ($1,500). The $1,556 deductible is historical example input, not a rate.

## The CWF pre-payment check (`cobol/cwf.cob` 17–52)

Per Pub. 100-04 Ch. 27 §20 the contractor prices the claim and then CWF validates it;
payment is released only on acceptance. Only `PAID`/`ZERO` claims are sent
(`batch.cob` 162–167): an INVALID claim has no trustworthy MBI/date/amounts to look up,
so it is `NOT_SENT / CLAIM_INVALID`. A ZERO claim *is* sent (CWF still records it).

Order, first failure wins (starting state `REJECTED`, released 0):

1. **Entitlement** (22–32): find the first `B` whose MBI equals the claim MBI. Not found,
   or service date `< from` or `> to` (inclusive bounds) → `NOT_ENTITLED`.
2. **Duplicate** (33–41): any `H` with the same MBI, same service date and same charges
   (cents) → `DUPLICATE`. Matching is against CWF history only, not other claims in the
   batch; one cent or one day different is not a duplicate.
3. **MSP primary not billed** (42–48): the beneficiary has an MSP period that covers the
   service date (inclusive) and the claim's primary payment is 0 → `MSP_PRIMARY_NOT_BILLED`.
4. Otherwise `ACCEPTED / DISPOSITION_01` and `released = payment` (49–51).

**Calculated vs released:** `payment_cents` is always the calculated amount (a CWF
rejection is not a recalculation); `released_cents` is what CWF lets through — equal to the
payment when ACCEPTED, otherwise 0. CMS-EX3 (MBI `2MSP0000001`, 2025-03-15, primary
$12,500 inside a 2025 MSP period) passes all three checks: 50,000 calculated, `ACCEPTED`,
50,000 released. The three curated look-alikes calculate the same kind of payment but
release 0 (`NOT_ENTITLED`, `DUPLICATE`, `MSP_PRIMARY_NOT_BILLED`).

## Counts, totals and fatal behavior

Each record adds 1 to exactly one of paid/zero/invalid and, if sent, to accepted or
rejected; `payment_cents` and `released_cents` totals are sums over all rows (INVALID rows
contribute 0). `records = paid + zero + invalid = accepted + rejected + invalid`.

Exit 0 = the batch ran (even with INVALID records). Exit 2 (`fatal-io`, `stop run`) = usage
error (≠ 4 arguments), identical path strings (compared as 1,024-byte space-padded fields,
so `o.csv` and `o.csv ` collide; aliases like `./o.csv` are *not* detected), any file
open/read/write failure, malformed CWF record or table overflow, line > 4,096 bytes,
> 10,000 records, duplicate ID. Observed file effects: the CWF is loaded **before** any
output is opened, so a bad CWF or a missing input leaves existing outputs untouched; once
the outputs are opened (truncated) a later fatal leaves a partial results file (header and
the rows already processed) and an empty totals file. The contract is that the caller
discards outputs on exit 2.
