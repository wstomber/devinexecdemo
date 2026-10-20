# Independently derived policy and interface tests (Layer A)

Written by Devin **before** any Python implementation existed. They were run and
committed against the COBOL executable first.

- `expectations.json` holds 72 hand-derived cases. Each one lists its input,
  CMS source section/page, the four §40.8.2 limits, the arithmetic, the
  assumptions, and the expected status/reason/cents.
  - Category `policy-*` cases come from CMS Pub. 100-05 Ch. 5 §§40.8–40.8.3.
  - Category `interface-*` cases come from the demo record contract in README.md
    (assumptions I1–I7). They are **not** CMS policy.
  - Category `cwf-*` cases come from the CWF pre-payment check in docs/rules.md
    (CMS Pub. 100-04 Ch. 27 §20; demo-defined reject codes on synthetic CWF data).
- `test_policy.py` has three test classes:
  - `PolicyLedgerTests` runs the ledger as one batch.
  - `BatchInterfaceTests` covers framing, duplicate IDs, state reset, the
    4,096-byte and 10,000-record limits, and usage errors.
  - `LedgerArithmeticAudit` checks the hand arithmetic for typos. It runs no
    executable.

```sh
make build
python3 -m unittest discover -s tests_policy -v                                   # COBOL
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v  # Python
```

## Cross-check with the starter ledger (done after the derivation above)

- The starter's `fixtures/expected.json` was consulted only after this ledger was
  written.
- The overlapping published cases agree on the same inputs: CMS-EX3 pays 50,000
  cents and CMS-EX1 pays 150,000 cents.
- This ledger adds:
  - the EX3-NO-OTAF counterfactual;
  - each of the four limits controlling in turn (OTAF-T, GROSS-P, GROSS-T,
    CHARGE-P, CHARGE-T);
  - equal limits;
  - one-cent differences on both sides of primary vs deductions and gross vs
    charges;
  - maximum values with a contract;
  - lowercase, leading-space and embedded-space IDs;
  - an alphabetic contract;
  - two-fault precedence pairs;
  - an explicit contract-leak state-reset check.
- No conflict between the COBOL and the cited policy was found on these cases.
  Agreement is limited to the 72 cases and the batch tests listed here.
