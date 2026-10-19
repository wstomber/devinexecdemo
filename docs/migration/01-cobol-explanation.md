# 01 — What the legacy COBOL does (Stage 1 explanation)

Starter commit `be0b00ec5a2369d50a34d351694b187ae2300fe4`. Read before any Python
existed. Line numbers refer to the starter sources. This is a synthetic educational
module built from public CMS rules, not CMS production code.

## Why this matters

A payment program can look right on ordinary claims and still owe the wrong amount
when a contractual exception applies. In the published CMS Example 3 (Pub. 100-05
Ch. 5 §40.8.3, PDF pp. 83–84) Medicare pays **$500**; if the provider's $13,000
obligated-to-accept amount (OTAF) were ignored the same claim would pay **$1,500**.
A migration has to keep that branch, the input validation around it, and the CWF
pre-payment check that decides whether the calculated money is actually released.

Evidence layers in this run, kept separate:
1. a hand-derived policy/interface ledger written before any Python (`tests_policy/`);
2. Python unit tests (`tests_python/`);
3. COBOL-vs-Python executable comparison on curated, seeded synthetic and edge batches.

What a reviewer should assess: the rule map (`02-rule-map.md`), that the ledger was
committed before `python/` (git history), the side-by-side outputs, and the limits below.

## Program structure

| File | Program | Job |
| --- | --- | --- |
| `cobol/batch.cob` | `msp-batch` (main) | arguments, CWF load, byte-level framing, per-record reset, duplicate IDs, counts/totals, CSV output, fatal exit |
| `cobol/validate.cob` | `validate-claim` | field validation in fixed precedence |
| `cobol/payment.cob` | `calculate-payment` | `calculate-prospective-payment`: the MSP formula |
| `cobol/cwf.cob` | `cwf-check` | entitlement → duplicate → MSP primary not billed |
| `cobol/copybooks/claim.cpy` | — | `claim-interface`: raw 92-byte record + parsed/packed fields + results |
| `cobol/copybooks/cwf.cpy` | — | `cwf-tables`: up to 1,000 `B` and 1,000 `H` entries |

The subprograms receive `claim-interface` (and `cwf-tables`) BY REFERENCE: they write
status, reason, payment and CWF fields directly into the caller's storage.

## Inputs and outputs

