# Legacy walkthrough: what the COBOL actually does, line by line

Read `03-cobol-primer.md` first if COBOL is new to you. Line numbers refer to
the unchanged starter files at commit `37ceca1`. Each section ends with the
Python that replaced it.

```
              ┌──────────────── batch.cob (msp-batch, main program) ────────────────┐
 INPUT file → │ read bytes → frame lines → process-record ─┬─ CALL validate-claim  ──┼─ validate.cob
              │                                             └─ CALL calculate-payment ┼─ payment.cob
              │ count + total ← result row → OUTPUT csv                              │
              │ totals row → TOTALS csv; any fatal → stop run, exit 2                │
              └──────────────────────────────────────────────────────────────────────┘
          all three programs share one memory block, claim-interface (claim.cpy)
```

## The shared record: `cobol/copybooks/claim.cpy`

| Lines | Field | Meaning |
|---|---|---|
| 1 | `claim-interface` | The single block passed by reference to both subprograms |
| 2–10 | `claim-raw` | The 73 input bytes overlaid as eight fields: ID 12, five amounts × 10, contract 10, flag 1 |
| 11 | `claim-length` | Length of the framed line, so validation can reject lengths ≠ 73 |
| 12–14 | `claim-id`, `claim-status`, `claim-reason` | The outputs. Validation and calculation write them; batch reads them |
| 15–20 | `claim-charges` … `claim-contract` | Parsed amounts as packed decimal (exact cents) |
| 21 | `claim-has-contract` | 1 if the contract was supplied, 0 if `----------`. This is how COBOL represents "optional": a separate flag, because a numeric field cannot be empty |
| 22 | `claim-payment` | The calculated payment |

Python: `Claim` (parsed inputs) and `Result` (outputs) in `python/msp.py`.
"Optional" is `contract: Optional[int]`, with `None` for absent, so the flag
and the value cannot disagree.

## `cobol/batch.cob`: the batch driver (`msp-batch`)

**Lines 1–19: files.** Three files. The input is read as 1-byte records
(14–15), so the program sees every byte, including CR, LF and NUL. The outputs
are line-sequential text with fixed buffers of 160 and 180 characters.

**Lines 20–44: working storage.** These are the program's globals. They
include path buffers of 1,024 bytes, a 4,097-byte line buffer (one byte larger
than the limit so overflow can be detected), four 10-digit counters, a 15-digit
payment total, and a fixed table of 10,000 seen IDs (40–43). The table size
*is* the 10,000-record limit.

**Lines 46–61: arguments.** Exactly three arguments, all distinct; otherwise
print usage and exit 2. Distinct paths stop a run from overwriting its own
input.

**Lines 62–74: open.** It disables two GnuCOBOL line-sequential runtime
options, then opens input, results and totals. Each open checks its file
status, and any failure goes to `fatal-io`. The `*-open` flags record what to
close later.

**Lines 75–76: header row** `record_no,claim_id,status,payment_cents,reason`.

**Lines 77–94: the framing loop.** Read one byte at a time:
- Status `10` (EOF): if a partial line is buffered, process it. This is why a
  last line without a newline still counts.
- Byte `x"0A"` (LF): the line is complete; run `finish-line`.
- Any other byte: append it. If 4,097 bytes are already buffered, the line is
  too long → fatal (88).
- Any other file status → fatal.

**Lines 95–104: totals.** It writes the header, then builds the totals row with
`STRING`. Because the counters are `pic 9(10)` and the total is `pic 9(15)`,
they come out zero-padded to 10 and 15 digits. It closes the files and exits 0.
Totals are written only after every record succeeded.

**Lines 105–118: `finish-line`.** It strips one trailing CR, so CRLF files
behave like LF. A line still over 4,096 bytes → fatal. Then it processes the
record and clears the buffer. Note that an *empty* line still reaches
`process-record`: a blank line is a record (it becomes `BAD_LENGTH`), not
something skipped.

**Lines 119–157: `process-record`.** This paragraph is the heart of the batch:
1. 120–124: the 10,001st record is fatal. Otherwise count it.
2. 126: `initialize claim-interface` resets *every* raw and parsed field. This
   prevents a contract or flag from a previous record leaking into this one.
3. 127–128: provisional identity `@` + record number (`@0000000007`). Records
   whose ID cannot be trusted are reported under this name. `@` is not a legal
   ID character, so these names can never collide with a real ID.
4. 129–131: overlay the raw bytes, record the length, and `CALL
   validate-claim`.
5. 132–141: if validation accepted the ID (it no longer starts with `@`),
   linear-search the seen table. A duplicate is fatal, even when the record
   was otherwise rejected, because two records claiming the same ID make the
   batch untrustworthy.
6. 142–144: only `VALID` records are priced (`CALL calculate-payment`).
7. 145–150: count by final status and add the payment (0 for zero/invalid).
8. 151–157: format and write the result row. `payment-display pic 9(10)` gives
   the 10-digit zero padding, and `function trim` removes the padding of the
   text fields.

**Lines 158–179: write/close helpers.** Every write and close checks file
status.

**Lines 180–184: `fatal-io`.** Print `fatal batch failure; discard outputs`
with the three file statuses, set exit code 2, and `stop run`. It does not
delete files. The contract is that the caller must discard outputs from a run
that exits non-zero. Partial results may exist; totals will be empty.

