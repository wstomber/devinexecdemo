# 01 — What the legacy COBOL does (Stage 1 explanation)

Live run, starter commit `be0b00ec5a2369d50a34d351694b187ae2300fe4`. This is a
synthetic educational module derived from public CMS rules. It is not CMS
production code, and nothing below describes CMS internal systems.

## The customer problem in one paragraph

A payment program decides how much money Medicare pays after another insurer has
paid first (Medicare Secondary Payer, MSP). If a rewrite changes one comparison,
the program can still run and still look right on ordinary claims, yet pay the
wrong amount on contractual exceptions. CMS-EX3 shows this. The correct scoped
payment is **$500**. If the code ignores the provider's $13,000 obligated
acceptance amount, it pays **$1,500**, which is $1,000 too much. After the payment
is calculated, a synthetic Common Working File (CWF) pre-payment check decides
whether that money is actually *released*. The reviewer should assess three
separate evidence layers:

1. independent policy-derived expectations, written before any Python existed;
2. focused Python unit tests;
3. executable-to-executable comparisons on identical batches.

Layer 3 only proves that the two programs agree on the tested inputs. Layer 1 is
the only layer tied to policy, and only for the cases it lists.

## Stage 1 execution (actual)

`make doctor` followed by `make build baseline generate test capture-baseline`
exited 0. The log is `evidence/live/stage1-baseline.log`, and the capture is
copied to `evidence/live/baseline/`. Every source hash and every input/output hash
in the new `manifest.json` equals `docs/evidence/cobol-baseline/manifest.json`.
The comparison is in `evidence/live/baseline-hash-check.txt`. Only
`source_commit` (the capture was made one commit earlier), the timestamp and the
runtime metadata differ. Curated batch: 33 records, 15 PAID, 9 ZERO, 9 INVALID,
10,001,694,602 cents calculated, 21 accepted, 3 rejected, 10,000,450,202 cents
released. Seeded synthetic batch: 1,000 records, 271 PAID, 729 ZERO,
485,289,809,347 cents calculated, 736 accepted, 264 rejected, 344,091,123,732
cents released.

## Program structure

| File | Program / paragraph | Job |
| --- | --- | --- |
| `cobol/batch.cob` | `msp-batch`: `main` (l.58), `finish-line` (l.122), `process-record` (l.136), `load-cwf`/`parse-cwf` (l.189/206), `fatal-io` (l.263) | CLI, CWF load, byte framing, reset, IDs, dispatch, counts, totals, CSV |
| `cobol/validate.cob` | `validate-claim` / `validate-record` (l.10) | Rejection precedence |
| `cobol/payment.cob` | `calculate-payment` / `calculate-prospective-payment` (l.12) | MSP payment and zero reasons |
| `cobol/cwf.cob` | `cwf-check` / `check-claim` (l.17) | Entitlement → duplicate → MSP primary billed |
| `cobol/copybooks/claim.cpy` | `claim-interface` | 92-byte raw layout plus parsed COMP-3 fields shared by CALL BY REFERENCE |
| `cobol/copybooks/cwf.cpy` | `cwf-tables` | In-memory CWF tables (1,000 `B`, 1,000 `H`) |

## Inputs and outputs

`msp-batch INPUT CWF OUTPUT TOTALS`. Any other argument count prints a usage line
and exits 2. If any two of the four path strings are identical, it exits 2
(`batch.cob` l.69–76; aliases are not resolved).

**Claim record, 92 bytes** (`claim.cpy`): ID 1–12; charges 13–22; gross 23–32;
primary 33–42; deductible 43–52; coinsurance 53–62; contract 63–72 (`----------`
means absent); full flag 73; MBI 74–84; date of service 85–92 (`YYYYMMDD`,
redefined as year/month/day). Every amount is ten unsigned ASCII digits of
integer cents.

**CWF reference file** (line sequential, read into `cwf-tables` by `load-cwf`
before the claims file is opened):

- `B` + MBI(11) + entitled-from(8) + entitled-to(8) + MSP-from(8) + MSP-to(8),
  44 bytes. Positions 45–64 must be spaces. The MBI must not be blank. Positions
  13–28 must be numeric. Positions 29–44 must be either all `-` (no MSP period) or
  all numeric.
- `H` + MBI(11) + date of service(8) + charges(10), 30 bytes. Positions 31–64 must
  be spaces and 13–30 must be numeric.
- Any other first byte, a blank line, a non-`00` read status, or a 1,001st `B`
  or `H` record goes to `bad-cwf` and then `fatal-io`, which exits 2.
