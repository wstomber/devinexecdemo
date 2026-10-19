# 04 — Line-by-line legacy walkthrough, with CMS-EX3 traced

Line numbers are per file at starter commit `be0b00e`.

## batch.cob (main program `msp-batch`)
| Lines | What happens |
| --- | --- |
| 5-13 | Four files: claims (1-byte sequential), CWF (line sequential), results and totals (line sequential output) |
| 16-23 | Record buffers: `input-byte pic x`, `cwf-record pic x(64)`, `output-record pic x(160)`, `totals-record pic x(180)` |
| 24-56 | Working storage: paths (1,024 bytes each), file statuses, counters `pic 9(10)`, totals `pic 9(15)`, `input-record pic x(4097)`, `seen-id` table of 10,000 IDs; copybooks |
| 59-64 | `argument-number` ≠ 4 → usage message, return code 2 |
| 65-76 | Read the four paths; any two equal → "paths must be distinct", 2 |
| 79-80 | Disable runtime NUL encoding and validation for line-sequential files |
| 81 | `perform load-cwf` **before** any other file is opened |
| 82-90 | Open input, results, totals; each failure → `fatal-io` |
| 91-92 | Write the results header |
| 94-110 | Byte loop: status 10 = EOF (flush the partial line); LF → `finish-line`; otherwise append, aborting if the buffer already holds 4,097 bytes |
| 111-121 | Write the totals header and a single `STRING` of the eight counters; close; return 0 |
| 122-135 | `finish-line`: strip one trailing CR; > 4,096 → fatal; `process-record`; reset the buffer |
| 136-141 | Record limit: the 10,001st record is fatal |
| 143-147 | Reset the whole interface; provisional ID `@`+10 digits; copy the first 92 bytes and the real length |
| 148 | `call "validate-claim"` |
| 149-158 | Non-`@` ID: linear search of `seen-id`; repeat → fatal; else append |
| 159-161 | VALID → `call "calculate-payment"` |
| 162-167 | PAID/ZERO → `call "cwf-check"`; else NOT_SENT/CLAIM_INVALID |
| 168-180 | Counters and totals |
| 181-188 | Build and write the CSV row |
| 189-205 | `load-cwf`: open; read until end; each record → `parse-cwf`; close |
| 206-237 | `parse-cwf`: B and H layout checks (see 01-cobol-explanation.md); anything else → `bad-cwf` |
| 238-267 | `bad-cwf`, write/close helpers, `fatal-io` (message, return code 2, `stop run`) |

## validate.cob (`validate-claim`)
| Lines | What happens |
| --- | --- |
| 11-13 | Assume INVALID/BAD_LENGTH; length ≠ 92 → return |
| 14-33 | BAD_ID: all spaces, or a scan in which a space ends the ID and any later non-space fails; allowed characters A-Z, 0-9, `-`, `_` |
| 33 | `move raw-id to claim-id`: from here on the row carries the real ID |
| 34-44 | BAD_AMOUNT: five NUMERIC tests, then the contract (sentinel or NUMERIC); a valid contract sets `claim-has-contract` |
| 46-50 | Text → packed decimal (only after all class tests) |
| 51-55 | BAD_CONTRACT: contract > charges |
| 56-57 | BAD_FLAG |
| 58-64 | BAD_MBI: 11 characters, each A-Z or 0-9 |
| 65-68 | BAD_DATE: NUMERIC, month 01-12, day 01-31 |
| 69-73 | Copy MBI and date; VALID |

## payment.cob — CMS-EX3 traced
Input row 2 of the curated batch: `CMS-EX3` C=1,500,000 G=1,400,000 P=1,250,000 D=155,600 K=0 A=1,300,000 full=N, MBI 2MSP0000001, date 20250315.

| Line | Statement | CMS-EX3 values |
| --- | --- | --- |
| 13-14 | payment 0, status ZERO | 0 / ZERO |
| 16 | `if raw-full = "Y"` | `N`, so this branch is skipped |
| 20 | `move claim-charges to charge-basis` | 1,500,000 |
| 21-22 | `if claim-has-contract = 1` → `move claim-contract to charge-basis` | has contract, so charge-basis = **1,300,000** |
| 24 | `payment-cap = min(claim-gross, charge-basis)` | min(1,400,000, 1,300,000) = 1,300,000 |
| 25 | `if claim-primary >= payment-cap` | 1,250,000 ≥ 1,300,000? No |
| 29 | `deductions = deductible + coinsurance` | 155,600 |
| 30 | `if deductions >= payment-cap` | No |
| 34 | `reduction-amount = max(deductions, claim-primary)` | 1,250,000 |
| 35 | `claim-payment = payment-cap - reduction-amount` | **50,000** |
| 36-37 | PAID / SECONDARY_PAYABLE | |

## cwf.cob — CMS-EX3 traced
Reference (`build/cwf.dat`): `B2MSP000000120200101999999992025010120251231`, which means entitled 2020-01-01 → open, MSP period 2025.

| Line | Statement | CMS-EX3 values |
| --- | --- | --- |
| 18-20 | released 0, REJECTED/NOT_ENTITLED | starting state |
| 22-27 | find the first B with MBI 2MSP0000001 | found (record 2) |
| 28 | not found → return | — |
| 29-32 | date < from or > to → return | 20250315 lies between 20200101 and 99999999, so it continues |
| 33-41 | DUPLICATE if any H matches MBI + date + charges | the only H is for 5HIST000001, so no match |
| 42-48 | MSP_PRIMARY_NOT_BILLED if MSP covers the date and primary = 0 | MSP 2025 covers the date, but primary is 1,250,000, so the insurer was billed and the check passes |
| 49-51 | ACCEPTED / DISPOSITION_01, released = payment | **50,000 released** |

Output row: `0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000`. COBOL and Python produce it identically (`evidence/live/comparison/curated/`).
