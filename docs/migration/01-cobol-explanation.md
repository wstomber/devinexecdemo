# 01 — What the COBOL starter does (Stage 1 explanation)

Live Playbook rehearsal, branch `devin/1792274347-playbook-rehearsal-migration`, starter
`37ceca17f110536d55261d5d19aa187781dd8851`. Synthetic educational application derived
from CMS Pub. 100-05 Ch. 5 §§40.8–40.8.3. It is not CMS production code.

## The customer problem, the money at stake, and what to review

A payment program that has been in service for a long time has to keep paying the
same cents after it is rewritten. A replacement can look correct on ordinary claims
and still overpay a contractual-cap claim. In the published CMS Example 3
(`CMS-EX3`), the provider must accept $13,000 as payment in full. Medicare's secondary
payment is **$500**. A rewrite that drops that cap pays **$1,500**, which overpays this
one claim by $1,000.

This work has three separate kinds of evidence:

1. **Independent policy tests** (`tests_policy/`), worked out by hand from §40.8–40.8.3
   and the README interface. They were written and run against COBOL *before* any Python
   existed.
2. **Python unit tests** (`tests_python/`) of the replacement's individual functions and
   boundaries.
3. **Executable comparison** of COBOL and Python on identical batches: the strict
   verifier plus a per-record side-by-side table.

The human reviewer should check four things. Is the hand-derived ledger a faithful
reading of the policy? Are the interface assumptions acceptable? Was every mismatch
explained? Is the Python code maintainable? Agreement between the two programs does not
prove Medicare correctness.

## Stage 1 execution (actual)

`make doctor` and `make build baseline generate test capture-baseline` both exited 0.
The log is in `evidence/live/stage1-baseline.log` and the capture is in
`evidence/live/cobol-baseline/`. The starter infrastructure tests also passed (17 of 17).
Every source, input and output SHA-256 in the new manifest matches
`docs/evidence/cobol-baseline/manifest.json` (`evidence/live/stage1-hash-check.txt`).
- Curated batch: 30 records, 12 PAID, 9 ZERO, 9 INVALID, 10,000,450,202 cents.
- Synthetic batch (seed 20261017): 1,000 records, 271 PAID, 729 ZERO, 0 INVALID,
  514,352,570,951 cents. These are observed COBOL behaviour, not a policy oracle.

## Program structure

| File | Program / paragraph | Role |
| --- | --- | --- |
| `cobol/copybooks/claim.cpy` | `claim-interface` | One shared record holding the raw 73-byte fields and the parsed values. It is passed *by reference* to both subprograms. |
| `cobol/batch.cob` | `msp-batch` / `main`, `finish-line`, `process-record`, `fatal-io` | CLI, byte-level framing, per-record reset, duplicate check, counts, totals, CSV output |
| `cobol/validate.cob` | `validate-claim` / `validate-record` | Rejection checks in a fixed order. It converts text to packed decimal only after the class tests. |
| `cobol/payment.cob` | `calculate-payment` / `calculate-prospective-payment` | Four-limit payment and zero-reason precedence |

## Inputs and outputs

Command: `msp-batch INPUT RESULTS TOTALS`. Any other argument count prints a usage
message and exits 2. Identical path strings exit 2 ("paths must be distinct").
`batch.cob` lines 47–61.

Input is fixed-width ASCII with no header. A well-formed record is **exactly 73 bytes**.

| Bytes | Field | `claim.cpy` |
| --- | --- | --- |
| 1–12 | claim ID, left-justified, space-padded | `raw-id pic x(12)` |
| 13–22 | covered charges C | `raw-charges pic x(10)` |
| 23–32 | gross Medicare payable G | `raw-gross` |
| 33–42 | primary payment P | `raw-primary` |
| 43–52 | deductible D | `raw-deductible` |
| 53–62 | coinsurance K | `raw-coinsurance` |
| 63–72 | contract (OTAF) A, or `----------` for absent | `raw-contract` |
| 73 | payment-in-full flag `Y`/`N` | `raw-full pic x` |

12 + 6×10 + 1 = 73. Each amount is ten unsigned digits of **cents**, from 0 to
9,999,999,999.

Results CSV: header `record_no,claim_id,status,payment_cents,reason`, then one row per
record. Totals CSV: header `records,paid,zero,invalid,payment_cents` and one row. The
COBOL `STRING` statement writes numeric items at their full PIC width, so the
output contains zero-padded fixed-width digit strings:
- record_no is 10 digits (`pic 9(10)`);
- payment is 10 digits (`payment-display pic 9(10)`);
- the counts are 10 digits each and the total is 15 digits (`pic 9(15)`).

Example: `0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE`. The ID, status and reason
are `function trim`-med.

## Exact cents

All parsed amounts are `pic 9(10) comp-3`, which is packed decimal. The intermediates
`deductions` and `reduction-amount` are `pic 9(11) comp-3`, so D + K ≤ 19,999,999,998
cannot overflow. The batch total is `pic 9(15)`; 10,000 × 9,999,999,999 fits. No
binary floating point is involved. A Python port must use `int` cents.

## Framing and the 4,096-byte / 10,000-record limits (`batch.cob` 62–124)

- The input is opened `organization sequential` with **1-byte records**, so the program
  frames lines itself. LF (`x"0A"`) ends a line. A single trailing CR (`x"0D"`) before
  LF is stripped (CRLF accepted). At EOF a non-empty partial line is still processed,
  so a missing final newline is fine. An empty file gives a zero-record batch, exit 0.
