# 04 — Line-by-line legacy walkthrough, with CMS-EX3 traced

Starter `be0b00e`. COBOL constructs are explained in `03-cobol-primer.md`.

## The record

```
CMS-EX3     000150000000014000000001250000000015560000000000000001300000NP2MSPEGHP0220250610
```

Values in cents: C = 1,500,000 ($15,000), G = 1,400,000, P = 1,250,000, D = 155,600,
K = 0, A (OTAF) = 1,300,000, full = `N`, MBI `P2MSPEGHP02`, DOS `20250610`.
(Record built by `tests_policy/msp_harness.py` from the ledger case `CMS-EX3`; the curated
batch has the same amounts with synthetic MBI `2MSP0000001`, DOS `20250315` and the starter
CWF file.) Reference record used in the trace (ledger CWF data, `tests_policy/expectations.json`):
`BP2MSPEGHP022018070199999999` + `2024060120251130` — entitled from 2018-07-01, open
ended, employer plan primary 2024-06-01 … 2025-11-30. No `H` history for this MBI.

## batch.cob — getting the record to the subprograms

| Lines | What happens to CMS-EX3 |
| --- | --- |
| 59–76 | four arguments, distinct paths; otherwise usage error, exit 2 |
| 79–81 | runtime options; `perform load-cwf` reads the CWF file **first** (189–237): the `B` line passes the checks at 209–212 (cols 45–64 blank, MBI present, dates numeric, < 1,000 entries) and 217–225 (MSP columns numeric, so `bene-has-msp = 1`) |
| 82–92 | open input, results, totals (each status checked); write the results header |
| 94–110 | read one byte at a time; bytes accumulate in `input-record`; LF (`x"0A"`) calls `finish-line` |
| 122–135 | no trailing CR; 92 ≤ 4,096; `perform process-record` |
| 137–141 | record 2 of 10,000 allowed (CMS-EX3 is record 2 of the curated batch) |
| 143–145 | `initialize claim-interface`; `claim-id` = `@0000000002` |
| 146–148 | copy bytes 1–92 into `claim-raw`, length 92, `call "validate-claim"` |

## validate.cob — passes every check

| Lines | Check | CMS-EX3 |
| --- | --- | --- |
| 11–13 | status INVALID, reason BAD_LENGTH; length ≠ 92? | 92 → continue |
| 14–32 | BAD_ID: not blank; `C M S - E X 3` are letters/digits/`-`; then spaces only | pass |
| 33 | `move raw-id to claim-id` — the provisional `@0000000002` is replaced by `CMS-EX3` | |
| 34–39 | BAD_AMOUNT: five amounts NUMERIC | pass |
| 40–44 | contract ≠ `----------` and NUMERIC → `claim-contract` = 1,300,000, `claim-has-contract = 1` | pass |
| 46–50 | only now are amounts moved into packed (COMP-3) fields | |
| 51–55 | BAD_CONTRACT: 1,300,000 > 1,500,000? | no → pass |
| 56–57 | BAD_FLAG: `N` | pass |
| 58–64 | BAD_MBI: `P2MSPEGHP02` all A–Z/0–9 | pass |
| 65–68 | BAD_DATE: `20250610` numeric, month 06, day 10 | pass |
| 69–73 | copy MBI/DOS, status `VALID`, reason spaces | |

Back in batch.cob 149–158: `CMS-EX3` does not start with `@`, not seen before, stored in
`seen-id`. Line 159: VALID → `call "calculate-payment"`.

## payment.cob — the $500

| Line | Statement | CMS-EX3 values |
| --- | --- | --- |
| 13–14 | `claim-payment = 0`, status `ZERO` | default until proven payable |
| 16–19 | `raw-full = "Y"`? | `N` → continue |
| 20 | `charge-basis = claim-charges` | 1,500,000 |
| 21–23 | `claim-has-contract = 1` → `charge-basis = claim-contract` | **1,300,000** — the OTAF replaces the charges (§40.8.3) |
| 24 | `payment-cap = min(claim-gross, charge-basis)` | min(1,400,000, 1,300,000) = **1,300,000** |
| 25–28 | `claim-primary >= payment-cap`? | 1,250,000 ≥ 1,300,000? no |
| 29 | `deductions = D + K` | 155,600 |
| 30–33 | `deductions >= payment-cap`? | no |
| 34 | `reduction-amount = max(deductions, claim-primary)` | max(155,600, 1,250,000) = 1,250,000 |
| 35 | `claim-payment = payment-cap - reduction-amount` | 1,300,000 − 1,250,000 = **50,000** |
| 36–37 | status `PAID`, reason `SECONDARY_PAYABLE` | |

Lines 24 and 34–35 are the four CMS limits in one step: min(G−P, G−T, A−P, A−T) =
min(G, A) − max(T, P). Lines 25–33 run *before* the subtraction because the fields are
unsigned (a negative difference would lose its sign) and they fix the zero-reason
precedence. Without lines 21–23 the cap would be 1,400,000 and the payment 150,000 ($1,500).

Back in batch.cob 162–163: status PAID → `call "cwf-check"`.

## cwf.cob — accepted, $500 released

| Line | Statement | CMS-EX3 |
| --- | --- | --- |
| 18–20 | released 0, `REJECTED`, reason `NOT_ENTITLED` | pessimistic default |
| 21–27 | find the first `B` with `bene-mbi = claim-mbi` | found `P2MSPEGHP02` |
| 28 | not found → reject | found → continue |
| 29–32 | DOS before entitled-from or after entitled-to? | 20180701 ≤ 20250610 ≤ 99999999 → continue |
| 33–34 | reason now `DUPLICATE`; charges as 10 digits | `0001500000` |
| 35–41 | any `H` with same MBI, DOS and charges? | none for this MBI → continue |
| 42 | reason now `MSP_PRIMARY_NOT_BILLED` | |
| 43–48 | MSP period on file, covers DOS, and primary = 0? | period 20240601–20251130 covers the DOS, but primary = 1,250,000 → continue |
| 49–51 | `ACCEPTED`, `DISPOSITION_01`, `claim-released = claim-payment` | released **50,000** |

Each check first sets the reason it would fail with, then `goback`s on failure — so the
first failing check's reason is what remains. A rejection never touches `claim-payment`:
the calculated amount stays visible and only `claim-released` is 0.

## batch.cob — output

Lines 168–180 count accepted/rejected and paid/zero/invalid and add payment and released
amounts to the totals; 181–188 write:

```
0000000002,CMS-EX3,PAID,0000050000,SECONDARY_PAYABLE,ACCEPTED,DISPOSITION_01,0000050000
```

(record number 2 in the curated batch; 10-digit fields because `record-count`,
`payment-display` and `released-display` are `PIC 9(10)`). At end of file (97–99, 111–121)
the totals line is written with 10-digit counts and 15-digit sums, files are closed
(247–262) and the return code is 0. Any failed status goes to `fatal-io` (263–267):
message on stderr, exit 2, outputs to be discarded.

Same trace in the evidence: `evidence/live/baseline/` (COBOL), the ledger row `CMS-EX3`
(`tests_policy/expectations.json`), and record 2 in `evidence/live/stage4/curated/side-by-side.md`.
