# Independent policy and interface tests (Stage 2)

These were written and run against COBOL **before any Python existed**. The ledger
`expectations.json` was worked by hand from Pub. 100-05 Ch. 5 §40.8–40.8.3
(`docs/rules.md`, `docs/cms-example-3.md`) and from the README interface. Each case
cites its source and shows its arithmetic. No expected value was copied from COBOL output
or from `fixtures/expected.json`.

- `policy_cases` contain CMS-derived payment arithmetic: CMS-EX3 ($500), the same
  inputs without an OTAF ($1,500), CMS-EX1, each of the four limits controlling, equal
  limits, one-cent boundaries, payment in full, and maximums. The zero *reason codes* and
  their precedence are demo decisions (`RULES-DEMO`), not CMS codes.
- `interface_cases` contain demo interface assumptions only. They cover valid zeros and
  the edge contract values (zero, equal to charges), and every rejection reason and its
  precedence (length > ID > amount > contract > flag). They also check that a malformed
  contract is `BAD_AMOUNT`, and that non-ASCII, signed, spaced and underscore digits are
  rejected.
- `test_batch_interface.py` tests the README batch contract:
  - CRLF and a missing final newline, empty input and blank lines;
  - 4,096/4,097-byte lines and 10,000/10,001 records;
  - duplicate IDs, including on rejected records;
  - state reset after rejected records, totals, and usage/file errors.

Run (selects the program under test; default `build/msp-batch`):

```sh
python3 -m unittest discover -s tests_policy -v
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
```
