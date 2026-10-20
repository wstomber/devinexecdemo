# 02 — Rule map: policy → COBOL → independent tests → Python → observed result

Columns: **Source type** `P` = CMS policy (public manual), `I` = demo interface
(README/rules.md, not CMS policy), `R` = observed GnuCOBOL runtime behavior.
COBOL line numbers are per file at starter `be0b00e`. Python line numbers refer
to `python/msp.py` on this branch. Test IDs are case IDs in
`tests_policy/expectations.json` or test names in `tests_policy/test_batch.py`
(Stage 2, committed before Python) and `tests_python/test_msp.py` (Stage 3).
"Observed" means the actual result on COBOL and on Python in this live run
(`evidence/live/stage2-tests-vs-cobol.log`, `stage3-python-tests.log`,
`stage4-comparison.log`).

## Payment calculation (Pub. 100-05 Ch. 5 §40.8–40.8.3)

| Rule | Source | Type | COBOL | Stage 2 tests | Python | Unit tests | Observed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| No payment if primary accepted/required as payment in full | §40.8, PDF p.78 | P | payment.cob l.16–19 | EX3-FULL-Y, FULL-OVERALL, DUP-ZERO | `calculate_payment` l.140–142 | `test_cms_ex3_and_counterfactual` | PASS / PASS; parity 0 mismatches |
| OTAF replaces charges (`claim-has-contract` branch) | §40.8.2, pp.79–80 | P | payment.cob l.20–23 | **CMS-EX3**, LIM-A-T, LIM-A-P, A-BELOW-C, EQ-A-C, DUP-CONTRACT | l.143 | `test_cms_ex3_and_counterfactual` | PASS / PASS |
| `payment-cap = min(gross, charge-basis)` | §40.8.2, §40.8.3 A | P | payment.cob l.24 | G-BELOW-C, G-ABOVE-C, LIM-C-P, LIM-C-T, EQ-ALL | l.144 | `test_each_limit_controls` | PASS / PASS |
| No payment when primary ≥ charges or gross | §40.8, p.78 | P | payment.cob l.25–28 | P-CAP-EQ, P-CAP-P1, P-CAP-M1, GROSS-ZERO | l.145–147 | `test_one_cent_boundaries_and_zero_reasons` | PASS / PASS |
| Deductible + coinsurance summed; zero if ≥ cap | §40.8.3 A | P | payment.cob l.29–33 | T-CAP-M1, T-CAP-EQ, T-CAP-P1, T-OVER-P, MAX-DEDUCT | l.148–151 | same | PASS / PASS |
| Lowest of four limits = cap − max(T, P) | §40.8.3 A, Ex. 1, Ex. 3 | P | payment.cob l.34–37 | CMS-EX1, CMS-EX3, EX3-NO-OTAF, LIM-G-P, LIM-G-T, LIM-C-P, LIM-C-T, LIM-A-T, LIM-A-P, EQ-*, P-OVER-T, T-OVER-P | l.152–153 | `test_each_limit_controls` | PASS / PASS |
| CMS-EX3 = $500 ($1,500 without OTAF) | §40.8.3 Ex. 3, pp.83–84 | P | payment.cob l.20–35 | CMS-EX3, EX3-NO-OTAF, `test_cms_ex3_headline` | l.143–153 | `test_cms_ex3_and_counterfactual` | 50,000 calc, ACCEPTED, 50,000 released in ledger, COBOL and Python (`curated-side-by-side.md` row 2) |
| Zero-reason precedence: full → primary → deductions | rules.md | I | payment.cob l.16–33 order | FULL-OVERALL, PRIM-AND-DED, ALL-ZERO | l.140–151 order | `test_one_cent_boundaries_and_zero_reasons` | PASS / PASS |
| Explicit zero contract is present; contract = charges allowed | rules.md | I | validate.cob l.40–55 | CONTRACT-0, EQ-A-C, MAX-ALL | l.110–117 | `test_contract_equal_and_zero_allowed` | PASS / PASS |
| Exact integer cents, 11-digit deductions, 15-digit totals | README | I | claim.cpy COMP-3; payment.cob l.7–10; batch.cob l.32, 49 | MAX-PAY, MAX-DEDUCT, MAX-MINUS-1, `test_10000_records_at_maximum_payment` | `digits_value` l.74; Python `int` | `test_maximums_have_no_overflow_or_float`, `test_digits_value_is_exact_integer` | PASS / PASS |

