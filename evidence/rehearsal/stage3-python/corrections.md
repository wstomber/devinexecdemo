# Corrections made during Stage 3

| # | Where | Symptom | Cause | Classification | Resolution | Rerun |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `tests_python/test_msp_units.py`, `test_length_and_identity` | 2 of 20 unit tests failed on the first run: IDs `b"A\x00…"` and `b"\xc9T…"` were reported `BAD_LENGTH` instead of `BAD_ID` | **Test-authoring error.** These two hand-typed 12-byte ID fields were only 10 and 11 bytes long, so the records really were 71 and 72 bytes. `python/msp.py` reported them correctly. | test defect (record handling in the test, not the implementation) | Padded both literals to 12 bytes. No implementation change. | `python-unit-tests.log`: 20/20 OK |

The independent Stage 2 tests (`tests_policy`) passed against `python/msp.py` on
the first run. See `policy-tests-python-first-run.log`. No change to the
Python implementation was needed for them.
