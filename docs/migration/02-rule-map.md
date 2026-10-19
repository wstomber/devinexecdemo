# 02 — Rule map: policy → COBOL → tests → Python → result

Source column: **P** = CMS policy (Pub. 100-05 Ch. 5 §40.8–40.8.3; CWF: Pub. 100-04 Ch. 27 §20,
Pub. 100-05 Ch. 5 §10.1); **I** = README / `docs/rules.md` interface decision (reason
codes, layouts and CWF codes are demo-defined in every row). Ledger = case IDs in
`tests_policy/expectations.json`; Batch = `tests_policy/test_batch.py`; Unit =
`tests_python/test_msp.py`. Result = Stage 2 run vs COBOL (`evidence/live/stage2-tests-cobol.log`),
Stage 3 run vs Python (`evidence/live/stage3-tests-policy-python.log`), and Stage 4 parity
(`evidence/live/stage4/README.md`: curated 33/33, synthetic 1000/1000, edge 2099/2099, fatal 22/22).

| # | Rule | Src | COBOL | Tests | Python (`python/msp.py`) | Result |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Payment = max(0, min(G−P, G−T, B−P, B−T)), integer cents | P | payment.cob 24, 29, 34–35 | Ledger LIM-*, CENT-*, CMS-EX1; Unit `test_payment_branches` | `calculate_payment` 161–174 | pass both; parity |
| 2 | OTAF replaces charges (B = A); CMS-EX3 = $500, without OTAF $1,500 | P | payment.cob 20–23 | Ledger CMS-EX3, EX3-NO-OTAF, LIM-A-T, CENT-A-*; Unit `test_contract_basis_and_cms_example_3` | `calculate_payment` (`basis`) | 50000 / 150000 in ledger, COBOL, Python |
| 3 | No payment when primary accepted as payment in full | P | payment.cob 16–19 | Ledger FULL-Y, FULL-Y-AND-P-HIGH, CWF-ZERO-SENT | `calculate_payment` first test | pass; parity |
| 4 | Zero precedence: full, primary at cap, deductions at cap | I | payment.cob 16–33 | Ledger CENT-P-AT/ABOVE, CENT-T-AT/ABOVE, P-AND-T-AT-CAP, ALL-ZERO, GROSS-ZERO | `calculate_payment` order | pass; parity |
| 5 | Amount maxima 9,999,999,999; D+K in 11 digits; totals 15 digits | I | claim.cpy 21–28; payment.cob 6; batch.cob 32, 49 | Ledger MAX-*; `test_output_widths` | Python `int`; `_totals_line` 345 | pass; parity |
| 6 | Validation precedence LENGTH, ID, AMOUNT, CONTRACT, FLAG, MBI, DATE | I | validate.cob 11–73 | Ledger BAD-* (incl. two-fault precedence pairs); Batch `test_byte_level_validation`; Unit `test_validation_precedence` | `validate_claim` 95–158 | pass; parity incl. 2,000 mutations |
| 7 | ASCII-digit-only amounts; malformed contract = BAD_AMOUNT | I | validate.cob 34–44 | Ledger BAD-AMT-*, BAD-CTR-PARTDASH/SPACES; Unit `test_ascii_digits_rejects_non_ascii_and_non_digits` | `ascii_digits` 75 | pass; parity |
| 8 | Provisional `@`+10-digit ID for BAD_LENGTH/BAD_ID; `@` never valid | I | batch.cob 144–145; validate.cob 14–33 | Ledger BAD-LEN-*, BAD-ID-*; Unit `test_claim_id_rules` | `_provisional_id` 91, `valid_claim_id` 79 | pass; parity |
| 9 | Duplicate identifiable ID fatal, even on rejected record | I | batch.cob 149–158 | Batch `test_duplicate_ids_and_invalid_ids`; fatal duplicate-id, duplicate-id-rejected | `_process_record` 352 | pass; fatal parity |
| 10 | Per-record state reset | I | batch.cob 143 | Ledger STATE-REJ-CTR → STATE-AFTER, STATE-AFTER-MBI (batch order) | new `Claim` per record | pass; parity |
| 11 | Framing: LF, one trailing CR, final line without LF, blank line = record, empty file = 0 records | I | batch.cob 94–135 | Batch `test_crlf_…`, `test_empty_input`, `test_blank_lines_…`; Unit `test_lf_crlf_lone_cr_and_empty_stream` | `iter_framed_records` 260, `_finish_line` 281 | pass; parity |
| 12 | 4,096-byte line limit (4,098th byte fatal without message), 10,000 records | I | batch.cob 104, 129–132, 137–140 | Batch `test_line_lengths_…`, `test_record_count_limit`; fatal line-4097/4098/5000, records-10001 | same; `_run_batch` record check | pass; fatal parity |
| 13 | Only PAID/ZERO claims go to CWF; invalid = NOT_SENT/CLAIM_INVALID | P/I | batch.cob 159–167 | Ledger CWF-INVALID-NOT-SENT, CWF-ZERO-SENT, CWF-ZERO-MSP, all BAD-* | `_process_record` | pass; parity |
| 14 | Entitlement: MBI on file, DOS within from..to inclusive | P | cwf.cob 18–32 | Ledger CWF-NOT-ON-FILE, CWF-ENT-START(-1), CWF-ENT-END(+1), CWF-ENT-OPEN, EX3-NOT-ENT | `check_cwf` 231–257 | pass; parity |
| 15 | Duplicate = posted `H` with same MBI, DOS, charges (not batch claims) | P/I | cwf.cob 33–41 | Ledger CWF-DUP, -CENT+, -CENT-, -DAY+, -OTHER-MBI, CWF-BATCH-A/B, EX3-DUP | `check_cwf` | pass; parity |
| 16 | MSP period covers DOS (inclusive) and primary = 0 → not billed | P | cwf.cob 42–48 | Ledger CWF-MSP-START/END/BEFORE/AFTER, CWF-MSP-P-1C, EX3-NOT-BILLED | `check_cwf` | pass; parity |
| 17 | Check order entitlement → duplicate → MSP | P/I | cwf.cob order | Ledger CWF-ENT-OVER-DUP, CWF-DUP-OVER-MSP | `check_cwf` order | pass; parity |
| 18 | Released = payment if ACCEPTED else 0; payment kept on reject | I | cwf.cob 18, 49–51; batch.cob 172–173 | every ledger row; ledger integrity test | `check_cwf` return; `_run_batch` totals | pass; parity |
| 19 | CWF file format, ≤1,000 B / H, malformed = fatal; read before input | I | batch.cob 81, 189–240 | Batch `test_missing_and_malformed_cwf_files`, `test_cwf_record_limits_…`; Unit `test_cwf_*`; fatal malformed-cwf-*, cwf-1001-* | `parse_cwf` 187, `_cwf_lines` 177 | pass; fatal parity |
| 20 | CSV contract: headers, 10/15-digit fields, trimmed text, LF, silent stdout | I | batch.cob 91, 111–118, 181–187 | `test_output_widths`, `test_empty_input` (exact bytes) | `_result_line` 331, `_totals_line` 345 | byte-identical results/totals on all three batches |
| 21 | Usage, distinct paths, fatal message + exit 2, open order and file statuses | I | batch.cob 59–92, 263–267 | Batch `test_usage_and_path_errors`; fatal usage-*, same-paths, missing-*, *-dir-missing | `main` 489, `_run_batch` 368, `_write_fatal` 323 | fatal parity 22/22 (stderr incl. libcob warnings) |

Not covered: coverage, pricing and primary allocation (upstream inputs); real CWF behaviour
beyond these three synthetic checks; runtime I/O errors other than the tested ones.
