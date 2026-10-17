# 02 — Rule map: policy → COBOL → tests → Python → result

Source column: **POLICY** = CMS Pub. 100-05 Ch. 5 §§40.8–40.8.3 as excerpted in
[docs/rules.md](../rules.md) / [cms-example-3.md](../cms-example-3.md);
**INTERFACE** = a demo/README decision (record layout, reasons, limits). Interface rows
are not CMS policy and must not be presented as such.

Tests: ledger case IDs live in [tests_policy/expectations.json](../../tests_policy/expectations.json)
(run by `tests_policy/test_policy_ledger.py`); batch tests in
`tests_policy/test_batch_interface.py`; unit tests in `tests_python/test_msp.py`.
"Result" = outcome of this live run: Stage 2 tests vs COBOL ([log](../../evidence/live/stage2-tests-vs-cobol.log)),
the same tests unchanged vs Python ([log](../../evidence/live/stage3-tests-policy-vs-python.log)),
and COBOL/Python side-by-side ([curated](../../evidence/live/compare/curated/side-by-side.md),
[synthetic](../../evidence/live/compare/synthetic/side-by-side.md),
[edge](../../evidence/live/compare/edge/side-by-side.md),
[fatal](../../evidence/live/compare/fatal/fatal-paths.md)).

## Payment rules

| # | Rule | Source | COBOL | Independent tests | Python | Result |
|---|---|---|---|---|---|---|
| P1 | Secondary payment = lowest of G−P, G−T, B−P, B−T, never below 0 (B = charges, or OTAF if present) | POLICY §40.8.3A, §40.8.2 | payment.cob 20–35 | CMS-EX1, LIM-G-T, LIM-G-P, LIM-C-P, LIM-C-T, LIM-A-P, LIM-A-T, A-WITH-T; `CalculatePayment.test_each_limit_controls` | `calculate_payment` 97–112 | PASS COBOL, PASS Python, 0 mismatches |
| P2 | OTAF/contract amount replaces charges as the charge basis (`claim-has-contract` branch) | POLICY §40.8.2 | payment.cob 20–23 | CMS-EX3, LIM-A-P, LIM-A-T, A-UNDER-C-1, EQ-A-G | `calculate_payment` 105 | PASS / PASS / 0 mismatches |
| P3 | Compute with the lower of gross and basis: `min(claim-gross, charge-basis)` | POLICY §40.8.3A | payment.cob 24 | EQ-G-C, G-OVER-C-1, G-UNDER-C-1 | 106 | PASS / PASS / 0 |
| P4 | `max(deductions, primary)` is the single reduction; equal-limit ties give one answer | POLICY §40.8.3A (algebra) | payment.cob 34–35 | EQ-T-P, EQ-ALL4, T-OVER-P-1, T-SPLIT-M1; `test_equal_limits` | 112 | PASS / PASS / 0 |
| P5 | **CMS-EX3 = $500 (50,000 cents)**; same inputs without OTAF = $1,500 | POLICY §40.8.3 Ex. 3 | payment.cob 22, 24, 34–35 | CMS-EX3, EX3-NO-OTAF; `test_cms_ex3_contract_branch`; curated record 2 | 105–112 | 50,000 in ledger, COBOL, Python |
| P6 | Primary paid ≥ cap → no secondary payment | POLICY §40.8, §40.8.3A | payment.cob 25–28 | P-CAP-M1, P-CAP-EQ, P-CAP-P1; `test_one_cent_boundaries` | 107–108 | PASS / PASS / 0 |
| P7 | Deductible + coinsurance ≥ cap → no secondary payment | POLICY §40.8.1, §40.8.3A | payment.cob 29–33 | T-CAP-M1, T-CAP-EQ, T-CAP-P1, MAX-DEDUCT | 109–111 | PASS / PASS / 0 |
| P8 | Primary payment accepted in full (`full=Y`) → no secondary payment | POLICY §40.8 | payment.cob 16–19 | FULL-PAY, IF-FULL-1ST | 103–104 | PASS / PASS / 0 |
| P9 | No primary payment → Medicare limit is G−T / B−T | POLICY §40.8.3A | payment.cob 34 | NO-PRIMARY | 112 | PASS / PASS / 0 |
| P10 | Exact integer cents, maxima 9,999,999,999 | INTERFACE (README) | claim.cpy 76–83 `9(10) comp-3`; payment.cob 5–8 | MAX-PAY, MAX-PAY-M1, MAX-DEDUCT; `test_maximums_are_exact_integers` | `int` throughout | PASS / PASS / 0 |

## Zero-reason precedence (INTERFACE)

