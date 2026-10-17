# 01 — What the legacy COBOL does (Stage 1 explanation)

Live run, Devin session https://app.devin.ai/sessions/7909f87127ea43d3af55ee357ca75c3c,
starting from `demo/starter-37ceca1` = `37ceca17f110536d55261d5d19aa187781dd8851`.
This is a **synthetic educational** MSP payment module built from public CMS rules
(Pub. 100-05 Ch. 5 §§40.8–40.8.3). It is not CMS production code. Reason codes,
file layouts, limits and exit codes are demo interface decisions, not CMS policy.

Everything below was read from `cobol/*.cob` / `cobol/copybooks/claim.cpy` at the
starter commit and checked against an actual run (`evidence/live/stage1-baseline.log`,
`evidence/live/baseline/`, hashes in `evidence/live/stage1-hash-check.txt`: every
input/output hash matches `docs/evidence/cobol-baseline/manifest.json`).

## Why this matters (customer problem)

A payment module like this decides how many dollars Medicare pays after another
insurer has paid. A migration that "works on ordinary claims" can still quietly
change money owed on the contractual-cap path. In CMS §40.8.3 Example 3 the right
answer is **$500**; a translation that forgets the contractual (OTAF) limit pays
**$1,500** — a $1,000 overstatement on one claim. The reviewer must be able to see,
for that case and every other rule, *policy → COBOL → test → Python → result*.

## Program structure

| File | Role |
| --- | --- |
| `batch.cob` (`msp-batch`) | CLI, byte-level framing, per-record reset, provisional IDs, duplicate check, dispatch, counts, totals, fatal exit |
| `validate.cob` (`validate-claim`) | Length, ID, numeric-class, contract range, flag — sets `claim-status`/`claim-reason` |
| `payment.cob` (`calculate-payment`) | Paragraph `calculate-prospective-payment`: zero reasons and the four-limit formula |
| `copybooks/claim.cpy` | `claim-interface` record shared by all three programs (passed BY REFERENCE) |

## Inputs and outputs

CLI: `msp-batch INPUT OUTPUT TOTALS` (batch.cob 47–61). Anything other than exactly
three arguments prints `usage: ...` to stderr and returns **2**. Identical path
strings (input = output, input = totals, output = totals) print
`paths must be distinct` and return **2** (string comparison only, no alias resolution).
Files are opened input, output, totals in that order; any non-`00` file status runs
`fatal-io` (exit 2) — so a missing input file never creates the outputs.

### The 73-byte record (claim.cpy `claim-raw`)

| Bytes (1-based) | Width | Field | Accepted form |
| --- | ---: | --- | --- |
| 1–12 | 12 | `raw-id` | 1–12 of `A-Z 0-9 - _`, left-justified, right-padded with spaces |
| 13–22 | 10 | `raw-charges` | 10 ASCII digits = integer cents |
| 23–32 | 10 | `raw-gross` | 10 digits |
| 33–42 | 10 | `raw-primary` | 10 digits |
| 43–52 | 10 | `raw-deductible` | 10 digits |
| 53–62 | 10 | `raw-coinsurance` | 10 digits |
| 63–72 | 10 | `raw-contract` | 10 digits, or exactly `----------` = absent |
| 73 | 1 | `raw-full` | `Y` or `N` |

### Outputs

Results CSV (written via LINE SEQUENTIAL, LF line endings, trailing spaces trimmed):

```
record_no,claim_id,status,payment_cents,reason
0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE
```

`record_no` and `payment_cents` are always **10 zero-padded digits** (`pic 9(10)`
moved into a `STRING`). `claim_id`, status and reason are `function trim`med.
Totals CSV: header `records,paid,zero,invalid,payment_cents` then one row
with four 10-digit counts and a **15-digit** total, e.g.
`0000000030,0000000012,0000000009,0000000009,000010000450202`.

## Exact cents

Every amount is an unsigned integer number of cents: `pic 9(10) comp-3` (packed
decimal — exact base-10, no binary floating point). Max per field 9,999,999,999
cents ($99,999,999.99). `deductions` and `reduction-amount` are `pic 9(11)` so
deductible + coinsurance (max 19,999,999,998) cannot overflow. `payment-total`
is `pic 9(15)`; 10,000 × 9,999,999,999 = 99,999,999,990,000 fits. There is no
rounding anywhere: only `min`, `max`, `+` and `-` on integers.

