# 04 — Line-by-line legacy walkthrough

Line numbers are from the starter commit `be0b00e` (unchanged in this branch).

## `batch.cob` — the driver

| Lines | What happens |
|---|---|
| 1–13 | Four files. `claims-file` is byte-sequential (1-byte records); `cwf-file`, `results-file`, `totals-file` are line sequential. |
| 15–23 | Record buffers: CWF 64 bytes, results 160, totals 180. |
| 24–56 | Working storage: paths (1,024 bytes), counters `pic 9(10)`, totals `pic 9(15)`, the 4,097-byte line buffer, a 10,000-entry seen-ID table; copybooks `claim.cpy`, `cwf.cpy`. |
| 58–64 | Exactly four arguments or `usage:` message, exit 2. |
| 65–76 | Read paths; any two equal → `paths must be distinct`, exit 2. |
| 79–80 | Disable line-sequential NUL/validation handling. |
| 81 | `perform load-cwf` — reference data is loaded and validated before the claims file is opened. |
| 82–90 | Open input, results, totals; each failure → `fatal-io`. |
| 91–92 | Write the CSV header. |
| 93–109 | Byte loop. Status `10` (EOF): a pending partial line is finished. LF → `finish-line`. Any other byte is appended; a 4,098th byte is fatal before an LF is seen. |
| 110–121 | Write totals header and the single totals line (fixed-width numbers), close, exit 0. |
| 122–135 | `finish-line`: drop one trailing CR; >4,096 bytes → fatal; `process-record`; reset buffer. |
| 136–140 | 10,001st record → fatal. |
| 141–147 | Count the record, `initialize` all claim state, provisional ID `@`+10 digits, copy the first 92 bytes and the true length. |
| 148 | `call "validate-claim"`. |
| 149–158 | If the ID became real (does not start with `@`), check it against all previous IDs — fatal on repeat, even when the record was later rejected. |
| 159–161 | Only `VALID` claims are priced. |
| 162–166 | Only priced claims (`PAID`/`ZERO`) go to `cwf-check`; others get `NOT_SENT`/`CLAIM_INVALID`. |
| 167–181 | Accumulate ACCEPTED/REJECTED, released, PAID/ZERO/INVALID, payment totals. |
| 182–188 | Build and write the result line. |
| 189–205 | `load-cwf`: open (missing file → fatal), read each line; read errors → `bad-cwf`. |
| 206–237 | `parse-cwf`: `B` = MBI 2–12, entitlement 13–28 (numeric), MSP 29–44 (`-`×16 or numeric), 45–64 spaces, ≤1,000; `H` = MBI 2–12, DOS 13–20, charges 21–30 (numeric), 31–64 spaces, ≤1,000; anything else fatal. |
| 238–262 | `bad-cwf`, write helpers, close helpers. |
| 263–267 | `fatal-io`: message with file statuses, return code 2, `stop run`. |

## `validate.cob` — `validate-record`

| Lines | Check (first failure wins; `claim-reason` is set *before* each test) |
|---|---|
| 11–13 | Status `INVALID`; length ≠ 92 → `BAD_LENGTH`. |
| 14–32 | All spaces, or a character outside `A-Z 0-9 - _`, or a non-space after a space → `BAD_ID`. |
| 33 | ID accepted: from here on the record reports its real ID. |
| 34–44 | Five amounts and (unless `----------`) the contract must be `NUMERIC` → `BAD_AMOUNT`. |
| 46–50 | Only now convert text to packed numbers (the comment at 45 explains why). |
| 51–55 | Contract > charges → `BAD_CONTRACT`. |
| 56–57 | Flag not `Y`/`N` → `BAD_FLAG`. |
| 58–64 | Any MBI byte not `A-Z`/`0-9` → `BAD_MBI`. |
| 65–68 | Date not numeric, month outside 01–12, day outside 01–31 → `BAD_DATE`. |
| 69–72 | Store MBI/DOS, status `VALID`, reason blank. |

## `payment.cob` — `calculate-prospective-payment`

| Lines | Step |
|---|---|
| 13–14 | Default: payment 0, status `ZERO`. |
| 16–19 | Full flag `Y` → `PAYMENT_IN_FULL`. |
| 20–23 | Basis B = charges, or the contract when present. |
| 24 | Cap = `min(gross, B)`. |
| 25–28 | Primary ≥ cap → `PRIMARY_AT_CAP`. |
| 29–33 | T = deductible + coinsurance; T ≥ cap → `DEDUCTIONS_AT_CAP`. |
| 34–37 | Payment = cap − `max(T, primary)`; `PAID`, `SECONDARY_PAYABLE`. |

## `cwf.cob` — `check-claim`

| Lines | Step |
|---|---|
| 18–20 | Default: released 0, `REJECTED`, `NOT_ENTITLED`. |
| 21–28 | Find the first `B` record with this MBI; none → return. |
| 29–32 | DOS outside the inclusive entitlement period → return (`NOT_ENTITLED`). |
| 33–41 | Reason `DUPLICATE`; any `H` with the same MBI, DOS and charges → return. |
| 42–48 | Reason `MSP_PRIMARY_NOT_BILLED`; MSP period present, DOS inside it (inclusive) and primary 0 → return. |
| 49–51 | `ACCEPTED`, `DISPOSITION_01`, released = calculated payment. |

<a id="cms-ex3-traced"></a>
## CMS-EX3 traced

Curated record 2 (and ledger case `CMS-EX3`). Values in cents.

Input: ID `CMS-EX3`, charges 1,500,000, gross 1,400,000, primary 1,250,000,
deductible 155,600, coinsurance 0, contract 1,300,000, full `N`; the ledger
uses MBI `7MSPEGHP001`, DOS 20250415 against its own CWF data.

1. `batch.cob` 141–148: record 2, length 92, provisional `@0000000002`, validate.
2. `validate.cob`: length 92; ID valid → `claim-id` = `CMS-EX3`; amounts and
   contract numeric → `claim-has-contract` = 1; 1,300,000 ≤ 1,500,000; flag
   `N`; MBI and date valid → `VALID`.
3. `batch.cob` 149–158: first time this ID is seen.
4. `payment.cob`:
   - 16: full = `N`, continue.
   - 20–23: B = 1,300,000 (the OTAF replaces 1,500,000).
   - 24: cap = min(1,400,000, 1,300,000) = **1,300,000**.
   - 25: 1,250,000 ≥ 1,300,000? No.
   - 29–30: T = 155,600 + 0 = 155,600 ≥ 1,300,000? No.
   - 34: reduction = max(155,600, 1,250,000) = 1,250,000.
   - 35: payment = 1,300,000 − 1,250,000 = **50,000** ($500). `PAID`.
   - Without the contract, line 24 would give cap 1,400,000 and payment 150,000 ($1,500) — ledger case `EX3-NO-OTAF`.
5. `cwf.cob` (ledger reference record `B7MSPEGHP00120200101999999992025030120250630`):
   - 21–28: MBI found.
   - 29–32: 20250415 within 20200101–99999999.
   - 33–41: no `H` record for this MBI.
   - 42–48: MSP period 20250301–20250630 covers the DOS, but primary 1,250,000 ≠ 0 → not rejected.
   - 49–51: `ACCEPTED`, `DISPOSITION_01`, released **50,000**.
6. `batch.cob` 182–188 writes
   `0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000`
   — the same line in `evidence/live/comparison/curated/cobol-results.csv` and
   `python-results.csv`.

The $13,000 is the provider's total obligation to accept from the primary
payer (OTAF). The $12,500 actually paid is less than that, so it is **not**
"payment in full"; the $500 gap is what Medicare pays as secondary.
