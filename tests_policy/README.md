# Stage 2 independent tests

These tests were written and run against the COBOL **before any Python existed**.
Their expected values come from `expectations.json`, which was worked out by hand
from the cited sources. They were not copied from COBOL output or from
`fixtures/expected.json`.

- `expectations.json`: 107 cases. Each case has a `kind` (`policy` = CMS rule
  arithmetic or a CWF decision; `interface` = a demo contract choice from the
  README or rules.md), a `source` key, written-out `arithmetic`, and an `expect`
  row. It ships its own synthetic CWF reference data (`P1…`–`P6…` MBIs), separate
  from `fixtures/cwf.json`.
- `test_policy.py`: runs the whole ledger as a single batch. It checks every CSV
  field exactly, then checks that the totals equal the sums of the ledger rows.
- `test_batch.py`: README framing and fatal-path contract. Covers CRLF, missing
  final newline, empty input, blank lines, 4,096/4,097-byte lines,
  10,000/10,001 records, duplicate IDs, a missing or malformed CWF file,
  1,000/1,001 `B`/`H` records, usage errors and output replacement.

Run:

```sh
make build
python3 -m unittest discover -s tests_policy -v                              # COBOL (default build/msp-batch)
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
```

Exact zero-padded CSV widths are an interface characterization of the committed
baseline format in `docs/evidence/cobol-baseline/`. They are not payment values.
Case `DATE-NO-CAL` is flagged for review: the README date rule accepts
2025-02-30.
