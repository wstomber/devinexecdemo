# Independent policy and interface tests

Written in Stage 2, before any Python implementation existed, and run first
against the COBOL program.

- `expectations.json` - hand-derived ledger, 119 cases run as one ordered batch
  (state reset depends on the order). Every case has a `kind` (`policy` = Pub.
  100-05 Ch. 5 §40.8-40.8.3 / CWF pre-payment rules; `interface` = README demo
  contract), a `source` citation and its `arithmetic`. Expected values were
  worked out from the cited sources, not copied from COBOL output or
  `fixtures/expected.json`. The ledger has its own synthetic CWF reference data
  (`cwf_reference.lines`, fictional MBIs), not `fixtures/cwf.json`.
- `test_policy_ledger.py` - runs the ledger and checks every row, the totals and
  CMS-EX3 (50,000 cents calculated, `ACCEPTED`, 50,000 released).
- `test_batch_interface.py` - CRLF / no final newline, empty input, blank lines,
  4,096/4,097-byte lines, 10,000/10,001 records, duplicate IDs, missing,
  empty and malformed CWF files, CWF table limits, usage errors.
- `msp_runner.py` - shared helpers; its record serializer is independent of
  `tools/fixtures.py`.

```sh
make build
python3 -m unittest discover -s tests_policy -v                       # COBOL (default build/msp-batch)
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
```

`MSP_COMMAND` is split with `shlex` and run without a shell; the four paths
`INPUT CWF RESULTS TOTALS` are appended.

Passing these tests shows agreement with these hand-derived expectations. It is
not proof of Medicare correctness beyond the cited cases.