## Validation, framing, identity, batch (README interface)

| Rule | Source | Type | COBOL | Stage 2 tests | Python | Unit tests | Observed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 92-byte record, otherwise `BAD_LENGTH` | README | I | validate.cob l.11–13 | BAD-LEN-91, BAD-LEN-93, BAD-LEN-0, LEN-OVER-ID | `validate_record` l.98 | `test_length_and_reserved_identity` | PASS / PASS |
| ID 1–12 of `A–Z0–9-_`, left-justified | README | I | validate.cob l.14–33 | BAD-ID-*, ID-OVER-AMT, ABCDEFGHIJ-_ | `valid_id` l.82 | `test_id_rules` | PASS / PASS |
| Numeric class test before any MOVE; malformed contract = `BAD_AMOUNT` | README | I | validate.cob l.34–50 | AMT-*, AMT-CON-PART, AMT-CON-SP, AMT-OVER-CON | l.105–115, `is_numeric` l.70 | `test_is_numeric_uses_explicit_ascii_digits`, `test_malformed_contract_is_bad_amount` | PASS / PASS |
| Contract > charges = `BAD_CONTRACT` | README, rules.md | I | validate.cob l.51–55 | A-ABOVE-C, CON-OVR-FLAG | l.116 | `test_precedence_chain` | PASS / PASS |
| Flag exactly Y/N | README | I | validate.cob l.56–57 | FLAG-* , RESET-REJ | l.120 | `test_precedence_chain` | PASS / PASS |
| MBI 11 × `A–Z0–9` | README | I | validate.cob l.58–64 | MBI-* | l.124 | `test_precedence_chain` | PASS / PASS |
| Date numeric, month 01–12, day 01–31 (no calendar) | README | I | validate.cob l.65–68 | DATE-*, DATE-NO-CAL (flagged) | l.128–131 | `test_date_bounds` | PASS / PASS |
| Validation precedes payment-in-full | README | I | batch.cob l.148–161 | AMT-FULL-Y, RESET-FREJ | `Batch.process` l.253 | — | PASS / PASS |
| State reset per record (INITIALIZE) | README | I | batch.cob l.143 | RESET-REJ→RESET-NEXT, RESET-FREJ→RESET-FNEXT, RESET-BADID→RESET-AFTID | new `Claim` per record, l.247 | `test_state_reset_after_rejected_record` | PASS / PASS |
| `@` + 10-digit record number for invalid length/ID | README | I | batch.cob l.144–145 | BAD-LEN-*, BAD-ID-*, `test_unidentifiable_records_never_collide` | l.97 | `test_length_and_reserved_identity` | PASS / PASS |
| Duplicate identifiable ID fatal, even if rejected | README | I | batch.cob l.149–158 | `test_duplicate_valid_ids_are_fatal`, `test_duplicate_of_identifiable_rejected_record_is_fatal` | l.249–252 | `test_duplicate_identifiable_id_is_fatal` | exit 2 / exit 2; fatal partial outputs identical |
| LF/CRLF, missing final newline, blank line = record | README | I | batch.cob l.94–110, 122–128 | `test_crlf_*`, `test_blank_lines_are_records_not_eof`, `test_empty_input_is_zero_record_batch` | `input_lines` l.214 | `test_lf_crlf_and_final_line` | PASS / PASS |
| 4,096-byte bound (fatal above) | README | I | batch.cob l.104, 129–132 | `test_4096_byte_line_is_one_invalid_record`, `test_4097_byte_line_is_fatal` | l.224 | `test_transport_bound` | PASS / PASS |
| 10,000-record limit | README | I | batch.cob l.137–140 | `test_10000_*`, `test_10001_records_is_fatal` | l.245 | `test_record_limit` | PASS / PASS |
| Usage, distinct paths, file errors → exit 2 | README | I | batch.cob l.59–90, 263–267 | `test_usage_errors`, `test_missing_cwf_file_is_fatal`, `test_existing_outputs_are_replaced` | `run` l.286–322 | `test_usage_and_distinct_paths_exit_2` | PASS / PASS; 18 fatal scenarios MATCH |
| Exact CSV headers, 10/15-digit zero padding | README; baseline format | I | batch.cob l.91, 111–118, 181–187 | `test_every_record_matches_ledger`, `test_totals_reconcile_with_ledger` | `result_row` l.230, `totals_row` l.271 | `test_csv_formatting` | Outputs byte-identical on all four batches |