## Framing and the transport limits (batch.cob 62–118)

- The input file is read **one byte at a time** (`record contains 1 characters`,
  `organization sequential`). Only `x"0A"` (LF) ends a line.
- Bytes are appended to `input-record pic x(4097)`. If 4,097 bytes are already
  held and another non-LF byte arrives → `fatal-io` (line 88).
- `finish-line`: if the last held byte is `x"0D"` (CR) it is dropped — so CRLF
  works and only **one** trailing CR is removed. If the remaining length > 4,096 →
  `input line exceeds 4096 bytes`, exit 2. So 4,096 bytes (+ optional CR) is the
  longest legal line; 4,097 content bytes is fatal.
- At end of file (status `10`) a pending partial line is processed if its byte
  count was > 0 — a missing final newline still yields the last record. A file
  ending in a lone `\r` after the last LF therefore yields one extra empty record.
- An **empty file** has no records: header-only results, totals all zeros, exit 0.
- A **blank line** is a record of length 0 → `INVALID/BAD_LENGTH`, not EOF.
- Record limit (`process-record` line 120): before the 10,001st record is counted,
  `batch exceeds 10000 records`, exit 2. Exactly 10,000 records is fine.

Every fatal path goes through `fatal-io`: message on stderr, return code 2,
`stop run`. Partially written outputs may exist and must be discarded by the caller.

## Per-record state reset and IDs (batch.cob 119–157)

For each record: `add 1 to record-count`, then **`initialize claim-interface`**
(alphanumerics to spaces, numerics — including `claim-has-contract` and every
parsed amount — to zero). So nothing from a previous (possibly rejected) record
leaks into the next one. Then `claim-id` is set to the provisional identity
`"@" + record-count` → `@0000000001` (record-count is `pic 9(10)`).

`validate-claim` overwrites `claim-id` with `raw-id` only once the ID check has
passed. So BAD_LENGTH and BAD_ID rows show `@` + 10 digits; every later rejection
(BAD_AMOUNT, BAD_CONTRACT, BAD_FLAG) shows the real claim ID.

**Duplicate IDs**: any record whose `claim-id` does not start with `@` is compared
with all previously seen IDs (linear table of up to 10,000). A repeat — even when
either occurrence was rejected for BAD_AMOUNT/BAD_CONTRACT/BAD_FLAG — is fatal
(`duplicate claim ID`, exit 2). `@` IDs are never checked; `@` cannot appear in a
valid input ID.

## Validation precedence (validate.cob `validate-record`)

The first failing check wins; the reason is pre-loaded before each check, and
`goback` returns with it:

1. `claim-length not = 73` → **BAD_LENGTH** (line 13). Length is after CR removal.
2. **BAD_ID** (14–32): all-spaces ID; or any byte outside `A-Z`, `0-9`, `-`, `_`;
   or a non-space after a space (embedded/leading space). Lowercase is rejected.
3. **BAD_AMOUNT** (34–44): any of the five required amounts `is not numeric`
   (every byte must be `0`–`9`: spaces, signs, `.`, letters all fail); or contract
   neither `----------` nor numeric. **A malformed contract is BAD_AMOUNT, not
   BAD_CONTRACT.** No numeric MOVE happens before these class tests (line 45 comment).
4. **BAD_CONTRACT** (51–55): contract present and `> claim-charges`. Contract equal to
   charges, and contract `0000000000`, are valid.
5. **BAD_FLAG** (56–57): `raw-full` not exactly `Y` or `N`.

Otherwise `claim-status = "VALID"` and `calculate-payment` is called. Note that the
flag is checked *after* contract range, and `full=Y` is only honoured after all
validation — an invalid record is never `PAYMENT_IN_FULL`.

## The payment paragraph (payment.cob `calculate-prospective-payment`, lines 12–38)