CLI: `msp-batch INPUT CWF OUTPUT TOTALS` (batch.cob 59–76). Exactly four arguments, else
`usage: …` on stderr and exit 2. Any two identical path *strings* → `paths must be
distinct`, exit 2 (aliases/symlinks are the caller's responsibility).

**Claim record — 92 bytes**, no header (claim.cpy 2–16):

| Bytes | Field | Rule |
| --- | --- | --- |
| 1–12 | claim ID | 1–12 of `A-Z 0-9 - _`, left-justified, space padded |
| 13–22 | covered charges C | 10 ASCII digits, cents |
| 23–32 | gross Medicare payable G | 10 digits |
| 33–42 | primary payment P | 10 digits |
| 43–52 | deductible D | 10 digits |
| 53–62 | coinsurance K | 10 digits |
| 63–72 | lower contractual acceptance A (OTAF) | 10 digits, or exactly `----------` = absent |
| 73 | full-payment flag | `Y` or `N` |
| 74–84 | MBI (synthetic) | 11 of `A-Z 0-9` |
| 85–92 | date of service | `YYYYMMDD`, all digits, month 01–12, day 01–31 (no calendar check: `20250631` is accepted) |

**CWF reference file** (line sequential, read in `load-cwf`/`parse-cwf`, batch.cob 189–240):

| Record | Bytes | Checked |
| --- | --- | --- |
| `B` beneficiary, 44 bytes | 2–12 MBI, 13–20 entitled from, 21–28 entitled to (`99999999` = open), 29–36/37–44 MSP period from/to or 16 dashes | 45–64 spaces; MBI not all spaces; 13–28 numeric; 29–44 all `-` or all numeric; ≤ 1,000 |
| `H` posted claim, 30 bytes | 2–12 MBI, 13–20 DOS, 21–30 charges | 31–64 spaces; MBI not all spaces; 13–30 numeric; ≤ 1,000 |

Anything else (blank line, other first byte) → `invalid CWF reference record`, exit 2.
Behaviour of the GnuCOBOL line-sequential reader observed on this VM (GnuCOBOL 3.1.2;
probes kept in `evidence/live/stage1-cwf-reader-probe.txt`): bytes after column 64
are ignored (record is `PIC X(64)`), CR bytes are dropped, short lines are space
padded, a missing final newline is fine, an empty file loads zero beneficiaries.
Dates are not calendar-validated in `B`/`H` records. The first `B` for an MBI wins.
The CWF file is loaded **before** the input is opened, so CWF errors win over input errors.

**Results CSV** header `record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents`;
`record_no`, `payment_cents`, `released_cents` print as 10-digit zero-padded numbers
(`PIC 9(10)` display fields, batch.cob 50, 33, 45). **Totals CSV** header
`records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents`; counts
10 digits, cent totals 15 digits (`PIC 9(15)`). Diagnostics go only to stderr.

## Exact cents

Amounts are moved from text into `PIC 9(10) COMP-3` (packed decimal) only after the
NUMERIC class test (validate.cob 82–97). All arithmetic is integer cents; there is no
rounding anywhere. `deductions` is `PIC 9(11)` so D+K of two maximums (19,999,999,998)
fits; totals are `PIC 9(15)`: 10,000 × 9,999,999,999 = 99,999,999,990,000 fits.

## Framing and limits (batch.cob 93–135)

The input is read **one byte at a time** (`record contains 1 characters`) so line
handling is explicit and not compiler-dependent:
- LF ends a line. At end of file, any pending bytes form a final line (missing final
  newline is fine; a file ending in a lone `\r` produces one extra blank record).
- One trailing CR is removed (CRLF accepted).
- A line longer than 4,096 bytes (after removing that CR) is fatal: `input line exceeds
  4096 bytes` (or the 4,097th stored byte, line 104, fatal immediately). 4,096 bytes is
  accepted and becomes one `BAD_LENGTH` record, never split.
- A blank line is a record (`BAD_LENGTH`), not end of file. An empty file is a valid
  zero-record batch.
- More than 10,000 records is fatal (`batch exceeds 10000 records`, line 137).

## Validation precedence (validate.cob 57–120)

First failure wins; status `INVALID`, payment 0:
1. `BAD_LENGTH` — length ≠ 92.
2. `BAD_ID` — ID all spaces, any byte outside `A-Z 0-9 - _`, or a non-space after a
   space (embedded/leading space). Lowercase and `@` fail.
3. `BAD_AMOUNT` — any of C, G, P, D, K not 10 ASCII digits, **or** a contract that is
   not exactly `----------` and not 10 digits (a malformed contract is BAD_AMOUNT, not
   BAD_CONTRACT). `NUMERIC` on `PIC X` accepts only bytes `0`–`9`: spaces, `+`, `.`, `_`,
   NUL and non-ASCII bytes fail.
4. `BAD_CONTRACT` — contract present and A > C (A = C and A = 0 are allowed).
5. `BAD_FLAG` — flag not exactly `Y`/`N`.
6. `BAD_MBI` — any of the 11 bytes outside `A-Z 0-9`.
7. `BAD_DATE` — not 8 digits, month outside 01–12 or day outside 01–31.

Validation happens before the payment-in-full test, so `full=Y` on a malformed record
is still INVALID.

## IDs, state reset and duplicates (batch.cob 136–158)

For each record: `INITIALIZE claim-interface` (all alphanumerics to spaces, numerics to
0 — including `claim-has-contract`), then the provisional ID `"@" + record-count`
(`@0000000021`) is placed in `claim-id`. `validate-claim` overwrites it with the real
ID once the ID passes (step 2). So BAD_LENGTH and BAD_ID records keep the `@` ID; all
later rejections carry their real ID. Every record whose ID passed is checked against
all earlier IDs: a duplicate is fatal (`duplicate claim ID`, exit 2) **even if the record
is otherwise rejected**. `@` IDs are never checked (and can't collide).

The reset matters: a rejected record may have parsed a contract before failing the flag
check; without the reset the next record would inherit `claim-has-contract = 1`.

## The payment: `calculate-prospective-payment` (payment.cob 12–38)

```
payment = 0; status = ZERO
if full = Y                          -> PAYMENT_IN_FULL
charge-basis = C; if claim-has-contract: charge-basis = A     (lines 20–23)
payment-cap  = min(G, charge-basis)                           (line 24)
if P >= payment-cap                  -> PRIMARY_AT_CAP
deductions = D + K
if deductions >= payment-cap         -> DEDUCTIONS_AT_CAP
payment = payment-cap - max(deductions, P); PAID / SECONDARY_PAYABLE
```

This equals the four §40.8.2 limits — min(G−P, G−T, B−P, B−T) with T = D+K and
B = A or C — because min over the four is min(G,B) − max(T,P). The zero branches are
checked before subtraction so an unsigned field never goes negative, and they fix
the reason precedence: payment in full, then primary at cap, then deductions at cap.
An all-zero claim is `PRIMARY_AT_CAP` (0 ≥ 0). A PAID result is always ≥ 1 cent.

### Why $13,000 OTAF is not "$12,500 accepted in full"

CMS-EX3: C = $15,000, G = $14,000, P = $12,500, D = $1,556 (historical example input),
K = 0, A = $13,000, `full=N`. The OTAF is the *total* the hospital must accept from all
payers; §40.8.3 says Medicare treats it as the charges. So `charge-basis` = $13,000,
`payment-cap` = min($14,000, $13,000) = $13,000, and the payment is
$13,000 − max($1,556, $12,500) = **$500** — the provider receives $12,500 + $500 = $13,000.
`full=Y` would mean the primary's $12,500 itself was accepted as payment in full,
which pays $0. Without the contract branch the cap is $14,000 and the payment $1,500.

## The CWF check: `cwf-check` (cwf.cob)

Called only for claims whose status is PAID or ZERO (batch.cob 159–167): an invalid
claim has no trustworthy MBI/date/amounts, so it is `NOT_SENT` / `CLAIM_INVALID`.
**ZERO claims are still sent** (they are valid claims; CWF may still reject them).
Order, first failure wins (status `REJECTED`):
1. `NOT_ENTITLED` — no `B` record with this MBI, or DOS < entitled-from or > entitled-to
   (both ends inclusive).
2. `DUPLICATE` — an `H` record with the same MBI, DOS and charges (exact cents). Only
   history is searched — two claims in the same batch never duplicate each other here.
3. `MSP_PRIMARY_NOT_BILLED` — the beneficiary has an MSP period that covers the DOS
   (inclusive) and P = 0.
Otherwise `ACCEPTED` / `DISPOSITION_01`.

**Calculated vs released:** `payment_cents` is always the calculated amount (kept for
review even when CWF rejects); `released_cents` = payment if ACCEPTED, else 0. Totals
count accepted/rejected (NOT_SENT counts as neither) and sum both amounts.
CMS-EX3 is filed for an MBI whose MSP period covers the DOS with a $12,500 primary
payment, so it passes all three checks and $500 is released.

## Fatal behaviour (batch.cob 263–267)

`fatal-io` prints `fatal batch failure; discard outputs; file status …` to stderr and
`STOP RUN` with exit 2. Triggers: usage, identical paths, CWF open/parse/limit, input
or output open/write/close errors, line > 4,096 bytes, > 10,000 records, duplicate ID.
Partially written results may remain on disk; callers must discard them. Exit 0 means
the batch ran, even if every record is INVALID.

## Limits of this explanation

Coverage, gross pricing, primary allocation and deductible/coinsurance are upstream
inputs. Reason codes, file layouts and CWF reject codes are demo-defined, not CMS codes.
CWF here is three checks on synthetic reference data, not the CWF system.
