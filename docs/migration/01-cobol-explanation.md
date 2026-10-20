# 01 — What the legacy COBOL does (explained for engineers who do not read COBOL)

Synthetic educational example derived from public CMS rules; not CMS production
code. Source files: `cobol/batch.cob` (driver), `cobol/validate.cob`,
`cobol/payment.cob`, `cobol/cwf.cob`, copybooks `cobol/copybooks/claim.cpy` and
`cobol/copybooks/cwf.cpy`. Starter commit `be0b00ec5a2369d50a34d351694b187ae2300fe4`.
Observed with GnuCOBOL 3.1.2.0 on Ubuntu 22.04 (`evidence/live/stage1-baseline.log`).

## 1. The business problem in one paragraph

Another insurer (the *primary* payer) has already paid part of a hospital claim.
Medicare, as *secondary* payer, must pay the lowest of four limits (Pub. 100-05
Ch. 5 §40.8.2–40.8.3), and pays nothing when the primary payment was accepted as
payment in full. Getting one branch wrong changes money owed: in CMS Example 3
the correct secondary payment is **$500**; ignoring the provider's $13,000
contractual acceptance amount would pay **$1,500**. After the payment is
calculated, a small synthetic slice of the Common Working File (CWF) pre-payment
check decides whether the calculated payment is actually released.

## 2. Inputs and outputs

```
build/msp-batch INPUT.dat CWF.dat RESULTS.csv TOTALS.csv
```

Exactly four positional arguments, else `usage: msp-batch INPUT CWF OUTPUT TOTALS`
on stderr and exit 2. The four path strings must be pairwise different
(`batch.cob` lines 69–76); identical strings → "paths must be distinct", exit 2.
Aliases (symlinks, `./x` vs `x`) are *not* detected; callers must avoid them.

### 2.1 The 92-byte claim record (`claim.cpy`, `claim-raw`)

| Bytes (1-based) | Field | COBOL name | Rule |
| --- | --- | --- | --- |
| 1–12 | Claim ID | `raw-id` | 1–12 of `A-Z 0-9 - _`, then only trailing spaces |
| 13–22 | Covered charges | `raw-charges` | 10 ASCII digits, integer cents |
| 23–32 | Gross Medicare payable (before deductible/coinsurance) | `raw-gross` | 10 digits |
| 33–42 | Primary payment | `raw-primary` | 10 digits |
| 43–52 | Applicable deductible | `raw-deductible` | 10 digits |
| 53–62 | Applicable coinsurance | `raw-coinsurance` | 10 digits |
| 63–72 | Lower contractual acceptance amount (OTAF) | `raw-contract` | 10 digits, or exactly `----------` = absent |
| 73 | Primary accepted as payment in full | `raw-full` | `Y` or `N` |
| 74–84 | Synthetic MBI | `raw-mbi` | 11 of `A-Z 0-9` |
| 85–92 | Date of service | `raw-dos` | 8 digits `YYYYMMDD`, month 01–12, day 01–31 |

No header, no sequence number in the record (the driver numbers records 1, 2, 3…).
Dates are only *range*-checked: `20250231` is accepted (no calendar check), and
year `0000` is accepted.

### 2.2 The CWF reference file (`cwf.cpy`, `load-cwf`/`parse-cwf` in `batch.cob` 189–237)

Line-sequential ASCII, loaded fully into memory **before** the claims file is opened.

| Record | Layout (1-based) | Checks that make it fatal (exit 2) |
| --- | --- | --- |
| `B` beneficiary, 44 bytes | 1 `B`; 2–12 MBI; 13–20 entitled from; 21–28 entitled to (`99999999` = open); 29–36 MSP from; 37–44 MSP to (both 16 bytes `-` if none) | bytes 45–64 not blank; MBI all blank; bytes 13–28 not all digits; bytes 29–44 neither all `-` nor all digits; more than 1,000 `B` records |
| `H` posted claim history, 30 bytes | 1 `H`; 2–12 MBI; 13–20 date of service; 21–30 charges in cents | bytes 31–64 not blank; MBI all blank; bytes 13–30 not all digits; more than 1,000 `H` records |
| anything else | — | any other first byte (including a blank line) is fatal |

