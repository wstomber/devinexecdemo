# COBOL vs Python: edge-cases.dat

**Verdict: MATCH** — 24 records compared, 0 mismatches, totals match, outputs byte-identical, exit codes COBOL=0 Python=0.

Input `evidence/maintainability-summary-json/edge/edge-cases.dat` (sha256 `2f36675df28170a6…`).

Parity shows the Python matches the COBOL for this batch. It does not prove Medicare correctness; the independent tests in `tests_policy/` cover that layer.

## Batch totals

| | records | paid | zero | invalid | payment |
|---|---|---|---|---|---|
| COBOL | 24 | 5 | 4 | 15 | $100,002,700.00 |
| Python | 24 | 5 | 4 | 15 | $100,002,700.00 |
| **Result** | | | | | **MATCH** |

## Per record

| # | claim_id | COBOL status | Python status | COBOL payment | Python payment | COBOL reason | Python reason | result |
|---|---|---|---|---|---|---|---|---|
| 1 | `EDGE-OK` | PAID | PAID | $900.00 | $900.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 2 | `@0000000002` | INVALID | INVALID | $0.00 | $0.00 | BAD_ID | BAD_ID | **MATCH** |
| 3 | `@0000000003` | INVALID | INVALID | $0.00 | $0.00 | BAD_ID | BAD_ID | **MATCH** |
| 4 | `@0000000004` | INVALID | INVALID | $0.00 | $0.00 | BAD_ID | BAD_ID | **MATCH** |
| 5 | `@0000000005` | INVALID | INVALID | $0.00 | $0.00 | BAD_ID | BAD_ID | **MATCH** |
| 6 | `EDGE-ID-OVER` | PAID | PAID | $900.00 | $900.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 7 | `EDGE-SIGN` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 8 | `EDGE-POINT` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 9 | `EDGE-HIBIT` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 10 | `EDGE-DASH` | INVALID | INVALID | $0.00 | $0.00 | BAD_AMOUNT | BAD_AMOUNT | **MATCH** |
| 11 | `EDGE-OVERK` | INVALID | INVALID | $0.00 | $0.00 | BAD_CONTRACT | BAD_CONTRACT | **MATCH** |
| 12 | `EDGE-LFLAG` | INVALID | INVALID | $0.00 | $0.00 | BAD_FLAG | BAD_FLAG | **MATCH** |
| 13 | `@0000000013` | INVALID | INVALID | $0.00 | $0.00 | BAD_LENGTH | BAD_LENGTH | **MATCH** |
| 14 | `@0000000014` | INVALID | INVALID | $0.00 | $0.00 | BAD_LENGTH | BAD_LENGTH | **MATCH** |
| 15 | `@0000000015` | INVALID | INVALID | $0.00 | $0.00 | BAD_LENGTH | BAD_LENGTH | **MATCH** |
| 16 | `@0000000016` | INVALID | INVALID | $0.00 | $0.00 | BAD_LENGTH | BAD_LENGTH | **MATCH** |
| 17 | `@0000000017` | INVALID | INVALID | $0.00 | $0.00 | BAD_ID | BAD_ID | **MATCH** |
| 18 | `EDGE-ZERO` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 19 | `EDGE-MAX` | PAID | PAID | $99,999,999.99 | $99,999,999.99 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 20 | `EDGE-CRLF` | PAID | PAID | $900.00 | $900.00 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 21 | `EDGE-OTAF0` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 22 | `EDGE-FULL` | ZERO | ZERO | $0.00 | $0.00 | PAYMENT_IN_FULL | PAYMENT_IN_FULL | **MATCH** |
| 23 | `EDGE-DEDCAP` | ZERO | ZERO | $0.00 | $0.00 | DEDUCTIONS_AT_CAP | DEDUCTIONS_AT_CAP | **MATCH** |
| 24 | `EDGE-1CENT` | PAID | PAID | $0.01 | $0.01 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