Python: `read_records` + `finish_line` (framing and limits), `Batch.process`
(steps 1–7), `result_row`/`Batch.totals_row` (formatting), `run`/`main` (files,
arguments, exit codes), `FatalBatchError` (`fatal-io`).

## `cobol/validate.cob`: validation (`validate-claim`)

The pattern is **set the reason first, then test, and `goback` if the test
fails**. Whatever reason was set last before the `goback` is the one reported.
This is how the rejection precedence is encoded:

| Lines | Check | Reason if it fails |
|---|---|---|
| 33–35 | Framed length is exactly 73 | `BAD_LENGTH` |
| 36–37 | ID is not all spaces | `BAD_ID` |
| 38–54 | Scan the 12 ID bytes: once a space is seen (`id-ended`), any later non-space fails. Each byte must be A–Z, 0–9, `-` or `_` | `BAD_ID` |
| 55 | ID accepted: copy it to `claim-id`. From here on, rejections are reported under the real ID | — |
| 56–61 | The five amount fields pass `IS NUMERIC` | `BAD_AMOUNT` |
| 62–66 | Contract is exactly `----------` (absent), or numeric (then parse it and set `claim-has-contract`) | `BAD_AMOUNT` |
| 67–72 | Only now convert the amount text to packed decimal | — |
| 73–77 | A supplied contract must not exceed covered charges | `BAD_CONTRACT` |
| 78–79 | Flag is exactly `Y` or `N` | `BAD_FLAG` |
| 80–82 | `VALID`, empty reason | — |

Points a reviewer might miss:
- A malformed contract is `BAD_AMOUNT`, not `BAD_CONTRACT`. `BAD_CONTRACT`
  means "well-formed but larger than the charges".
- The ID scan accepts an exactly 12-character ID with no padding
  (`EDGE-ID-OVER` in the edge batch).
- A valid zero is not invalid: all-zero amounts pass validation and become
  `ZERO / PRIMARY_AT_CAP` in calculation. "Malformed" and "legitimately $0"
  are distinguished.

Python: `validate()` runs the same checks in the same order, with
`valid_claim_id` and `is_numeric` as small helpers.

## `cobol/payment.cob`: the MSP calculation (`calculate-payment`)

```cobol
12 calculate-prospective-payment.
13     move 0 to claim-payment
14     move "ZERO" to claim-status
16     if raw-full = "Y"                         → ZERO / PAYMENT_IN_FULL
20     move claim-charges to charge-basis
21     if claim-has-contract = 1
22         move claim-contract to charge-basis    ← OTAF replaces the charges
24     compute payment-cap = function min(claim-gross, charge-basis)
25     if claim-primary >= payment-cap           → ZERO / PRIMARY_AT_CAP
29     compute deductions = claim-deductible + claim-coinsurance
30     if deductions >= payment-cap              → ZERO / DEDUCTIONS_AT_CAP
34     compute reduction-amount = function max(deductions, claim-primary)
35     compute claim-payment = payment-cap - reduction-amount   → PAID / SECONDARY_PAYABLE
```

**What it means in policy terms** (Pub. 100-05 Ch. 5 §40.8.2): Medicare's
secondary payment is the lowest of four limits:

1. gross Medicare payable − primary payment (G − P)
2. gross Medicare payable − deductible and coinsurance (G − T)
3. charge basis − primary payment (B − P)
4. charge basis − deductible and coinsurance (B − T)

and never less than zero. The COBOL computes this as one subtraction: the
smaller of the two "tops" (G, B) minus the larger of the two "reductions"
(P, T). That is algebraically the same minimum of all four. Lines 25 and 30
are the "never below zero" floor, split into two reason codes.

**Line 21–22 is the CMS-EX3 line.** When a provider is obligated to accept a
lower contractual amount (the OTAF), §40.8.2 says that amount is treated as
the charges. The code does not subtract it and does not add it as a fifth
limit; it *replaces* the charge basis.

### CMS-EX3 through the code

| Line | Value |
|---|---|
| inputs | C=1,500,000 G=1,400,000 P=1,250,000 D=155,600 K=0 contract=1,300,000 full=N |
| 16 | `full` is `N`, so continue |
| 20–22 | charge-basis = 1,500,000, then replaced by the contract: **1,300,000** |
| 24 | cap = min(1,400,000, 1,300,000) = **1,300,000** |
| 25 | 1,250,000 ≥ 1,300,000? no |
| 29–30 | deductions = 155,600 ≥ 1,300,000? no |
| 34 | reduction = max(155,600, 1,250,000) = 1,250,000 |
| 35 | payment = 1,300,000 − 1,250,000 = **50,000 cents = $500.00** |

Without line 21–22 the cap would be min(1,400,000, 1,500,000) = 1,400,000 and
the payment $1,500. That is the $1,000 overpayment the demo is about
(EX3-NO-OTAF). Note also that `full=N`: the $13,000 is the total the provider
must accept, not a statement that the $12,500 primary payment was accepted as
payment in full.

Python: `charge_basis`, `payment_cap` and `calculate` in `python/msp.py`, in
the same order.
