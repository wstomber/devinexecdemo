# 06 — Maintenance guide for `python/msp.py`

## Daily commands

```sh
make build                                                     # COBOL reference, still needed for parity
python3 -m unittest discover -s tests_python -v                # unit tests (Python only)
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v   # policy ledger + batch contract
python3 -m unittest discover -s tests_policy -v                # same tests against COBOL
make test                                                      # starter infrastructure tests
make compare CANDIDATE='python3 python/msp.py'                 # strict parity, seeded 1,000
python3 tools/verify.py compare --candidate 'python3 python/msp.py' --input build/curated.dat
python3 tools/edge_batch.py --ascii --output build/edge.dat --cwf-output build/edge-cwf.dat
python3 tools/side_by_side.py edge build/edge.dat build/edge-cwf.dat build/compare
python3 tools/compare_fatal.py --outdir build/compare
```

## Where to change what

| Change | Code | Must also update |
| --- | --- | --- |
| Payment formula or zero reasons | `calculate_payment` | Ledger cases + arithmetic **first**, with a source citation; then the rule map |
| New validation rule / reason code | `validate_record` (keep precedence order) | README interface, `tools/verify.py` `REASONS` (starter, needs review), ledger |
| CWF check | `cwf_check` (order matters) | Ledger CWF section and its own reference data; rules.md |
| CWF file format | `cwf_records` / `parse_cwf` | README layout, `test_batch.CwfFileTests` |
| Output format | `result_row`, `totals_row`, headers | Every consumer; byte-identical parity will (correctly) fail until the COBOL also changes or is retired |

## Rules for safe changes

1. Write or adjust the expectation in `tests_policy/expectations.json` from the
   policy source *before* changing code. Never paste observed output into the
   ledger.
2. While COBOL remains the reference, any intentional behavior change will show
   up as a parity MISMATCH. Record the change and its approval. Do not loosen the
   verifier.
3. Keep `int` cents, explicit ASCII byte sets, and byte-mode I/O.
4. Keep `Claim` creation per record. Never reuse a claim object, because that
   recreates the state-leak bug that `INITIALIZE` prevents.
5. Diagnostics go to stderr. The CSV goes only to files. Exit codes are only 0
   and 2.

## Known limits

- Equivalence is shown only on the tested batches (6,093 records + 18 fatal
  scenarios). It is not proof of Medicare correctness.
- No calendar validation (`DATE-NO-CAL`). The demo CWF covers only three checks.
- The parity checks depend on GnuCOBOL 3.1.2 runtime behavior for the CWF file. A
  different COBOL runtime may need its probes repeated.
