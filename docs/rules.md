# Rules, provenance, and assumptions

Source: CMS Medicare Secondary Payer Manual, Publication 100-05, Chapter 5,
[official PDF](https://www.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Downloads/msp105c05.pdf).
Retrieved **2026-10-17**. The retrieved document has 222 pages; its contents page
states Rev. 13783, issued 2026-05-27. The selected sections state Rev. 11550,
issued 2022-08-12, effective and implemented 2022-10-13.

SHA-256 of the retrieved PDF:
`a2ea49af2675c75ee617961723848016fee55f80b74aa7716b22fa38e10af693`.
The CMS URL is mutable; this hash identifies the reviewed version. The repository
does not redistribute the entire manual. Relevant pages were read as extracted
text and visually checked; references below are **one-based PDF viewer pages**,
not the zero-based indexes used by some PDF tools.

| Section | PDF pages | Interpretation used here |
| --- | --- | --- |
| 40.8 | 78 | No payment when primary reaches charges or gross, or is received and accepted/required as payment in full |
| 40.8.1 | 79 | Gross is before deductible/coinsurance; pricing is supplied upstream |
| 40.8.2 | 79–80 | Four payment limits; lower obligatory acceptance replaces charges; full-payment condition |
| 40.8.3 A | 80–81 | Prospective-payment formula using the larger of deductions or primary |
| 40.8.3 Example 1 | 82 | $25,000 charges, $22,000 gross, $20,500 primary, $1,556 deductible: $1,500 secondary |
| 40.8.3 Example 3 | 83–84 | $15,000 charges, $14,000 gross, $12,500 primary, $1,556 deductible, $13,000 obligatory acceptance: $500 secondary |
| 40.8.3 Example 4 | 84 | Contains a contradictory extra intermediate equality; excluded from fixtures |

## Exact selected formula

All symbols below represent integer cents. Let C be covered charges, G gross
Medicare payable, P primary payment for covered services, D applicable deductible,
K applicable coinsurance, and A the optional lower contractual acceptance amount.
Let B = A if supplied, otherwise C. Let T = D + K.

After validation, payment is zero if the received primary payment is accepted or
required as payment in full (`full=Y`). Otherwise:

```
payment = max(0, min(G - T, G - P, B - P, B - T))
        = max(0, min(G, B) - max(T, P))
```

The second expression is an algebraic simplification of the four limits and
§40.8.3 A. It does not deduct both primary payment and Medicare deductions in
series. The explicit zero cases avoid unsigned subtraction below zero.

Example 1 limits, in dollars: 20,444; 1,500; 4,500; 23,444. Lowest is 1,500.
Example 3 limits: 12,444; 1,500; 500; 11,444. Lowest is 500. The $13,000 OTAF
is the total the provider must accept, not an additional reduction from $15,000.
The difference between $13,000 and the $12,500 primary payment is the memorable
$500 secondary payment. Neither example has accepted the primary payment itself
as full payment, so their `full` indicator is `N`.

## Published inconsistency

Example 4 (PDF page 84) says the deductible is met and coinsurance is zero. Its
gross-minus-coinsurance line correctly reaches $4,600 but appends another equality
to $3,822, inconsistent with those inputs. The surrounding formula and its stated
$1,200 final payment do not require this extra number. We flag this as a source
review issue, exclude Example 4 as an authoritative fixture, and use unambiguous
Examples 1 and 3. No application behavior silently incorporates $3,822.

## Simplifications and demo decisions

- Proper primary filing, eligibility, coverage, allocation of primary payment,
  gross pricing, and applicable deductions are supplied correctly upstream.
- `full=Y` asserts the received primary payment is accepted or required as full
  payment. A lower contract supplied with `full=N` is an obligatory total charge
  basis, not evidence that a smaller primary payment was accepted in full.
- An optional acceptance amount must not exceed covered charges. Equal and zero
  values are accepted as explicit demo interface decisions. Contradictory or
  malformed data is rejected; no missing monetary field defaults to zero.
- Deduction amounts above a cap remain valid inputs; they produce zero payment.
  No calculation of beneficiary liability is attempted.
- Negative inputs, fractional cents, signed fields, unrecognized flags, and extra
  fields are unsupported. File layouts, validation precedence, reason codes,
  limits, and exit codes are our own interface, not CMS policy or CMS edit codes.
- Valid zero precedence is payment in full, then primary at/above the smaller
  gross/charge cap, then combined deductions at/above that cap. Thus an all-zero
  claim gets `PRIMARY_AT_CAP`. Positive amounts get `SECONDARY_PAYABLE`.
- Historical deductible amounts are confined to the two published fixtures.
  There is no current rate table and no claim of exhaustive policy coverage.

## Rule-to-COBOL mapping

| Rule / interface decision | Code |
| --- | --- |
| Raw fields, ten-digit cents, packed parsed amounts | `copybooks/claim.cpy` |
| Validate length, identifier, numeric fields before conversion, contract, flag | `validate.cob`, `validate-record` |
| Received primary accepted in full | `payment.cob`, first branch of `calculate-prospective-payment` |
| Contract replaces covered charges | `payment.cob`, `charge-basis` assignment |
| Four limits / prospective formula | `payment.cob`, `payment-cap`, `deductions`, `reduction-amount` |
| No negative payment and reason precedence | `payment.cob`, ordered zero branches before subtraction |
| Independent record state and totals | `batch.cob`, `process-record` and `main` |
| Duplicate IDs, 10,000-record limit, file failure | `batch.cob`, `process-record` and `fatal-io` |

## Fixture-to-rule mapping

`fixtures/expected.json` is the independent expectation ledger, with origin and
a short arithmetic or validation rationale for **every** record. Inputs are in
`fixtures/curated.json`. Expectations are not generated from COBOL output.

| Cases | Rule / boundary |
| --- | --- |
| CMS-EX1, CMS-EX3 | Published examples; gross and lower contractual caps |
| ORDINARY, CHARGE-LIMIT | Gross versus charge cap |
| DEDUCT-LIMIT, COINS-CENT, TIE | Sum deductions; choose larger deduction or primary; one-cent precision |
| CONTRACT-DED, CONTRACT-0 | Contractual basis plus deductions; explicit zero contract |
| PRIMARY-EQ, PRIMARY-HIGH, CENT-BELOW | Primary exactly at, above, or one cent below a cap |
| FULL-FIRST, ALL-ZERO | Zero precedence when multiple conditions apply |
| NO-PRIMARY, ONE-CENT | Valid zero inputs and smallest positive payment |
| DEDUCT-EQ, DEDUCT-HIGH | Deduction equality and clamping below zero |
| MAX-DEDUCT, MAX-PAY | Eleven-digit deduction sum and total beyond per-record width |
| SHORT, EXTRA, BADID | Length, unsupported trailing field, absent ID |
| MISSING, SIGNED, DECIMAL, BADOPTION | Absent / malformed numeric data and optional sentinel |
| HIGHCONTRACT, BADFLAG | Contract range and unsupported indicator |
| AFTER-ERROR | Positive claim following rejected records; reset of optional and parsed values |

Thirty records: 12 paid, 9 valid zero, 9 invalid. Expected total is
10,000,450,202 cents. Synthetic boundary cases use intentionally small or extreme
values to exercise the interface; they are not realistic rate examples.
The 1,000-record seeded batch has no policy oracle. Agreement on it is
characterization evidence only.