- The record area is `pic x(64)`. Observed GnuCOBOL 3.1.2 line-sequential
  behavior, probed on this VM: every CR byte in a line is discarded, bytes after
  position 64 are silently dropped, and a short line is space-padded. Tab, NUL
  and other control bytes are kept as data, so they fail the space or numeric
  tests. These are runtime behaviors, not documented interface rules, and Python
  must reproduce them.

**Results CSV**: header
`record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents`,
followed by one row per record. `record_no`, `payment_cents` and `released_cents`
are zero-padded 10-digit fields (`pic 9(10)`). **Totals CSV**: header
`records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents`, then
one row. Counts are 10 digits and both cent totals are 15 digits (`pic 9(15)`).

## Exact cents

Amounts are moved from validated ASCII digits into `pic 9(10) comp-3`, which is
packed decimal integer cents. There is no fraction and no rounding. The
deduction sum is `pic 9(11)`, so 9,999,999,999 + 9,999,999,999 cannot overflow.
The batch totals are `pic 9(15)`. The largest possible total, 10,000 ×
9,999,999,999 = 99,999,999,990,000, fits in 15 digits.

## Framing and limits (`main` l.94–110, `finish-line` l.122–135)

The input is read **one byte at a time** (`record contains 1 characters`), so
no runtime line handling applies.

- LF (`x"0A"`) ends a line. At EOF, a non-empty partial line is processed, so a
  missing final newline is fine. An empty file gives zero records and exit 0.
- `finish-line` removes **one** trailing CR (CRLF support). Any other CR is data.
- A blank physical line (length 0) is still processed as a record and gets
  `BAD_LENGTH`. A blank line is not EOF.
- Transport bound: when a 4,098th byte arrives (`input-length >= 4097`), or a
  line is still longer than 4,096 bytes after CR removal, the program goes to
  `fatal-io` and exits 2. A 4,096-byte line is one `BAD_LENGTH` record.
- Record bound: `process-record` aborts (exit 2) before counting a 10,001st record.

## Validation precedence (`validate-record`, validate.cob l.10–73)

Validation sets `INVALID`, writes a reason, and changes it as each check passes.
The first failure wins:

1. `BAD_LENGTH`: the length after CR removal is not 92.
2. `BAD_ID`: the ID is all spaces, contains a byte outside `A–Z 0–9 - _`, or has
   a non-space byte after a space. Leading or embedded spaces are invalid.
   Trailing spaces are padding.
3. `BAD_AMOUNT`: any of the five required amounts is `NOT NUMERIC`, or the
   contract is neither `----------` nor numeric. **A malformed contract is
   `BAD_AMOUNT`, not `BAD_CONTRACT`.** No numeric MOVE happens before these class
   tests.
4. `BAD_CONTRACT`: a present contract is greater than charges. A contract equal
   to charges is allowed, and so is zero.
5. `BAD_FLAG`: the flag is not exactly `Y` or `N`.
6. `BAD_MBI`: any of the 11 bytes is outside `A–Z 0–9`.
7. `BAD_DATE`: the date is not 8 digits, the month is outside `01`–`12`, or the
   day is outside `01`–`31`. There is **no calendar check**, so `20250230` is
   valid. This is an interface fact to review, not a policy claim.

Validation always comes before the payment-in-full test, so `full=Y` cannot rescue
a malformed record.

## State reset and IDs (`process-record` l.136–188)

`initialize claim-interface` clears every raw and parsed field for each record,
including `claim-has-contract`. A contract parsed on a rejected record cannot
leak into the next one. Before validation, `claim-id` is set to `@` plus the
10-digit record number (for example `@0000000021`). Only an ID that passes the
`BAD_ID` check replaces it. `@` can never appear in a valid ID. Every
identifiable ID (any record that got past `BAD_ID`, **including later-rejected
records**) is checked against `seen-id`. A repeat is fatal (exit 2).

## Payment calculation (`calculate-prospective-payment`, payment.cob l.12–39)

```
move 0 to claim-payment; move "ZERO" to claim-status             l.13–14
if raw-full = "Y"  -> PAYMENT_IN_FULL                             l.16–19
move claim-charges to charge-basis                                l.20
if claim-has-contract = 1  move claim-contract to charge-basis    l.21–23
compute payment-cap = function min(claim-gross, charge-basis)     l.24
if claim-primary >= payment-cap -> PRIMARY_AT_CAP                 l.25–28
compute deductions = claim-deductible + claim-coinsurance         l.29
if deductions >= payment-cap -> DEDUCTIONS_AT_CAP                 l.30–33
compute reduction-amount = function max(deductions, claim-primary) l.34
compute claim-payment = payment-cap - reduction-amount            l.35
PAID / SECONDARY_PAYABLE                                          l.36–37
```