Observed with GnuCOBOL 3.1.2: a CWF file with CRLF line endings or without a final
newline loads normally; a blank line is fatal. A missing CWF file is fatal (file status not `00`). An *empty* CWF file is legal:
then nobody is on file and every valid claim is `NOT_ENTITLED`. If an MBI appears
in several `B` records, the first one wins (the search stops at the first match).

### 2.3 Outputs

Results CSV, header exactly
`record_no,claim_id,status,payment_cents,reason,cwf,cwf_reason,released_cents`, then
one row per input record. Totals CSV, header
`records,paid,zero,invalid,payment_cents,accepted,rejected,released_cents` and one row.

The COBOL builds rows with `STRING` from `PIC 9(n)` display fields, so numbers are
**zero-padded to fixed width**: `record_no`, `payment_cents`, `released_cents` and the
count columns are 10 digits; the two money totals are 15 digits. Example (observed):

```
0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000
0000000033,0000000015,0000000009,0000000009,000010001694602,0000000021,0000000003,000010000450202
```

IDs, statuses and reasons are trimmed (`FUNCTION TRIM`). Lines end in LF.

## 3. Exact cents and limits

* Every amount is an unsigned integer number of cents, 0–9,999,999,999 ($99,999,999.99).
  The text digits are checked with the COBOL `NUMERIC` class test **before** any
  numeric `MOVE`, then moved into `PIC 9(10) COMP-3` packed decimals. There is no
  floating point anywhere.
* `deductions = deductible + coinsurance` is `PIC 9(11)`, so two maximum values
  (19,999,999,998) cannot overflow.
* The payment is always `min(G, B) - max(T, P)` with both terms below the cap,
  so it fits in 10 digits.
* Batch totals are `PIC 9(15)`: 10,000 × 9,999,999,999 = 99,999,999,990,000 fits.

## 4. Record framing (`batch.cob` lines 77–135)

The claims file is read **one byte at a time** (`record contains 1 characters`),
so framing is explicit and does not depend on the GnuCOBOL version:

* LF (`x"0A"`) ends a line. If the line's last byte is CR (`x"0D"`), exactly one CR
  is removed, so CRLF files work.
* At end of file, a non-empty unterminated last line is still processed (missing
  final newline is fine). An empty file is a successful zero-record batch.
* A blank physical line (`\n` or `\r\n`) is a record of length 0 → `INVALID`,
  `BAD_LENGTH`. It is *not* end of file.
* The buffer is 4,097 bytes. Up to 4,096 bytes (after removing the CR) is a
  record; if it is not exactly 92 bytes it is `BAD_LENGTH` and processing
  continues. A line longer than 4,096 bytes is fatal (exit 2) — it is never split
  into several records.
* The 10,001st record (of any validity) is fatal: "batch exceeds 10000 records".

## 5. Per-record processing (`process-record`, lines 136–188)

1. `add 1 to record-count`.
2. **State reset:** `INITIALIZE claim-interface` sets every alphanumeric field to
   spaces and every numeric field to zero — including `claim-has-contract`,
   `claim-contract`, `claim-payment`, `claim-released`. Nothing from the previous
   (possibly rejected) record can leak into this one.
3. `claim-id` is set to the **provisional ID** `@` followed by the 10-digit record
   number (e.g. `@0000000021`). `@` can never appear in a valid ID.
4. The first 92 bytes of the line are copied over `claim-raw` (short lines are
   space padded) and the true length goes into `claim-length`.
5. `CALL "validate-claim"` (see §6). It replaces the provisional ID with the real
   one only once the ID itself has passed.
