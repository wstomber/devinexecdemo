# Rule map: policy → COBOL → independent test → Python → result

Every row traces one rule from where it comes from, to where the legacy code
implements it, to the test that pins it down independently, to the Python that
replaces it, to the observed result. **Source** says whether the rule is CMS
policy (Pub. 100-05, Ch. 5, §40.8–40.8.3; see `docs/rules.md`) or a decision
of this synthetic demo's interface (`README.md`). Interface rules are not CMS
facts. They are kept exactly so the Python is a drop-in replacement.

Test IDs refer to cases in `tests_policy/expectations.json` (Layer A) and to
classes in `tests_python/test_msp_units.py` (Layer B). "Parity" refers to the
COBOL-vs-Python comparisons in `evidence/rehearsal/stage4-comparison/`
(Layer C).

## Payment rules

| # | Rule | Source | COBOL | Layer A tests | Python | Layer B tests | Result |
|---|---|---|---|---|---|---|---|
| P1 | No secondary payment when the primary payment was accepted as payment in full (`full=Y`) | Policy §40.8 (p. 78) | `payment.cob` 16–19 | FULL-PAID, FULL-PRIM | `calculate` (`paid_in_full` branch) | `CalculateTests.test_zero_reason_boundaries` | PASS · parity |
| P2 | A lower obligatory contractual acceptance amount (OTAF) replaces covered charges as the charge basis. It is not subtracted and it is not a fifth limit | Policy §40.8.2 (pp. 79–80) | `payment.cob` 20–23 (`claim-has-contract` branch) | CMS-EX3, EX3-NO-OTAF, OTAF-T, OTAF-EQ-GRS, OTAF-EQ-CHG, OTAF-PRIM-AT, OTAF-ZERO, MAX-OTAF | `charge_basis` | `test_cms_ex3_contract_replaces_charges_and_pays_500`, `test_cms_ex3_without_contract_would_pay_1500` | PASS · parity |
| P3 | The payment cap is the lower of gross Medicare payable and the charge basis | Policy §40.8.2 | `payment.cob` 24 (`function min`) | GROSS-P, GROSS-T, CHARGE-P, CHARGE-T, CAP-1C, EQUAL-LIMITS, GROSS-ZERO | `payment_cap` | `test_payment_cap_is_lower_of_gross_and_basis` | PASS · parity |
| P4 | No payment when the primary payment is at or above the cap | Policy §40.8 (p. 78) | `payment.cob` 25–28 | PRIM-AT-CAP, PRIM-1C-OVER, PRIM-1C-UNDR, MAX-PRIMARY | `calculate` | `test_zero_reason_boundaries` | PASS · parity |
| P5 | Deductions = deductible + coinsurance; no payment when they are at or above the cap | Policy §40.8.2 | `payment.cob` 29–33 | DED-AT-CAP, DED-1C-UNDR, MAX-DEDUCT | `calculate` | `test_zero_reason_boundaries`, `test_maximum_amounts_are_exact_integers` | PASS · parity |
| P6 | Otherwise pay cap − max(deductions, primary). This equals the lowest of the four §40.8.2 limits | Policy §40.8.2, §40.8.3 A | `payment.cob` 34–37 | CMS-EX1, CMS-EX3, T-OVER-P-1C, P-OVER-T-1C, NO-PRIMARY, MAX-PAY; `LedgerArithmeticAudit` | `calculate` | `test_larger_of_deductions_or_primary_is_subtracted` | PASS · parity |
| P7 | Exact integer cents. No binary floating point anywhere | Interface (README) + policy amounts | `pic 9(10) comp-3` packed decimal in `claim.cpy`, `payment.cob` 5–8 | MAX-PAY, MAX-OTAF (1-cent result at 10-digit maximum) | Python `int` throughout; `int(bytes)` parse | `test_maximum_amounts_are_exact_integers` | PASS · parity |
| P8 | Zero-reason precedence: PAYMENT_IN_FULL, then PRIMARY_AT_CAP, then DEDUCTIONS_AT_CAP | Interface (README) | `payment.cob` 15–33 (order of the `if … goback` blocks) | FULL-PRIM, PRIM-AND-DED | order of branches in `calculate` | `test_zero_reason_boundaries` ("full precedes primary", "primary precedes deductions") | PASS · parity |

## Validation rules (all interface decisions)

