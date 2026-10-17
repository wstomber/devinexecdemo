# COBOL vs Python: curated 30-record batch

**Verdict: MATCH** — 30 records compared, 0 mismatches, totals match, outputs byte-identical, exit codes COBOL=0 Python=0.

Input `build/curated.dat` (sha256 `143f9cf2e83b811b…`).

Parity shows the Python matches the COBOL for this batch. It does not prove Medicare correctness; the independent tests in `tests_policy/` cover that layer.

## Batch totals

| | records | paid | zero | invalid | payment |
|---|---|---|---|---|---|
| COBOL | 30 | 12 | 9 | 9 | $100,004,502.02 |
| Python | 30 | 12 | 9 | 9 | $100,004,502.02 |
| **Result** | | | | | **MATCH** |

## CMS-EX3 (CMS Example 3)

COBOL $500.00 SECONDARY_PAYABLE · Python $500.00 SECONDARY_PAYABLE · **MATCH**. Expected from policy: $13,000 OTAF − $12,500 primary = $500.00.

## Per record

| # | claim_id | COBOL status | Python status | COBOL payment | Python payment | COBOL reason | Python reason | result |
|---|---|---|---|---|---|---|---|---|
| 1 | `CMS-EX1` | PAID | PAID | $1,500.00 | $1,500.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 2 | `CMS-EX3` | PAID | PAID | $500.00 | $500.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 3 | `ORDINARY` | PAID | PAID | $600.00 | $600.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 4 | `CHARGE-LIMIT` | PAID | PAID | $500.00 | $500.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 5 | `DEDUCT-LIMIT` | PAID | PAID | $600.00 | $600.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 6 | `CONTRACT-DED` | ZERO | ZERO | $0.00 | $0.00 | DEDUCTIONS_AT_CAP | DEDUCTIONS_AT_CAP | **MATCH** |
| 7 | `PRIMARY-EQ` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 8 | `PRIMARY-HIGH` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 9 | `FULL-FIRST` | ZERO | ZERO | $0.00 | $0.00 | PAYMENT_IN_FULL | PAYMENT_IN_FULL | **MATCH** |
| 10 | `ALL-ZERO` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 11 | `NO-PRIMARY` | PAID | PAID | $800.00 | $800.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 12 | `ONE-CENT` | PAID | PAID | $0.01 | $0.01 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 13 | `CENT-BELOW` | PAID | PAID | $0.01 | $0.01 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 14 | `CONTRACT-0` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 15 | `DEDUCT-EQ` | ZERO | ZERO | $0.00 | $0.00 | DEDUCTIONS_AT_CAP | DEDUCTIONS_AT_CAP | **MATCH** |
| 16 | `DEDUCT-HIGH` | ZERO | ZERO | $0.00 | $0.00 | DEDUCTIONS_AT_CAP | DEDUCTIONS_AT_CAP | **MATCH** |
| 17 | `COINS-CENT` | PAID | PAID | $0.01 | $0.01 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 18 | `TIE` | PAID | PAID | $1.00 | $1.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 19 | `MAX-DEDUCT` | ZERO | ZERO | $0.00 | $0.00 | DEDUCTIONS_AT_CAP | DEDUCTIONS_AT_CAP | **MATCH** |
| 20 | `MAX-PAY` | PAID | PAID | $99,999,999.99 | $99,999,999.99 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 21 | `@0000000021` | INVALID | INVALID | $0.00 | $0.00 | BAD_LENGTH | BAD_LENGTH | **MATCH** |
| 22 | `@0000000022` | INVALID | INVALID | $0.00 | $0.00 | BAD_LENGTH | BAD_LENGTH | **MATCH** |
| 23 | `@0000000023` | INVALID | INVALID | $0.00 | $0.00 | BAD_ID | BAD_ID | **MATCH** |
| 24 | `MISSING` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 25 | `SIGNED` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 26 | `DECIMAL` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 27 | `BADOPTION` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 28 | `HIGHCONTRACT` | INVALID | INVALID | $0.00 | $0.00 | BAD_CONTRACT | BAD_CONTRACT | **MATCH** |
| 29 | `BADFLAG` | INVALID | INVALID | $0.00 | $0.00 | BAD_FLAG | BAD_FLAG | **MATCH** |
| 30 | `AFTER-ERROR` | PAID | PAID | $1.00 | $1.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
