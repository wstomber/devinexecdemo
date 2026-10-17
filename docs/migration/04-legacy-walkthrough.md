# 04 — Line-by-line walkthrough of the legacy COBOL, with CMS-EX3 traced

Read [03-cobol-primer.md](03-cobol-primer.md) first if COBOL syntax is new.
Line numbers are from the unchanged starter files. The trace values are the real
CMS-EX3 record, which is line 2 of `build/curated.dat`:

```
CMS-EX3     000150000000014000000001250000000015560000000000000001300000N
|id 1-12   |charges   |gross     |primary   |deduct.   |coins.    |contract  |full
```

charges 1,500,000 · gross 1,400,000 · primary 1,250,000 · deductible 155,600 ·
coinsurance 0 · contract (OTAF) 1,300,000 · full `N` (all cents).

## batch.cob — the driver

| Lines | Code | What it does | CMS-EX3 state |
|---|---|---|---|
| 1–2 | `identification division` / `program-id. msp-batch` | Names the main program | |
| 3–11 | `environment division ... select` | Binds `claims-file` (sequential, 1-byte records) and the two LINE SEQUENTIAL output files to the path variables; each has a file-status variable | |
| 14–19 | `fd` entries | File buffers: one input byte; 160/180-byte output lines | |
| 21–43 | working-storage | Paths (1,024 bytes each), the 4,097-byte line buffer, counters `9(10)`, total `9(15)`, the 10,000-entry `seen-id` table | |
| 44 | `copy "claim.cpy"` | The shared `claim-interface` block | |
| 47–52 | `accept argument-count ...` | Exactly 3 arguments, else `usage:` and return code 2 | |
| 53–61 | path checks | Identical path strings → `paths must be distinct`, return 2 | |
| 64–65 | `set environment "COB_LS_..."` | Disables GnuCOBOL line-sequential null/validation handling for the outputs | |
| 66–74 | `open` ×3 | Input, then results, then totals; any non-`00` status → `fatal-io` | |
| 75–76 | header | Writes `record_no,claim_id,status,payment_cents,reason` | |
| 78–94 | read loop | Status `10` (EOF): process a pending partial line, stop. Status `00`: LF ends a line (`finish-line`); any other byte is appended, but a 4,098th byte is fatal (88) | Bytes of line 2 accumulate; LF at byte 74 → `finish-line` with `input-length` 73 |
| 105–111 | `finish-line` CR strip | Drops exactly one trailing X'0D' | No CR in curated.dat |
| 112–115 | length guard | Length > 4,096 after CR strip → fatal | 73, fine |
| 116–118 | | `process-record`, then clear the buffer | |
| 120–124 | record limit | Record 10,001 → fatal; else count it | `record-count` = 2 |
| 126 | `initialize claim-interface` | Every field spaces/zero — `claim-has-contract` = 0, `claim-payment` = 0 | Record 1's values are gone |
| 127–128 | provisional ID | `claim-id` = `@0000000002` until validation proves a real ID | `@0000000002` |
| 129–130 | | Slice the first 73 bytes into `claim-raw`; set `claim-length` | raw fields as shown above |
| 131 | `call "validate-claim"` | By reference (see validate.cob below) | returns `VALID`, `claim-id` = `CMS-EX3` |
| 132–141 | duplicate check | If `claim-id` no longer starts with `@` it is identifiable: linear scan of `seen-id`; a match is fatal (even if status is INVALID); otherwise append | `CMS-EX3` not seen; appended |
| 142–144 | | Only VALID records reach payment | calls `calculate-payment` |
| 145–150 | counts and total | PAID / ZERO / other → INVALID; add payment to total | `paid-count` +1, total +50,000 |
| 151–157 | output row | 10-digit record no., trimmed ID/status, 10-digit payment, trimmed reason | `0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE` |
| 95–104 | totals | After EOF: header + `STRING` of four 10-digit counts and the 15-digit total; close; return 0 | |
| 164–179 | `close-files` | Closes what is open, checks status | |
| 180–184 | `fatal-io` | Message to stderr, return code 2, `stop run` (partial files must be discarded) | |