## CWF pre-payment check (Pub. 100-04 Ch. 27 §20/§20.2.2; Pub. 100-05 Ch. 5 §10.1)

| Rule | Source | Type | COBOL | Stage 2 tests | Python | Unit tests | Observed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Only valid (PAID/ZERO) claims are sent; invalid → `NOT_SENT`/`CLAIM_INVALID` | Ch. 27 §20 (prices first, then CWF); rules.md | P+I | batch.cob l.162–167 | INV-UNK-MBI, all INVALID rows | `Batch.process` l.255 | — | PASS / PASS |
| ZERO claims still sent | rules.md | I | batch.cob l.162 | EX3-FULL-Y, DUP-ZERO, MSP-ZERO, ZERO-NOT-ENT | l.255 | `test_zero_claim_is_checked` | PASS / PASS |
| 1. Entitled on the date of service (inclusive; MBI must be on file) | Ch. 27 §20 | P | cwf.cob l.22–32 | ENT-START-M1, ENT-START, ENT-END, ENT-END-P1, ENT-NOT-FILE, ENT-OPEN, EX3-ENDED | `cwf_check` l.159–162 | `test_not_entitled_keeps_calculated_payment` | PASS / PASS |
| 2. Duplicate of posted history (MBI + DOS + covered charges) | Ch. 27 §20 | P (+I key) | cwf.cob l.33–41 | DUP-EXACT, DUP-CENT-LO/HI, DUP-DAY-BEF/AFT, DUP-CONTRACT, DUP-OTH-MBI, BATCH-SAMEKY | l.163–165 | `test_duplicate_matches_history_exactly` | PASS / PASS |
| 3. MSP period covers DOS and primary = 0 → `MSP_PRIMARY_NOT_BILLED` | Ch. 5 §10.1; rules.md | P+I | cwf.cob l.42–48 | MSP-START-M1, MSP-START, MSP-END, MSP-END-P1, MSP-PRIM-1C, MSP-ZERO | l.166–168 | `test_msp_primary_not_billed` | PASS / PASS |
| Check order: entitlement → duplicate → MSP | rules.md | I | cwf.cob order | ENT-BEF-DUP, ENT-NOT-FILE, MSP-ENT-1ST, MSP-ENT-IN, DUP-BEF-MSP | l.159–168 order | — | PASS / PASS |
| Accepted → `DISPOSITION_01`, released = calculated; rejected keeps payment, released 0 | Ch. 27 §20.2.2; README | P+I | cwf.cob l.18, 49–51 | every CWF case, CMS-EX3 | l.158, 169–170 | `test_accepted_releases_payment` | PASS / PASS |
| CWF file layout, ≤1,000 B / H, malformed is fatal | README | I | batch.cob l.189–240 | `test_malformed_cwf_records_are_fatal`, `test_1000_*` | `parse_cwf` l.183 | `test_malformed_is_fatal` | PASS / PASS |
| First `B` per MBI wins | — | R | cwf.cob l.22–27 | — | `setdefault` l.201 | `test_first_beneficiary_wins` | edge batch parity |
| CWF line read: CR dropped, >64 bytes truncated, padded | — | R | batch.cob l.18–19, 196–204 (GnuCOBOL 3.1.2 runtime) | — | `cwf_records` l.173 | `test_runtime_line_sequential_behaviour` | edge batch parity |

## Open review items

- `DATE-NO-CAL`: the interface accepts 2025-02-30. Both programs agree on this.
  It may be a policy gap.
- The CWF reject codes and the demo's MSP-not-billed rule are simplifications. The
  reverse MSP case and all other CWF edits are out of scope (see rules.md).
- The Python port does not reproduce COBOL's `pic x(1024)` path truncation or
  its trailing-space-insensitive path equality. Neither is tested.
