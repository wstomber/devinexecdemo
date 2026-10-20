# 04 — Line-by-line legacy walkthrough, with CMS-EX3 traced

Line numbers are per file at starter `be0b00e`.

## batch.cob: `msp-batch`

| Lines | What happens |
| --- | --- |
| 6–13 | Four files: claims (byte-sequential), CWF, results and totals (line sequential), each with a file-status variable |
| 16–23 | Record areas: 1-byte claim reads, 64-byte CWF lines, 160-byte result lines, 180-byte totals lines |
| 25–56 | Working storage: paths, counters (`pic 9(10)`), totals (`pic 9(15)`), the 4,097-byte line buffer, the 10,000-entry `seen-id` table, and both copybooks |
| 59–64 | Exactly 4 arguments, otherwise usage + exit 2 |
| 65–76 | Read the four paths. Any two equal → exit 2 |
| 79–80 | Stop the runtime from altering NULs or validating line data |
| 81 | `perform load-cwf`: the reference data is loaded *before* the claims file opens |
| 82–90 | Open input, then results, then totals. Any failure → `fatal-io` |
| 91–92 | Write the results header |
| 94–110 | Byte loop: status `10` = EOF (flush a partial line), LF = end of line, otherwise append. The 4,098th byte → fatal |
| 111–118 | Write the totals header and the one data row |
| 119–121 | Close the files, exit 0 |
| 122–135 | `finish-line`: drop one trailing CR, fatal if > 4,096, process, reset buffer |
| 137–141 | 10,001st record → fatal; otherwise count it |
| 143–147 | Reset everything, set provisional `@`+number ID, copy the first 92 bytes and the true length |
| 148 | Validate |
| 149–158 | Identified ID: linear scan of `seen-id`, a repeat is fatal, otherwise remember it |
| 159–161 | Valid → calculate payment |
| 162–167 | PAID/ZERO → CWF check. Invalid → NOT_SENT/CLAIM_INVALID |
| 168–180 | Update CWF counts, released total, status counts, payment total |
| 181–188 | Build and write the CSV row |
| 189–205 | `load-cwf`: open (fatal if missing), read every line into `parse-cwf` |
| 206–237 | `parse-cwf`: `B` and `H` layout checks (spaces after the record, non-blank MBI, numeric dates/charges, MSP all-dash or numeric, 1,000-entry caps); any other first byte → `bad-cwf` |
| 263–267 | `fatal-io`: message to stderr, return code 2, `stop run` |

## validate.cob: `validate-record`

| Lines | Check (first failure wins) |
| --- | --- |
| 11–13 | Assume INVALID/BAD_LENGTH. Length ≠ 92 → return |
| 14–33 | BAD_ID: all spaces, or a scan in which any non-space after a space, or any byte outside `A–Z 0–9 - _`, returns |
| 33 | ID accepted: `claim-id` = raw ID |
| 34–39 | BAD_AMOUNT: five required amounts are NUMERIC |
| 40–44 | Contract: `----------` = absent; otherwise NUMERIC (else BAD_AMOUNT); set `claim-has-contract` |
| 45–50 | Only now MOVE text → packed numbers |
| 51–55 | BAD_CONTRACT: contract > charges |
| 56–57 | BAD_FLAG: not `Y`/`N` |
| 58–64 | BAD_MBI: each of 11 bytes A–Z or 0–9 |
| 65–68 | BAD_DATE: NUMERIC, month 01–12, day 01–31 |
| 69–73 | Copy MBI and date, status VALID |

## CMS-EX3 traced through payment.cob and cwf.cob

Input (curated record 2): ID `CMS-EX3`, charges 1,500,000, gross 1,400,000,
primary 1,250,000, deductible 155,600, coinsurance 0, contract 1,300,000,
`full=N`, MBI `2MSP0000001`, date 20250315. The CWF file says `2MSP0000001` is
entitled 2020-01-01 → open-ended, with an MSP period 2025-01-01 → 2025-12-31,
and there is no history for this MBI.

**payment.cob, `calculate-prospective-payment`**

| Line | Statement | Value after |
| --- | --- | --- |
| 13–14 | `move 0 to claim-payment`, `move "ZERO" to claim-status` | payment 0, ZERO |
| 16 | `if raw-full = "Y"` | `N`, so not taken |
| 20 | `move claim-charges to charge-basis` | charge-basis = 1,500,000 |
| 21–23 | `if claim-has-contract = 1  move claim-contract to charge-basis` | **charge-basis = 1,300,000** (the OTAF replaces the charges) |
| 24 | `compute payment-cap = function min(claim-gross, charge-basis)` | min(1,400,000, 1,300,000) = **1,300,000** |
| 25 | `if claim-primary >= payment-cap` | 1,250,000 ≥ 1,300,000? No |
| 29 | `compute deductions = claim-deductible + claim-coinsurance` | 155,600 |
| 30 | `if deductions >= payment-cap` | No |
| 34 | `compute reduction-amount = function max(deductions, claim-primary)` | max(155,600, 1,250,000) = 1,250,000 |
| 35 | `compute claim-payment = payment-cap - reduction-amount` | 1,300,000 − 1,250,000 = **50,000 ($500)** |
| 36–37 | PAID / SECONDARY_PAYABLE | |

Without line 21–23 the cap would be min(1,400,000, 1,500,000) = 1,400,000 and the
payment 150,000 ($1,500). The ledger shows this as EX3-NO-OTAF.

**cwf.cob, `check-claim`**

| Line | Statement | Value after |
| --- | --- | --- |
| 18–20 | released 0, `REJECTED`, `NOT_ENTITLED` (pessimistic default) | |
| 22–27 | Scan `bene-mbi` for `2MSP0000001` | found (entry 2) |
| 28 | not found? | No |
| 29–32 | 20250315 < 20200101 or > 99999999? | No → entitled |
| 33 | reason := `DUPLICATE` | |
| 34–41 | any `H` with same MBI, date and charges `0001500000`? | none → continue |
| 42 | reason := `MSP_PRIMARY_NOT_BILLED` | |
| 43–48 | MSP period 20250101–20251231 covers 20250315 **and** primary = 0? | primary is 1,250,000 → not taken |
| 49–51 | `ACCEPTED`, `DISPOSITION_01`, `claim-released = claim-payment` | **released 50,000** |

Output row (identical from COBOL and Python):
`0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000`.
The curated look-alikes run the same payment arithmetic. `EX3-NOT-ENT` stops at
line 29–32, `EX3-DUP` at 34–41, and `EX3-MSP-NOBL` (primary 0) at 43–48. Each
keeps its calculated payment and releases 0.