**The `claim-has-contract` branch.** Pub. 100-05 Ch. 5 §40.8.2 says that when the
provider is obligated to accept a lower amount (OTAF), that amount takes the place
of the charges. The COBOL does exactly this. It overwrites `charge-basis` with
`claim-contract`, and every later comparison uses that basis.

**`min(claim-gross, charge-basis)`.** The four §40.8.3 limits are G−P, G−T, B−P
and B−T, where B is the charge basis and T = deductible + coinsurance. They
simplify to `min(G, B) − max(P, T)`. Taking the cap first and testing `P >= cap`
and `T >= cap` before subtracting keeps the unsigned packed fields from going
below zero. The zero checks also fix the reason precedence: `PAYMENT_IN_FULL`,
then `PRIMARY_AT_CAP`, then `DEDUCTIONS_AT_CAP`. An all-zero claim is
`PRIMARY_AT_CAP`, because 0 >= 0.

**Why $13,000 OTAF is not "the $12,500 primary accepted in full".** In CMS-EX3,
the provider agreed to accept $13,000 in total. That figure replaces the $15,000
charges as the basis. The insurer actually paid $12,500, which is less than
$13,000, so the provider has not been paid in full and `full=N`. Trace:
B = 1,300,000; cap = min(1,400,000, 1,300,000) = 1,300,000;
P = 1,250,000 < cap; T = 155,600 < cap;
payment = 1,300,000 − max(155,600, 1,250,000) = **50,000 cents = $500**.
If the $12,500 had been accepted in full (`full=Y`), the payment would be $0. If
the contract were ignored (B = 1,500,000), cap = 1,400,000 and the payment would be
150,000 cents = $1,500.

## Totals and fatal behavior

`main` counts each record as PAID, ZERO or INVALID. It adds `claim-payment`
(calculated) to `payment-total` and `claim-released` to `released-total`. It
counts CWF `ACCEPTED` and `REJECTED`, but not `NOT_SENT`. On success, exit 0 even
if records are invalid. `fatal-io` prints a message to stderr, sets return code 2
and `STOP RUN`s. The fatal cases are usage, identical paths, file open/read/write
errors, a malformed or oversized CWF file, an over-long line, a 10,001st record,
or a duplicate ID. Outputs may already be partly written, and the contract says
to discard them. If the CWF file fails, nothing is opened for output yet.

## CWF pre-payment check (`cobol/cwf.cob`, `check-claim` l.17–52)

Pub. 100-04 Ch. 27 §20/§20.2.2: the contractor prices the claim first, then CWF
validates and authorizes payment. In this demo, CWF is called only when
`claim-status` is `PAID` or `ZERO` (batch.cob l.162). Invalid claims have no
trustworthy MBI, date or amounts to check, so they get `NOT_SENT` /
`CLAIM_INVALID`. **ZERO claims are still sent**, because a zero payment still has
an entitlement and history decision.

Order (first failure wins):

1. **Entitlement** (l.22–32): find the *first* `B` record with the claim's MBI. If
   none exists, or the date of service is before `entitled-from` or after
   `entitled-to` (both inclusive), the result is `REJECTED` / `NOT_ENTITLED`.
   `99999999` means the entitlement is open-ended.
2. **Duplicate** (l.33–41): any `H` record with the same MBI, the same date of
   service and the same **covered charges** (not contract, not payment) gives
   `DUPLICATE`. Duplicates are matched only against CWF history, never against
   other claims in the batch.
3. **MSP primary not billed** (l.42–48): if the beneficiary has an MSP period
   that covers the date (inclusive) and `claim-primary = 0`, the result is
   `MSP_PRIMARY_NOT_BILLED`.
4. Otherwise `ACCEPTED` / `DISPOSITION_01`, and `claim-released = claim-payment`.

**Calculated vs released.** A CWF rejection never changes `payment_cents` or the
payment status/reason. It only sets `released_cents` to 0. CMS-EX3 is entitled,
new, and has a primary payment, so it is `ACCEPTED` and releases 50,000 cents. The
curated look-alikes `EX3-NOT-ENT`, `EX3-DUP` and `EX3-MSP-NOBL` still show their
calculated payments but release 0.

## Known edges worth reviewer attention

- Date validation has no calendar check (`20250230` is valid). Entitlement and
  MSP comparisons are numeric.
- Duplicate `B` records for the same MBI are not rejected. The first one wins.
- Path equality uses `pic x(1024)` string comparison. Trailing spaces and paths
  over 1,024 bytes are not modelled by the Python port, and both are untested.