6. **Duplicate IDs:** if the ID no longer starts with `@` it is compared with every
   ID seen earlier in the batch. A repeat is fatal (exit 2) — **even when this
   record or the earlier one was rejected later in validation** (e.g. `BAD_AMOUNT`).
   Records rejected for `BAD_LENGTH`/`BAD_ID` keep their unique `@` ID and are not
   checked.
7. If valid, `CALL "calculate-payment"` (§7).
8. If `PAID` or `ZERO`, `CALL "cwf-check"` (§8); otherwise CWF is `NOT_SENT` /
   `CLAIM_INVALID` and released is zero.
9. Counters and totals are updated, and the CSV row is written.

## 6. Validation and its precedence (`validate.cob`)

The paragraph starts by assuming failure: status `INVALID` and reason
`BAD_LENGTH`. It then changes the reason *before* each test and `GOBACK`s (returns)
on the first failure, so **the first failing check wins**:

| Order | Reason | Fails when |
| --- | --- | --- |
| 1 | `BAD_LENGTH` | length ≠ 92 |
| 2 | `BAD_ID` | ID all spaces; a character other than `A-Z 0-9 - _`; a non-space after a space (leading or embedded space) |
| 3 | `BAD_AMOUNT` | any of the five required amounts not all ASCII digits; **or** the contract is neither `----------` nor 10 digits |
| 4 | `BAD_CONTRACT` | contract present and greater than charges (equal is allowed; zero is allowed) |
| 5 | `BAD_FLAG` | flag is not exactly `Y` or `N` |
| 6 | `BAD_MBI` | any of the 11 bytes not `A-Z`/`0-9` |
| 7 | `BAD_DATE` | not 8 digits, month outside `01`–`12`, or day outside `01`–`31` |

Note that a malformed contract amount (e.g. `-000000001`, `12345.6789`, all spaces)
is `BAD_AMOUNT`, **not** `BAD_CONTRACT`; `BAD_CONTRACT` is only the range rule.
Validation always runs before any payment logic, so a malformed record with
`full=Y` is still `INVALID`, never `PAYMENT_IN_FULL`.

## 7. The payment rule (`payment.cob`, paragraph `calculate-prospective-payment`)

```cobol
move 0 to claim-payment
move "ZERO" to claim-status
if raw-full = "Y"  ->  PAYMENT_IN_FULL, return             (zero reason 1)
move claim-charges to charge-basis
if claim-has-contract = 1
    move claim-contract to charge-basis                       (OTAF replaces charges)
compute payment-cap = function min(claim-gross, charge-basis)
if claim-primary >= payment-cap -> PRIMARY_AT_CAP, return  (zero reason 2)
compute deductions = claim-deductible + claim-coinsurance
if deductions >= payment-cap    -> DEDUCTIONS_AT_CAP, return (zero reason 3)
compute reduction-amount = function max(deductions, claim-primary)
compute claim-payment = payment-cap - reduction-amount
PAID / SECONDARY_PAYABLE
```

This is the four §40.8.2 limits — G−P, G−T, B−P, B−T (B = charge basis, T =
deductible + coinsurance) — simplified to `min(G,B) − max(T,P)`. The zero branches
run before the subtraction, so the unsigned packed fields never go negative, and
they fix the **zero-reason precedence**: payment in full, then primary at/above
the cap, then deductions at/above the cap. An all-zero claim is
`PRIMARY_AT_CAP` (0 ≥ 0). Any `PAID` result is at least 1 cent.

### 7.1 The `claim-has-contract` branch and `min(claim-gross, charge-basis)`

`claim-has-contract` is set to 1 by `validate.cob` only when bytes 63–72 are
digits (an explicit `0000000000` counts as present and yields a zero cap). When
it is 1, the contractual acceptance amount *replaces* covered charges as
`charge-basis`; it is not subtracted from anything. Then the cap is the smaller
of gross Medicare payable and that basis.

### 7.2 Why the $13,000 OTAF is not "the $12,500 primary accepted in full"

CMS Example 3: charges $15,000, gross $14,000, primary $12,500, deductible $1,556
(historical input), coinsurance $0, OTAF $13,000, `full=N`.