| # | Rule | COBOL | Layer A tests | Python | Layer B tests | Result |
|---|---|---|---|---|---|---|
| V1 | A record is exactly 92 bytes after framing, else `BAD_LENGTH` | `validate.cob` 13 | @…31, @…32, @…33 | `validate` (`RECORD_LENGTH`) | `ValidateTests.test_length_and_identity` | PASS · parity |
| V2 | ID: uppercase A–Z, 0–9, `-`, `_`, left-aligned, right-padded with spaces, not blank, else `BAD_ID` | `validate.cob` 36–55 | @…34, @…35, @…36, @…37 | `valid_claim_id` (`ID_CHARACTERS`) | `test_length_and_identity` | PASS · parity, incl. NUL/tab/high-byte edge batch |
| V3 | The five amount fields must be all digits (COBOL `NUMERIC` class test), else `BAD_AMOUNT`. Nothing defaults to zero | `validate.cob` 56–61 | AMT-SPACE, AMT-PLUS | `is_numeric` (`DIGITS`) | `test_numeric_class_matches_cobol` | PASS · parity |
| V4 | Contract is exactly `----------` (absent) or all digits, else `BAD_AMOUNT` | `validate.cob` 62–66 | OTAF-ALPHA | `validate` (`ABSENT_CONTRACT`) | `test_numeric_class_matches_cobol` | PASS · parity |
| V5 | A supplied contract above covered charges is `BAD_CONTRACT`. An equal contract or a zero contract is allowed | `validate.cob` 73–77 | OTAF-1C-HIGH, OTAF-EQ-CHG, OTAF-ZERO | `validate` | `test_contract_range_and_flag` | PASS · parity |
| V6 | Flag is exactly `Y` or `N`, else `BAD_FLAG` | `validate.cob` 78–79 | FLAG-LOWER, FLAG-SPACE | `validate` (`FULL_FLAG`) | `test_contract_range_and_flag` | PASS · parity |
| V7 | Rejection precedence: LENGTH → ID → AMOUNT → CONTRACT → FLAG | order of `move … to claim-reason` / `goback` in `validate.cob` | @…46, PREC-AMT-FLG, PREC-OTAF-FL | order of checks in `validate` | `test_rejection_precedence` | PASS · parity |
| V8 | No numeric conversion before the class tests pass | `validate.cob` 67–72 | AMT-SPACE, AMT-PLUS | `int(...)` only after `is_numeric` | `test_numeric_class_matches_cobol` | PASS · parity |

## CWF pre-payment check (runs after the payment is calculated)

Sources: CMS Pub. 100-04 Ch. 27 §20, §20.2.2 (price, then CWF pre-payment
validation and authorization, then pay or deny); Pub. 100-05 Ch. 5 §10.1 (MSP
records on CWF). Reject codes are demo-defined; only disposition 01 is a CWF code.

| # | Rule | COBOL | Layer A cases | Python | Result |
|---|---|---|---|---|---|
| C0 | MBI is 11 of `A–Z 0–9` (`BAD_MBI`); service date is 8 digits with month 01–12 and day 01–31 (`BAD_DATE`). Invalid claims are not sent to CWF (`NOT_SENT`/`CLAIM_INVALID`, 0 released) | `validate.cob` 58–71; `batch.cob` 163–167 | CWF-BAD-MBI, CWF-MBI-SPC, CWF-BAD-MON | `validate`, `Batch.process` | PASS · parity |
| C1 | MBI not on file, or service date outside the inclusive entitlement period → `NOT_ENTITLED` | `cwf.cob` 17–32 | CWF-NOFILE, CWF-ENT-FROM, CWF-ENT-TO, CWF-ENT-BEF, CWF-ENT-AFT | `cwf_check` | PASS · parity |
| C2 | Same MBI, service date and charges as a posted claim (`H` record) → `DUPLICATE` | `cwf.cob` 33–41 | CWF-DUP, CWF-DUP-AMT, CWF-DUP-DOS, CWF-PREC-DUP | `cwf_check` | PASS · parity |
| C3 | MSP period covers the service date and primary payment is 0 → `MSP_PRIMARY_NOT_BILLED` | `cwf.cob` 42–48 | CWF-MSP-NOPR, CWF-MSP-PAID, CWF-MSP-FROM, CWF-MSP-TO, CWF-MSP-OUT | `cwf_check` | PASS · parity |
| C4 | Otherwise `ACCEPTED` / `DISPOSITION_01` and released = calculated payment; any rejection releases 0 but keeps the calculated payment; ZERO claims are still checked | `cwf.cob` 49–51 | CMS-EX3, CWF-ZERO-REJ, CWF-ZERO-ACC, CWF-PREC-ENT | `cwf_check`, `Batch` totals | PASS · parity |
| C5 | CWF reference file: `B` and `H` records; any malformed record, or more than 1,000 of either, is fatal (exit 2) | `batch.cob` 189–230 (`load-cwf`, `parse-cwf`) | malformed-CWF batch tests | `load_cwf` | PASS · fatal parity |

## Batch rules (all interface decisions)

