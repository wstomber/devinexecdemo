# 02 — Rule map: policy → COBOL → tests → Python → result

Source column: **P** = public CMS policy (Pub. 100-05 Ch. 5 §40.8–40.8.3; CWF
rules Pub. 100-04 Ch. 27 §20, Pub. 100-05 Ch. 5 §10.1, as interpreted in
[`docs/rules.md`](../rules.md)); **I** = demo interface contract in
[`README.md`](../../README.md) (not CMS policy); **R** = GnuCOBOL runtime
behavior observed in this run and preserved.

Tests: ledger groups are in [`tests_policy/expectations.json`](../../tests_policy/expectations.json)
(`group` field); batch tests are in `tests_policy/test_batch_interface.py`; unit
tests in `tests_python/test_msp_units.py`. Result = state at the PR head: Stage 2
tests pass on COBOL ([log](../../evidence/live/stage2-cobol-tests.log)) and on
Python ([log](../../evidence/live/stage3-python-tests.log)); comparisons in
[`evidence/live/comparison/`](../../evidence/live/comparison/README.md) are 0 mismatches.

| # | Rule | Src | COBOL | Independent tests | Python (`python/msp.py`) | Result |
|---|---|---|---|---|---|---|
| 1 | Payment = lowest of G−P, G−T, B−P, B−T, i.e. `min(G,B) − max(T,P)` | P §40.8.2, §40.8.3 A | `payment.cob` 24, 29, 34–35 | `limit-controls`, `equal-limits`, `one-cent`; `PaymentTests` | `calculate_payment` 107–124 | pass, MATCH |
| 2 | Contract/OTAF replaces charges as the basis (B) | P §40.8.2 | `payment.cob` 20–23 | `CMS-EX3`, `EX3-NO-OTAF`, `LIM-OTAF-T`, `EQ-OTAF-*`, `OTAF-*` | `charge_basis` in `calculate_payment` | pass, MATCH |
| 3 | CMS Example 3 = $500; without OTAF $1,500; Example 1 = $1,500 | P §40.8.3 Ex. 1, Ex. 3 | `payment.cob` 20–37 | `published`; `test_cms_example_3_is_500_dollars_released`; `test_cms_example_3` | `calculate_payment` | 50,000 calc / ACCEPTED / 50,000 released in ledger, COBOL, Python |
| 4 | Primary paid in full → no secondary payment | P §40.8 | `payment.cob` 16–19 | `PIF`, `PIF-FIRST`, `PR-INV-PIF` | `calculate_payment` first branch | pass, MATCH |
| 5 | No negative payment; primary or deductions at/above cap → 0 | P §40.8 | `payment.cob` 25–33 | `zero-reasons`, `P-CAP-*`, `T-CAP-*` | `calculate_payment` | pass, MATCH |
| 6 | Zero-reason precedence `PAYMENT_IN_FULL` > `PRIMARY_AT_CAP` > `DEDUCTIONS_AT_CAP` | I | `payment.cob` 16–33 order | `PIF-FIRST`, `PRIM-FIRST`, `ALL-ZEROES` | same order | pass, MATCH |
| 7 | Exact integer cents; 10-digit amounts; 11-digit T; 15-digit totals | I | `claim.cpy` PIC 9(10) COMP-3; `payment.cob` 6–7; `batch.cob` totals PIC 9(15) | `maximums`; `test_10000_records_with_maximum_total` | `int` only | pass, MATCH |
| 8 | 92-byte record, else `BAD_LENGTH` (blank line included) | I | `validate.cob` 12–13 | `V-SHORT`, `V-LONG`, `V-BLANK`, `test_blank_lines_are_records_not_eof` | `validate` 58–60 | pass, MATCH |
| 9 | ID `[A-Z0-9_-]{1,12}` left-justified, else `BAD_ID` + `@`-provisional ID | I | `validate.cob` 14–33; `batch.cob` 145 | `V-ID-*`, `MAX12CHAR-_0`, `Q`, `test_provisional_ids_never_collide` | `validate`, `Claim.__init__` | pass, MATCH |
| 10 | Amounts only ASCII digits; malformed contract is `BAD_AMOUNT` | I | `validate.cob` 34–44 (`IS NUMERIC`) | `A-*` cases; `NumericTests` | `is_numeric` 33 | pass, MATCH |
| 11 | Contract > charges → `BAD_CONTRACT` | I | `validate.cob` 51–55 | `C-HIGH`, `EQ-OTAF-C` | `validate` | pass, MATCH |
| 12 | Flag `Y`/`N` → else `BAD_FLAG` | I | `validate.cob` 56–57 | `F-LOWER`, `F-SPACE` | `validate` | pass, MATCH |
| 13 | MBI 11 × `[A-Z0-9]` → else `BAD_MBI` | I | `validate.cob` 58–64 | `M-*`, `CWF-BAD-MBI` | `validate` | pass, MATCH |
| 14 | DOS 8 digits, month 01–12, day 01–31, no calendar check → else `BAD_DATE` | I | `validate.cob` 65–68 | `D-*` (`D-FEB31` valid), `CWF-BAD-DATE` | `validate` | pass, MATCH |
| 15 | Validation precedence LENGTH > ID > AMOUNT > CONTRACT > FLAG > MBI > DATE | I | `validate.cob` order | `precedence` | `validate` order | pass, MATCH |
| 16 | State reset after every record | I | `batch.cob` 143 `INITIALIZE` | `state-reset` | new `Claim` per record | pass, MATCH |
| 17 | Duplicate identifiable ID (even on rejected record) is fatal | I | `batch.cob` 149–157 | `DuplicateIdTests`; fatal `duplicate-*` | `run_batch` `seen_ids` | pass, MATCH |
| 18 | LF ends a line; one trailing CR removed; last line without LF counts; >4,096 bytes fatal | I | `batch.cob` 93–135 | `FramingTests`; unit `FramingTests` | `read_lines` 192–210 | pass, MATCH |
| 19 | >10,000 records fatal | I | `batch.cob` 137–140 | `test_10001_*` | `run_batch` `MAX_RECORDS` | pass, MATCH |
| 20 | Only valid (PAID/ZERO) claims sent to CWF; invalid → `NOT_SENT`/`CLAIM_INVALID` | P §20 (pre-payment after pricing) / I | `batch.cob` 159–166 | `CWF-INV-*`, `CWF-ZERO-*` | `run_batch` | pass, MATCH |
| 21 | Entitlement: MBI on file and DOS within inclusive period → else `NOT_ENTITLED` | P Ch. 27 §20; Ch. 5 §10.1 | `cwf.cob` 18–32 | `cwf-entitlement` | `cwf_check` 127–133 | pass, MATCH |
| 22 | Duplicate: same MBI + DOS + charges in `H` history (not in-batch) | P Ch. 27 §20 | `cwf.cob` 33–41 | `cwf-duplicate` (incl. `CWF-BATCH-A/B`) | `cwf_check` history set | pass, MATCH |
| 23 | MSP period covers DOS and primary = 0 → `MSP_PRIMARY_NOT_BILLED` | P Ch. 5 §10.1 | `cwf.cob` 42–48 | `cwf-msp` | `cwf_check` | pass, MATCH |
| 24 | Check order entitlement > duplicate > MSP | I | `cwf.cob` order | `cwf-precedence` | `cwf_check` order | pass, MATCH |
| 25 | CWF rejection keeps `payment_cents`; `released_cents` = payment only if ACCEPTED | I | `cwf.cob` 18, 51 | `test_ledger_is_self_consistent`; `CwfTests` | `cwf_check` 141 | pass, MATCH |
| 26 | CWF file: B 44 / H 30 bytes, bad record or >1,000 of a type fatal; empty file OK | I | `batch.cob` 189–237 | `CwfFileTests` | `load_cwf` 159–189 | pass, MATCH |
| 27 | CWF LINE SEQUENTIAL quirks: all CR dropped, bytes past col 64 ignored, first `B` per MBI wins | R | `batch.cob` 8–9, 18–19, `cwf.cob` 22–27 | edge batch (comparison); unit `test_line_sequential_reading` | `cwf_records` 144–156 | MATCH (not in Stage 2 ledger) |
| 28 | Usage / distinct paths / I/O failure → exit 2, nothing on stdout | I | `batch.cob` 60–76, 263–267 | `UsageTests`; fatal paths | `main` 263– | pass, MATCH |
| 29 | Totals line counts and sums | I | `batch.cob` 112–118, 167–180 | `test_totals_reconcile_with_ledger` | `run_batch` | pass, MATCH |

Not covered: Pub. 100-05 Example 4 (excluded, see `docs/rules.md`
"Published inconsistency"), real CMS pricing, real CWF dispositions or edits
beyond the three demo-defined checks.