- A **blank physical line** (length 0) is still a record. It is not EOF. Its length is
  not 73, so it is `INVALID,BAD_LENGTH` with ID `@` + record number.
- Lines up to 4,096 bytes (after CR stripping) are records. Any line other than 73 bytes
  is `BAD_LENGTH`. A 4,097-byte line, or a byte that would overflow the 4,097-byte
  buffer, triggers `fatal-io`: a message on stderr, exit 2, and outputs discarded.
- The 10,001st record is fatal (`record-count >= 10000` is checked before increment).
  10,000 records is allowed.

## Validation precedence (`validate.cob` 10–59)

Each check sets the reason *first* and then `goback`s, so the first failure wins:

1. `BAD_LENGTH`: length ≠ 73.
2. `BAD_ID`: the ID is all spaces, or contains a character outside `A–Z 0–9 - _`, or
   has a non-space after a space (embedded space). Lower case is invalid.
3. `BAD_AMOUNT`: any of C, G, P, D, K is not `NUMERIC`, or the contract is neither the
   exact sentinel `----------` nor numeric. A malformed contract is therefore
   `BAD_AMOUNT`, **not** `BAD_CONTRACT`. `NUMERIC` on a `pic x` field means every byte is
   `0`–`9`. Signs, spaces, decimal points and partial sentinels fail.
4. `BAD_CONTRACT`: the contract is present and A > C. A = C and A = 0 are valid.
5. `BAD_FLAG`: the flag is not exactly `Y` or `N`.

Numeric `MOVE`s into COMP-3 happen only after step 3 succeeds (the comment at line 45).

## State reset and IDs (`batch.cob` 119–141)

For every record, `process-record` runs `initialize claim-interface`. That clears every
field: raw and parsed amounts become zero or spaces, the payment becomes 0, and
`claim-has-contract` becomes 0. A contract from an earlier record therefore cannot leak
into the next one, even after a rejection. The ID is pre-set to `@` + the 10-digit record
number (for example `@0000000003`). `validate-record` replaces it with the real ID only
after the ID check passes. Records rejected for `BAD_LENGTH` or `BAD_ID` keep the
provisional `@` ID. Records rejected later (`BAD_AMOUNT`, `BAD_CONTRACT`, `BAD_FLAG`)
carry their real ID.

**Duplicate IDs:** every non-`@` ID is checked against all earlier IDs. A repeat is
fatal, exit 2. This applies even when either occurrence was rejected for amount,
contract or flag. `@` IDs never collide because `@` is not a legal input character.

## Payment and zero-reason precedence (`payment.cob`)

Only VALID records reach `calculate-prospective-payment`. Let B = A if the contract is
present, otherwise C. Let T = D + K.

1. `full = Y` → ZERO, `PAYMENT_IN_FULL` (§40.8).
2. `payment-cap = min(G, B)`. If P ≥ cap → ZERO, `PRIMARY_AT_CAP`.
3. If T ≥ cap → ZERO, `DEDUCTIONS_AT_CAP`.
4. Otherwise payment = cap − max(T, P) → PAID, `SECONDARY_PAYABLE`.

Step 4 equals the lowest of the four §40.8.3 limits, G−P, G−T, B−P and B−T, because
min(G,B) − max(T,P) = min over those four differences. The zero branches run first so
that unsigned fields never go negative. An all-zero claim hits step 2 (0 ≥ 0) and gets
`PRIMARY_AT_CAP`.

**Totals:** PAID / ZERO / INVALID counters, plus `payment-total += claim-payment` for
every record. Invalid and zero records add 0.

**Fatal behaviour:** `fatal-io` covers usage, distinct paths, open/read/write/close
failures, oversized lines, more than 10,000 records and duplicate IDs. It prints a
diagnostic to stderr, sets return code 2 and runs `stop run`. Partial outputs may exist
and must be discarded by the caller.

## The `claim-has-contract` branch and why $13,000 is not "$12,500 accepted in full"

```cobol
move claim-charges to charge-basis          *> B = C
if claim-has-contract = 1
    move claim-contract to charge-basis     *> B = A (OTAF replaces charges, §40.8.2)
end-if
compute payment-cap = function min(claim-gross, charge-basis)
```

CMS-EX3: C = 1,500,000, G = 1,400,000, P = 1,250,000, D = 155,600, K = 0, A = 1,300,000,
full = N.
- B = 1,300,000 and cap = min(1,400,000, 1,300,000) = 1,300,000.
- P = 1,250,000 is below the cap, and T = 155,600 is below the cap.
- payment = 1,300,000 − max(155,600, 1,250,000) = **50,000 cents = $500**.

Without the contract branch, B = C = 1,500,000. The cap is then min(1,400,000, 1,500,000)
= 1,400,000, and the payment is 1,400,000 − 1,250,000 = $1,500.

Two different facts are involved here:
- **The $13,000 OTAF is a contractual total.** The provider must accept it from all
  payers combined, so Medicare treats it as the charges (§40.8.2, §40.8.3 Ex. 3).
- **The $12,500 primary payment was not accepted as payment in full** (`full=N`). If it
  had been (`full=Y`), §40.8 says Medicare pays nothing (`PAYMENT_IN_FULL`).

The OTAF lowers the cap. It does not make the primary payment "full". Medicare tops the
provider up to the $13,000 it agreed to accept, which is $500. The $1,556 deductible is
a historical example input, not a rate lookup.