## validate.cob — `validate-record`

Pattern: set the reason **before** each check and `goback` on failure, so the reason
left in place is the first rule that failed (this is the precedence).

| Lines | Code | CMS-EX3 |
|---|---|---|
| 11–13 | status INVALID, reason BAD_LENGTH; length ≠ 73 → return | 73 → continue |
| 14–15 | reason BAD_ID; all-space ID → return | `CMS-EX3     ` → continue |
| 16–32 | scan 12 ID bytes: after the first space only spaces allowed; else `A-Z`, `0-9`, `-`, `_` | `C M S - E X 3` then 5 spaces → valid |
| 33 | ID becomes identifiable | `claim-id` = `CMS-EX3     ` |
| 34–39 | reason BAD_AMOUNT; five required amounts must be NUMERIC | all digits |
| 40–44 | contract: `----------` = absent; else must be NUMERIC (malformed → still BAD_AMOUNT); set `claim-has-contract` = 1 | `0001300000` → `claim-contract` 1,300,000, flag 1 |
| 45–50 | numeric moves, only after the class tests | parsed amounts as above |
| 51–55 | reason BAD_CONTRACT; contract > charges → return | 1,300,000 ≤ 1,500,000 → continue |
| 56–57 | reason BAD_FLAG; flag must be `Y`/`N` | `N` → continue |
| 58–60 | status VALID, reason spaces | VALID |

## payment.cob — `calculate-prospective-payment` (CMS-EX3 line by line)

| Line | Code | CMS-EX3 values after the line |
|---|---|---|
| 13 | `move 0 to claim-payment` | payment 0 |
| 14 | `move "ZERO" to claim-status` | status ZERO (default until proven payable) |
| 16–19 | `if raw-full = "Y"` → PAYMENT_IN_FULL, return | `N`: skipped. The $13,000 is **not** "primary accepted in full" |
| 20 | `move claim-charges to charge-basis` | charge-basis 1,500,000 |
| 21–23 | `if claim-has-contract = 1` → `move claim-contract to charge-basis` | **charge-basis 1,300,000** (OTAF replaces charges) |
| 24 | `payment-cap = min(claim-gross, charge-basis)` | min(1,400,000, 1,300,000) = **1,300,000** |
| 25–28 | `if claim-primary >= payment-cap` → PRIMARY_AT_CAP | 1,250,000 < 1,300,000: continue |
| 29 | `deductions = claim-deductible + claim-coinsurance` | 155,600 |
| 30–33 | `if deductions >= payment-cap` → DEDUCTIONS_AT_CAP | 155,600 < 1,300,000: continue |
| 34 | `reduction-amount = max(deductions, claim-primary)` | max(155,600, 1,250,000) = 1,250,000 |
| 35 | `claim-payment = payment-cap - reduction-amount` | 1,300,000 − 1,250,000 = **50,000** |
| 36–37 | status PAID, reason SECONDARY_PAYABLE | PAID / SECONDARY_PAYABLE |
| 38 | `goback` | back to batch.cob 145 |

### Why lines 24 and 34–35 equal the CMS four-limit rule

`min(G, B) − max(T, P)` = the smallest of `G−T, G−P, B−T, B−P`, because subtracting
the larger reduction from the smaller ceiling gives the smallest difference. For CMS-EX3:
G−T 1,244,400 · G−P 150,000 · B−P **50,000** · B−T 1,144,400 → lowest 50,000. Lines 25–33
handle the cases where that value would be ≤ 0 (payment 0 with a reason).

### The $1,500 wrong answer

If lines 21–23 were dropped (or the contract ignored), charge-basis stays 1,500,000,
line 24 gives min(1,400,000, 1,500,000) = 1,400,000, and line 35 gives
1,400,000 − 1,250,000 = **150,000** ($1,500). Ledger case `EX3-NO-OTAF` pins that value for
the no-OTAF input; `CMS-EX3` pins $500 with OTAF. The historical $1,556 deductible is an
input from the published example and only affects the T limits, which do not control here.
