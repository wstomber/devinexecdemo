# 06 — Maintenance guide (Python implementation)

## Run and check
```sh
make build generate                                    # COBOL reference + fixtures
python3 python/msp.py IN.dat CWF.dat results.csv totals.csv
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v
MSP_COMMAND=build/msp-batch        python3 -m unittest discover -s tests_policy -v
python3 -m unittest discover -s tests_python -v
make test
make compare CANDIDATE='python3 python/msp.py'
python3 tools/side_by_side.py --name curated --input build/curated.dat --cwf build/cwf.dat --out /tmp/sbs
python3 tools/edge_batch.py --out /tmp/edge && python3 tools/side_by_side.py --name edge --input /tmp/edge/edge.dat --cwf /tmp/edge/edge-cwf.dat --out /tmp/sbs-edge
python3 tools/fatal_parity.py --out /tmp/fatal
```
Python 3.10+, standard library only.

## Where things live
| Concern | Function |
| --- | --- |
| field validation | `validate_claim`, `ascii_digits`, `valid_claim_id` |
| MSP payment | `calculate_payment` |
| CWF reference file | `parse_cwf`, `_cwf_lines` |
| CWF checks | `check_cwf` |
| framing / limits | `iter_framed_records`, `_finish_line` |
| batch, totals, fatal paths | `_run_batch`, `_write_fatal`, `_result_line`, `_totals_line` |

## Changing a rule
1. Cite the CMS or interface source and add/adjust ledger cases with arithmetic in
   `tests_policy/ledger_source.py`; regenerate `expectations.json`.
2. Change `python/msp.py` and the unit tests.
3. Expect the COBOL comparison to diverge exactly on the changed cases; record the
   intended divergence instead of forcing parity. While COBOL remains the system of
   record, both must change together.
4. Keep integer cents and byte-level validation. Keep the output contract unless every
   consumer is updated.

## Known limits
Synthetic module; reason/CWF codes are demo-defined; three synthetic CWF checks only;
parity is with this COBOL under GnuCOBOL 3.1.2 on the tested batches, not proof of Medicare
correctness. libcob warning lines are reproduced for the tested fatal paths only.