| # | Rule | COBOL | Layer A tests | Python | Layer B tests | Result |
|---|---|---|---|---|---|---|
| B1 | Exactly four distinct positional paths `INPUT CWF OUTPUT TOTALS`, else exit 2; the Python CLI also accepts optional `--summary-json PATH` | `batch.cob` 59–61 (four paths only) | `test_usage_errors_exit_2` | `main`, `parse_args` | `MainTests.test_usage_and_failure_exit_2` | PASS |
| B2 | Framing: LF; one trailing CR stripped; final line without newline is a record; blank line is a `BAD_LENGTH` record | `batch.cob` 78–94, 105–118 | `test_crlf_and_missing_final_newline_match_lf`, @…33 | `read_records`, `finish_line` | `FramingTests` | PASS · parity (edge batch: no final newline, bare CR, CRLF) |
| B3 | A line over 4,096 bytes is fatal. A 4,096-byte line is an ordinary `BAD_LENGTH` record | `batch.cob` 88, 112–115 | `test_line_of_4096_bytes_is_invalid_record_and_4097_is_fatal` | `read_records` (`MAX_LINE_BYTES`) | `test_transport_limit`, `test_line_spanning_read_chunks` | PASS · fatal parity |
| B4 | More than 10,000 records is fatal | `batch.cob` 120–123 | `test_10000_records_succeed_and_10001_is_fatal` | `Batch.process` (`MAX_RECORDS`) | `BatchTests.test_record_limit` | PASS · fatal parity |
| B5 | All raw and parsed state resets for every record, including after a rejection | `batch.cob` 125–126 (`initialize claim-interface`) | RESET-SRC → RESET-NEXT; `test_state_resets_after_rejected_contract_and_payment_in_full` | new immutable `Claim`/`Result` per record | `test_no_state_carries_between_records` | PASS · parity |
| B6 | An unidentifiable record gets provisional ID `@` + 10-digit record number | `batch.cob` 127–128 | @…31–@…46; `test_unidentifiable_rejections_never_collide` | `validate` (`provisional_id`) | `test_length_and_identity` | PASS · parity |
| B7 | A duplicate identifiable ID (valid or rejected) is fatal. `@` IDs never collide | `batch.cob` 132–141 | `test_duplicate_valid_id_is_fatal`, `test_duplicate_identifiable_rejected_id_is_fatal` | `Batch.process` (`seen_ids`) | `test_duplicate_identifiable_ids_are_fatal_but_reserved_ids_are_not` | PASS · fatal parity |
| B8 | Counts: PAID / ZERO / INVALID; total = sum of payments (15-digit) | `batch.cob` 145–150, 95–101 | `test_totals_match_ledger_and_rows`, `test_ledger_totals_follow_from_rows` | `Batch.process`, `Batch.totals_row` | `test_counts_totals_and_formatting` | PASS · parity |
| B9 | Output CSVs: exact headers, 10-digit zero-padded `record_no`/`payment_cents`, trimmed text fields, LF endings | `batch.cob` 75, 95, 98–100, 151–156 (`pic 9(10)` in `STRING`, `function trim`) | every ledger test compares exact rows | `result_row`, `RESULTS_HEADER`, `TOTALS_HEADER` | `test_counts_totals_and_formatting`, `test_success_writes_exact_files` | PASS · byte-identical |
| B10 | Any fatal error: exit 2, "discard outputs" on stderr, totals not written. The caller must not use partial files | `batch.cob` 180–184 (`fatal-io`, `stop run`) | `test_missing_input_exits_2` | `FatalBatchError` → `main` returns 2 | `test_usage_and_failure_exit_2` | PASS · fatal parity (`fatal-parity.md`) |
| B11 | Optional `--summary-json PATH` writes integer batch counts and payment cents as JSON only after successful CSV output; destination must differ from all positional paths. Interface — synthetic exercise, not CMS policy | none (Python-only; no COBOL equivalent) | — (policy tests unchanged) | `parse_args`, `summary_path_collides`, `Batch.summary`, `write_summary`, `run` | `test_no_flag_csv_bytes_and_flag_preserves_csv`, `test_summary_contract_matches_totals`, `test_integer_cents_are_exact`, `test_empty_batch_summary_matches_totals`, `test_mixed_validity_counts_match_totals`, `test_option_positions_and_equals_form`, `test_fatal_duplicate_does_not_write_or_replace_summary`, `test_summary_path_collisions_are_rejected_before_open`, `test_unwritable_summary_destinations_fail_cleanly`, `test_summary_option_usage_errors` (`tests_python/test_summary_json.py`) | PASS · CSV parity unchanged |

## Results behind the "Result" column

- Layer A, the hand-derived ledger run against COBOL before any Python existed:
  `evidence/rehearsal/stage2-pre-migration-tests/`. The same tests passed
  against Python, unchanged: `stage3-python/policy-tests-python-first-run.log`.
- Layer B, focused Python unit tests: `stage3-python/python-unit-tests.log`.
  Every correction and its cause is in `stage3-python/corrections.md`.
- Layer C (calculated payment, CWF decision and released amount): curated 33/33,
  synthetic 1,000/1,000, adversarial edge batch 2,099/2,099, 22 fatal paths,
  all byte-identical; fatal cases identical (`stage4-comparison/`).
  `tools/verify.py` also reports PASS for the curated and synthetic batches.
