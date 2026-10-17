# Independent tests (Stage 2, written and run against COBOL before any Python existed)

- `expectations.json` — hand-derived ledger. `policy_cases` cite Pub. 100-05 Ch. 5
  §40.8–40.8.3 pages; `interface_cases` cite README/docs/rules.md demo decisions
  (NOT CMS policy). Each case has its arithmetic. Nothing was copied from COBOL
  output or `fixtures/expected.json`.
- `test_policy_ledger.py` — runs the ledger as one batch and per case, checks totals,
  state-reset sequences, and re-adds the ledger's own hand arithmetic.
- `test_batch_interface.py` — CRLF, missing final newline, empty/blank lines,
  non-ASCII digits, 4,096/4,097-byte lines, 10,000/10,001 records, duplicates, usage.

```sh
python3 -m unittest discover -s tests_policy -v                               # COBOL (build/msp-batch)
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
```
