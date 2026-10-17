# COBOL vs Python: synthetic.dat

**Verdict: MATCH** — 1000 records compared, 0 mismatches, totals match, outputs byte-identical, exit codes COBOL=0 Python=0.

Input `build/synthetic.dat` (sha256 `56584f8a9c0ce83e…`).

Parity shows the Python matches the COBOL for this batch. It does not prove Medicare correctness; the independent tests in `tests_policy/` cover that layer.

## Batch totals

| | records | paid | zero | invalid | payment |
|---|---|---|---|---|---|
| COBOL | 1000 | 271 | 729 | 0 | $5,143,525,709.51 |
| Python | 1000 | 271 | 729 | 0 | $5,143,525,709.51 |
| **Result** | | | | | **MATCH** |

## Per record (first 25 + any mismatches + CMS-EX3; full table in side-by-side.csv)

| # | claim_id | COBOL status | Python status | COBOL payment | Python payment | COBOL reason | Python reason | result |
|---|---|---|---|---|---|---|---|---|
| 1 | `S00000000001` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 2 | `S00000000002` | PAID | PAID | $16,241,722.50 | $16,241,722.50 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 3 | `S00000000003` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 4 | `S00000000004` | PAID | PAID | $31,830,839.89 | $31,830,839.89 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 5 | `S00000000005` | PAID | PAID | $22,313,574.06 | $22,313,574.06 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 6 | `S00000000006` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 7 | `S00000000007` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 8 | `S00000000008` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 9 | `S00000000009` | PAID | PAID | $2,185,058.30 | $2,185,058.30 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 10 | `S00000000010` | PAID | PAID | $27,048,134.71 | $27,048,134.71 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 11 | `S00000000011` | PAID | PAID | $10,874,724.52 | $10,874,724.52 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 12 | `S00000000012` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 13 | `S00000000013` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 14 | `S00000000014` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 15 | `S00000000015` | ZERO | ZERO | $0.00 | $0.00 | PAYMENT_IN_FULL | PAYMENT_IN_FULL | **MATCH** |
| 16 | `S00000000016` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 17 | `S00000000017` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 18 | `S00000000018` | ZERO | ZERO | $0.00 | $0.00 | PRIMARY_AT_CAP | PRIMARY_AT_CAP | **MATCH** |
| 19 | `S00000000019` | PAID | PAID | $15,728,996.41 | $15,728,996.41 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 20 | `S00000000020` | PAID | PAID | $14,490,849.22 | $14,490,849.22 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 21 | `S00000000021` | ZERO | ZERO | $0.00 | $0.00 | DEDUCTIONS_AT_CAP | DEDUCTIONS_AT_CAP | **MATCH** |
| 22 | `S00000000022` | PAID | PAID | $517,820.51 | $517,820.51 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 23 | `S00000000023` | PAID | PAID | $23,874,239.85 | $23,874,239.85 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 24 | `S00000000024` | PAID | PAID | $11,020,211.19 | $11,020,211.19 | SECONDARY_PAYABLE | SECONDARY_PAYABLE | **MATCH** |
| 25 | `S00000000025` | ZERO | ZERO | $0.00 | $0.00 | PAYMENT_IN_FULL | PAYMENT_IN_FULL | **MATCH** |
