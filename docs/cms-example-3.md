# CMS §40.8.3, Example 3: source excerpt

Source: CMS Medicare Secondary Payer Manual, Publication 100-05, Chapter 5,
§40.8.3 Example 3, **PDF viewer pages 83–84** (one-based).
[Official PDF](https://www.cms.gov/Regulations-and-Guidance/Guidance/Manuals/Downloads/msp105c05.pdf).
Retrieved 2026-10-17; section Rev. 11550 (issued 2022-08-12).
Retrieved PDF SHA-256:
`a2ea49af2675c75ee617961723848016fee55f80b74aa7716b22fa38e10af693`.

The following is a textual excerpt from the U.S. government manual. Line wrapping
and bullet layout are normalized; the final beneficiary-liability discussion is
omitted because that calculation is outside this demo's scope.

> EXAMPLE 3:
>
> A hospital furnished five days of inpatient care to a Medicare beneficiary. No
> part of the Medicare inpatient deductible of $1,556 had been met. The hospital's
> charges for Medicare covered services were $15,000 and the Medicare gross
> payment amount (without regard to the deductible) was $14,000. The provider
> agreed to accept $13,000 as payment in full. The primary payer paid $12,500 due
> to a deductible requirement under its plan. The amount the provider is obligated
> to accept as payment in full (OTAF) $13,000 is considered by Medicare to be the
> hospital's charges in this situation. As secondary payer, Medicare pays the
> lowest of:
>
> - The Medicare gross payment amount (without regard to deductible) minus the
>   primary payer's payment: $14,000 - $12,500 = $1,500;
> - The Medicare gross payment amount (without regard to deductible) minus the
>   Medicare inpatient deductible: $14,000 - $1,556 = $12,444;
> - The OTAF amount minus the primary payer's payment: $13,000 - $12,500 = $500; or
> - The OTAF amount minus the Medicare inpatient deductible: $13,000 - $1,556 = $11,444.
>
> Medicare pays $500.

Demo inputs: covered/billed charges $15,000, gross $14,000, primary $12,500,
acceptance $13,000, remaining deductible **$1,556 (historical example input)**,
coinsurance $0. Stable fixture ID: `CMS-EX3`.

The $13,000 amount is the total obligatory acceptance amount. It does not mean
that the smaller $12,500 primary payment itself was accepted in full; this fixture
has `full=N`. With the acceptance limit, payment is $500. Ignoring that limit
would leave $1,500 under the other limits, overstating the scoped payment by $1,000.
That counterfactual is explanatory arithmetic, not a staged defect in the COBOL.

The COBOL paragraph to explain is `calculate-prospective-payment` in
`cobol/payment.cob`: the `claim-has-contract` branch replaces `charge-basis` with
`claim-contract`, followed by `min(claim-gross, charge-basis)`.
Devin must connect this source, paragraph, its independently derived tests, and
its Python implementation in the migration rule map.
