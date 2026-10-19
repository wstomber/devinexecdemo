# 06 — Maintenance guide for `python/msp.py`

## Before you change anything
```sh
make build baseline generate                                            # COBOL reference + inputs
python3 -m unittest discover -s tests_python -v                         # unit tests
MSP_COMMAND="python3 $PWD/python/msp.py" python3 -m unittest discover -s tests_policy -v   # independent ledger + batch tests
python3 tools/verify.py baseline --command 'python3 python/msp.py' --report build/python-baseline-report.json
make compare CANDIDATE='python3 python/msp.py'
python3 tools/compare_report.py --out build/comparison                   # side-by-side + edge + fatal paths
```
Use an **absolute** path in `MSP_COMMAND`: the ledger runner executes in a temporary directory (`evidence/live/corrections.md` #4).

## Where things live
| Concern | Function |
| --- | --- |
| Byte framing and the 4,096 bound | `input_lines`, `finish_line` |
| Field validation and its precedence | `validate`, `valid_id`, `is_digits` |
| Payment formula | `calculate_payment` |
| CWF file parsing | `cwf_lines`, `CwfReference.add`, `load_cwf` |
| CWF decision | `cwf_check` |
| Per-record orchestration, duplicate IDs, the record limit | `process_line` |
| CSV text | `result_row`, `Totals.row` |
| CLI, file order, exit codes | `run`, `main` |

## Rules for changes
* **Policy change** (a new limit, a different check order): first add or adjust cases in `tests_policy/expectations.json`, with a citation and arithmetic, in a separate commit. Then change the code, then update `02-rule-map.md`. An intentional change makes COBOL parity fail, so record the expected differences rather than weakening `tools/verify.py`.
* **Interface change** (a new output, a flag): keep the four-positional-argument behavior and CSV bytes unchanged unless the change explicitly requires otherwise, and prove it with `tools/compare_report.py` (byte-identical results and totals).
* Keep integer cents, the stdlib-only constraint and the ASCII byte sets. Never parse amounts with `int(text)`.
* The CWF reader deliberately reproduces GnuCOBOL quirks (CR dropped, 64-byte truncation, directory = empty). Removing them is a behavior change; flag it for review and update `evidence/live/cobol-probes.sh` expectations.
* Do not edit `cobol/`, `fixtures/`, `tools/verify.py`, `tools/fixtures.py`, `tests/` or `docs/evidence/`. They are the reference and the starter evidence.

## Open review items
1. A CWF path that is a directory is silently treated as an empty reference (COBOL runtime behavior, preserved). It fails safe, because nothing is released, but it arguably should be fatal.
2. CWF dates are checked only for digits (no month/day range). Claim dates have no calendar check (`20250230` is valid).
3. Lowercase or space-containing MBIs in the CWF file are accepted but can never match a claim.
4. Parity shows equivalence to the COBOL on the tested batches. It is not proof of Medicare correctness.