| # | Rule | Source | COBOL | Tests | Python | Result |
|---|---|---|---|---|---|---|
| Z1 | PAYMENT_IN_FULL before PRIMARY_AT_CAP before DEDUCTIONS_AT_CAP | INTERFACE (README, rules.md) | payment.cob 15–33 (order of `goback`s) | IF-FULL-1ST, IF-PRIM-1ST, IF-ALL-ZERO, G-ZERO; `test_zero_reason_precedence` | 103–111 | PASS / PASS / 0 |
| Z2 | Contract = 0 is valid and caps at 0 (PRIMARY_AT_CAP) | INTERFACE | payment.cob 22–25 | IF-A-ZERO | 105–107 | PASS / PASS / 0 |

## Validation (all INTERFACE)

| # | Rule | COBOL | Tests | Python | Result |
|---|---|---|---|---|---|
| V1 | Length ≠ 73 → BAD_LENGTH (checked first; blank line = BAD_LENGTH) | validate.cob 11–13 | IF-LEN-72, IF-LEN-74, IF-LEN-ID, IF-LEN-BLANK; batch blank/CR-only tests | `validate_record` 71–72 | PASS / PASS / 0 |
| V2 | ID: 1–12 of `A-Z 0-9 - _`, left-justified, space padded → else BAD_ID | validate.cob 14–33 | IF-ID-* (9 cases); `ValidId` | `valid_id` 55–63 | PASS / PASS / 0 |
| V3 | Required amounts all ASCII digits → else BAD_AMOUNT (checked before contract/flag) | validate.cob 34–39 | IF-AM-* (8), IF-FULL-BAD; `IsNumeric` | `is_numeric` 50–52, 78–79 | PASS / PASS / 0 |
| V4 | Contract `----------` = absent; otherwise must be digits → malformed contract is **BAD_AMOUNT** | validate.cob 40–44 | IF-A-DASH9, IF-A-BLANK, IF-A-LETTER, IF-AM-CONTR | 80–86 | PASS / PASS / 0 |
| V5 | Contract > charges → BAD_CONTRACT (contract = charges valid) | validate.cob 51–55 | IF-A-HIGH, IF-A-HIGH-F, IF-A-EQ-C | 88–89 | PASS / PASS / 0 |
| V6 | Flag must be `Y` or `N` → else BAD_FLAG | validate.cob 56–57 | IF-FLAG-LOW, IF-FLAG-SP | 90–92 | PASS / PASS / 0 |
| V7 | No numeric move before class tests | validate.cob 45–50 | IF-AM-* (non-digit bytes never reach arithmetic) | `int()` only after `is_numeric` | PASS / PASS / 0 |

## Batch behavior (all INTERFACE)

| # | Rule | COBOL | Tests | Python | Result |
|---|---|---|---|---|---|
| B1 | LF framing, one trailing CR stripped, final line without LF is a record, empty file = 0 records | batch.cob 78–94, 105–111 | batch: LF/CRLF/mixed, missing final newline, empty, CR handling; `Framing` | `iter_records` / `_finish_line` 129–160 | PASS / PASS / 0; edge batch mixes CRLF/LF and no final newline |
| B2 | Line > 4,096 bytes (after CR strip) → fatal exit 2 | batch.cob 88, 112–115 | batch 4,096 / 4,097 tests; fatal `line-*` | 145, 158–159 | PASS / PASS / fatal MATCH |
| B3 | > 10,000 records → fatal exit 2 | batch.cob 120–123 | batch 10,000 / 10,001; fatal `records-10001` | 179–180 | PASS / PASS / fatal MATCH |
| B4 | Fresh state per record (`INITIALIZE`) | batch.cob 125–130 | ledger `sequences`; `test_state_reset_after_rejected_contract` | `process_record` creates new objects | PASS / PASS / 0 |
| B5 | Unidentifiable records get `@` + 10-digit record number | batch.cob 127–128 | IF-ID-*, IF-LEN-*; `test_duplicates` | `provisional_id` 115–116 | PASS / PASS / 0 |
| B6 | Duplicate identifiable ID fatal, even when the record is rejected | batch.cob 132–141 | batch duplicate tests; fatal `duplicate-*` | 184–187 | PASS / PASS / fatal MATCH |
| B7 | Counts by status; total = sum of payments; CSV field widths 10/15 | batch.cob 95–101, 145–157 | ledger totals check; `Formatting` | `format_result`, `format_totals`, `run_batch` | Curated/synthetic/edge outputs byte-identical |
| B8 | Usage (≠ 3 args), identical paths, unopenable files → exit 2, no stdout | batch.cob 47–61, 66–74, 180–184 | batch usage tests; fatal cases | `main` 194–215 | PASS / PASS / fatal MATCH |

## Not mapped / not tested

- Eligibility, MSP type, claim pricing, and how OTAF is determined are upstream of
  this module (rules.md) and are not implemented by either program.
- Path comparison quirks of `PIC X(1024)` (see [05-cobol-to-python.md](05-cobol-to-python.md#known-untested-differences)).
