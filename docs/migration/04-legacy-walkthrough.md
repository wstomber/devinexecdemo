# 04 — Walking the COBOL program, then tracing CMS-EX3

This walkthrough follows the actual source statements. The numbers in the CMS-EX3
trace are **cents**, not dollars. The code is a synthetic educational subset,
not CMS production software.

## `batch.cob`: main, framing, and record processing

### `main` (`cobol/batch.cob:45-104`)

1. Lines 47–61 read the argument count and three paths. Anything other than
   `INPUT OUTPUT TOTALS`, or any identical path strings, exits with code 2.
2. Lines 62–74 configure the sequential one-byte input and open the result and
   totals files. A failed open calls `fatal-io`.
3. Lines 75–76 write the result CSV header.
4. Lines 77–94 repeatedly read one byte. Status `"00"` means the byte is
   available; LF runs `finish-line`, while other bytes are appended to the
   current buffer. Status `"10"` is EOF: a nonempty final partial line is
   finished, then the loop ends. Other statuses are fatal.
5. Lines 95–101 write the totals header and fixed-width totals row. Lines
   102–104 close the files and return success.

### `finish-line` (`cobol/batch.cob:105-118`)

1. Lines 106–110 remove one trailing CR when it is present before the line
   terminator.
2. Lines 112–115 reject an over-limit line through `fatal-io`.
3. Line 116 dispatches the physical line to `process-record`.
4. Lines 117–118 reset the length and buffer for the next line. A blank physical
   line still calls `process-record`; only the EOF branch ends input.

### `process-record` (`cobol/batch.cob:119-157`)

1. Lines 120–124 reject record 10,001, then increment the record number.
2. Lines 125–131 initialize the shared claim record, install a provisional
   `@`-plus-record-number ID, copy the raw 73-byte slice and actual line length,
   then call `validate-claim`.
3. Lines 132–141 check every identifiable ID against the prior-ID table. The
   check is independent of payment status, so an ID on a rejected record can
   still cause a later duplicate to abort the batch.
4. Lines 142–144 call the payment subprogram only for `VALID` records.
5. Lines 145–150 increment exactly one status count and add the record's
   payment to the batch total.
6. Lines 151–157 move the payment to its display field, assemble the CSV row,
   and write it. `write-result` at lines 158–160 treats a non-`"00"` status as
   fatal.

## `validate.cob`: rejection order and safe conversion

`validate-record` begins at `cobol/validate.cob:10`.

1. Lines 11–13 set the default status/reason and reject lengths other than 73
   with `BAD_LENGTH`.
2. Lines 14–33 test the 12-byte ID: it cannot be all spaces; allowed characters
   are uppercase letters, digits, `-`, and `_`; after the first padding space,
   only spaces are allowed. Failure keeps the provisional ID. A passing ID is
   copied to `claim-id` at line 33.
3. Lines 34–44 check C, G, P, D, and K as numeric text. The contract must be
   the exact absent sentinel or numeric text. A malformed contract is
   `BAD_AMOUNT`; only a syntactically valid contract is copied and marked
   present.
4. Lines 45–50 convert the already-checked amount fields. No numeric move or
   arithmetic occurs before the class checks.
5. Lines 51–55 reject a present contract greater than covered charges as
   `BAD_CONTRACT`.
6. Lines 56–60 accept exactly `Y` or `N`; otherwise the result remains invalid
   with `BAD_FLAG`. Success sets `VALID` and clears the reason.

## `payment.cob`: cap and secondary payment

`calculate-prospective-payment` begins at `cobol/payment.cob:12`.

1. Lines 13–14 initialize payment to zero and status to `ZERO`.
2. Lines 16–19 handle `full=Y` first: reason `PAYMENT_IN_FULL`, then return.
3. Lines 20–24 choose covered charges as the default basis, replace it with the
   contract amount when present, then set `payment-cap = min(gross, basis)`.
4. Lines 25–28 return zero with `PRIMARY_AT_CAP` when primary payment reaches
   or exceeds the cap.
5. Lines 29–33 sum deductible and coinsurance, then return zero with
   `DEDUCTIONS_AT_CAP` when the combined amount reaches the cap.
6. Lines 34–37 subtract the larger of deductions and primary payment from the
   cap, set `PAID`, and use `SECONDARY_PAYABLE`.
7. Line 38 returns the shared record to the caller.

The explicit zero branches occur before subtraction, so the unsigned payment
field never has to represent a negative result.

## CMS-EX3 traced through the payment statements

The inputs in `tests_policy/expectations.json` and the retained curated fixture
are:

| Field | Value (cents) | Meaning |
| --- | ---: | --- |
| C | 1,500,000 | covered charges |
| G | 1,400,000 | gross Medicare payable |
| P | 1,250,000 | primary payment |
| D | 155,600 | deductible |
| K | 0 | coinsurance |
| A | 1,300,000 | obligatory acceptance amount |
| `full` | `N` | primary payment is not marked as payment in full |

Statement-by-statement values for `payment.cob`:

| Source line(s) | Operation | Values after the statement |
| --- | --- | --- |
| 13–14 | Initialize payment and status | `claim-payment = 0`; status `ZERO` |
| 16–19 | Test `raw-full = "Y"` | `N`, so no early payment-in-full return |
| 20 | `move claim-charges to charge-basis` | `charge-basis = C = 1,500,000` |
| 21–23 | If a contract is present, move it to the basis | `claim-has-contract = 1`; `charge-basis = A = 1,300,000` |
| 24 | `payment-cap = min(claim-gross, charge-basis)` | `min(1,400,000, 1,300,000) = 1,300,000` |
| 25–28 | Compare primary with cap | `1,250,000 < 1,300,000`; continue |
| 29 | Sum deductible and coinsurance | `deductions = 155,600 + 0 = 155,600` |
| 30–33 | Compare deductions with cap | `155,600 < 1,300,000`; continue |
| 34 | `reduction-amount = max(deductions, claim-primary)` | `max(155,600, 1,250,000) = 1,250,000` |
| 35 | `claim-payment = payment-cap - reduction-amount` | `1,300,000 - 1,250,000 = 50,000` |
| 36–37 | Set final status and reason | `PAID`, `SECONDARY_PAYABLE` |

**Result: `claim-payment = 50,000` cents = $500.00.** The contract is the
provider's total acceptance basis; it is not an extra subtraction after the
primary payment.

### Counterfactual without the contract-basis move

If the move at `payment.cob:21-23` were omitted, the earlier basis would remain
`C = 1,500,000`. The cap at line 24 would be
`min(1,400,000, 1,500,000) = 1,400,000`. Primary remains below that cap;
deductions remain 155,600; the larger reduction is still 1,250,000. Line 35
would then produce:

```text
1,400,000 - 1,250,000 = 150,000 cents = $1,500.00
```

That counterfactual is the precise reason the contract-basis move is important
for CMS-EX3.