* The $13,000 is the **total** the provider is obligated to accept from all payers.
  Medicare treats it as the hospital's charges. `charge-basis` = 1,300,000 cents.
* "Primary accepted as payment in full" (`full=Y`) would mean the provider accepted
  the $12,500 itself as the full payment — then Medicare pays $0. That is not this
  case: the provider can still collect $13,000 − $12,500 = $500 more.
* cap = min(1,400,000, 1,300,000) = 1,300,000; T = 155,600; P = 1,250,000;
  payment = 1,300,000 − max(155,600, 1,250,000) = **50,000 cents ($500)**.
* Without the OTAF the cap would be min(1,400,000, 1,500,000) = 1,400,000 and the
  payment 150,000 cents ($1,500) — $1,000 too much.

## 8. The CWF pre-payment check (`cobol/cwf.cob`, paragraph `check-claim`)

CMS Pub. 100-04 Ch. 27 §20 describes the order of work: the contractor prices the
claim, then the CWF Host validates it, and payment is released only if CWF accepts.
That is why `batch.cob` calls `cwf-check` **after** `calculate-payment`, and only
for claims whose status is `PAID` or `ZERO`. Invalid claims cannot be priced and
are not sent (`NOT_SENT` / `CLAIM_INVALID`). **ZERO claims are still sent** — a
zero calculated payment is a valid priced claim.

`check-claim` starts with `released = 0`, `REJECTED`, `NOT_ENTITLED`, and returns at
the first failure:

1. **Entitlement** — find the first `B` record with the same MBI. Not found →
   `NOT_ENTITLED`. Found but `dos < entitled_from` or `dos > entitled_to` →
   `NOT_ENTITLED`. Both ends are inclusive.
2. **Duplicate** — reason becomes `DUPLICATE` if any `H` history record has the same
   MBI, the same date of service and the same charges (covered charges, bytes
   13–22, compared as numbers). Matching is against **posted history only**, not
   against other claims in this batch. One cent or one day different is not a
   duplicate.
3. **MSP primary not billed** — reason becomes `MSP_PRIMARY_NOT_BILLED` if the
   beneficiary has an MSP period, `msp_from ≤ dos ≤ msp_to` (inclusive), and the
   claim's primary payment is exactly 0. (Pub. 100-05 Ch. 5 §10.1: CWF holds the
   MSP file that says when another insurer pays first.)
4. Otherwise `ACCEPTED` / `DISPOSITION_01` and `released = payment`.

**Calculated vs released.** A CWF rejection does not change the calculation:
`payment_cents` keeps the calculated amount and status `PAID` stays `PAID`; only
`released_cents` is 0. Totals carry both: `payment_cents` sums calculated amounts,
`released_cents` sums released amounts; `accepted`/`rejected` count CWF decisions
(`NOT_SENT` is in neither).

## 9. Totals and fatal behaviour

`records = paid + zero + invalid` and `accepted + rejected = paid + zero`.
Fatal conditions — usage error, identical paths, missing/unreadable CWF file,
malformed CWF record, too many `B`/`H` records, missing input file, unwritable
output, a line over 4,096 bytes, the 10,001st record, a duplicate identifiable ID —
go through `fatal-io`: a diagnostic on stderr, `return-code 2`, `STOP RUN`.
Output files may be partially written and must be discarded. Exit 0 means the
batch ran, even if every record was invalid; there are no other exit codes.

## 10. Observed baseline

Curated batch (33 records): 15 PAID, 9 ZERO, 9 INVALID; 10,001,694,602 cents
calculated; CWF 21 accepted, 3 rejected; 10,000,450,202 cents released. Seeded
synthetic batch (1,000): 271/729/0, 485,289,809,347 calculated, 736/264,
344,091,123,732 released. All eight retained file hashes and all source hashes
match `docs/evidence/cobol-baseline/manifest.json`
(`evidence/live/stage1-hash-check.txt`). This is observed COBOL behaviour, not a
payment oracle.