```cobol
move 0 to claim-payment
move "ZERO" to claim-status
if raw-full = "Y"                         *> 1. payment in full
    move "PAYMENT_IN_FULL" to claim-reason
    goback
end-if
move claim-charges to charge-basis        *> 2. basis = covered charges ...
if claim-has-contract = 1
    move claim-contract to charge-basis   *>    ... or the OTAF, if supplied
end-if
compute payment-cap = function min(claim-gross, charge-basis)
if claim-primary >= payment-cap           *> 3. primary reaches cap
    move "PRIMARY_AT_CAP" to claim-reason
    goback
end-if
compute deductions = claim-deductible + claim-coinsurance
if deductions >= payment-cap              *> 4. deductions reach cap
    move "DEDUCTIONS_AT_CAP" to claim-reason
    goback
end-if
compute reduction-amount = function max(deductions, claim-primary)
compute claim-payment = payment-cap - reduction-amount
move "PAID" to claim-status
move "SECONDARY_PAYABLE" to claim-reason
```

With C charges, G gross, P primary, D deductible, K coinsurance, A optional OTAF,
B = A if supplied else C, T = D + K, this computes
`max(0, min(G, B) − max(T, P))` = `max(0, min(G−T, G−P, B−P, B−T))`, the four
limits of §40.8.2/§40.8.3 A. The zero branches come **before** subtraction because
the fields are unsigned; they also fix the demo **zero-reason precedence**:
`PAYMENT_IN_FULL` > `PRIMARY_AT_CAP` > `DEDUCTIONS_AT_CAP`. An all-zero claim is
therefore `PRIMARY_AT_CAP` (0 ≥ 0). Any claim reaching the last two lines has
cap > P and cap > T, so the payment is always ≥ 1 cent when status is `PAID`.

### Counts and totals

`PAID` → paid-count, `ZERO` → zero-count, anything else (`INVALID`) → invalid-count.
`claim-payment` (0 for ZERO/INVALID) is added to `payment-total`. records = paid +
zero + invalid.

## CMS-EX3: why the $13,000 OTAF is not "the $12,500 primary accepted in full"

Inputs (`fixtures/curated.json`, record 2): C = 1,500,000, G = 1,400,000,
P = 1,250,000, D = 155,600 (**$1,556 — historical example input** from the 2022
manual text, not a current rate), K = 0, A = 1,300,000, `full=N`.

Trace through `calculate-prospective-payment`:

1. `raw-full = "N"` → not payment in full.
2. `charge-basis` = 1,500,000, then `claim-has-contract = 1` replaces it with 1,300,000.
3. `payment-cap = min(1,400,000, 1,300,000) = 1,300,000`.
4. `1,250,000 >= 1,300,000`? No.
5. `deductions = 155,600`; `155,600 >= 1,300,000`? No.
6. `reduction-amount = max(155,600, 1,250,000) = 1,250,000`.
7. `claim-payment = 1,300,000 − 1,250,000 = 50,000` cents = **$500**, `PAID/SECONDARY_PAYABLE`.

Observed: `evidence/live/baseline/curated-results.csv` row
`0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE`.

The $13,000 is the amount the provider is **obligated to accept as payment in full
from all sources** (OTAF); §40.8.3 Example 3 says Medicare treats it as the
hospital's charges. It *replaces the charge basis* in the formula. It is **not** a
statement that the primary payer's $12,500 was accepted as full payment — if it
were (`full=Y`), §40.8 says Medicare pays nothing and the COBOL returns
`ZERO/PAYMENT_IN_FULL`. Here the provider can still collect up to
$13,000 − $12,500 = $500 more, and that is what Medicare pays.

Without the OTAF branch the basis would stay at $15,000:
`min(14,000, 15,000) − max(1,556, 12,500) = 14,000 − 12,500 = $1,500`. That is the
$1,000 overstatement a careless migration would introduce. This is explanatory
arithmetic; the starter COBOL handles the case correctly.

## Behaviors a migration must not lose (checklist for Stage 2)

Exact integer cents; ASCII-digit-only numeric test; byte framing with LF and one
optional CR; 4,096-byte and 10,000-record limits; blank line = BAD_LENGTH; empty
file = zero records; validation precedence LENGTH > ID > AMOUNT > CONTRACT > FLAG;
malformed contract = BAD_AMOUNT; full reset per record; `@`+10-digit provisional ID;
duplicate identifiable ID fatal even when rejected; zero-reason precedence; 10-digit
and 15-digit zero-padded CSV fields; exit 0 for a processed batch even with invalid
records, exit 2 for usage and every fatal path.
