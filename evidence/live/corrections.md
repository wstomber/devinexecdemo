# Corrections log (live run)

Every correction made during this session, with its cause. Times are not recorded
as human time; human review/intervention time is UNKNOWN.

## Stage 2 (test harness, before any Python existed; program under test = COBOL)

| # | What failed | Cause | Correction |
|---|---|---|---|
| 1 | `IF-LEN-72`, `IF-LEN-74`, `IF-LEN-ID` raw records were 82/82/79 bytes | Hand-typed fixed-width strings in the ledger had the wrong padding | Regenerated the three raw strings from the 73-byte layout and checked lengths 72/74/72 before running any test |
| 2 | `TypeError: 'Run' object is not callable` | `setUpClass` stored the batch result as `cls.run`, shadowing `unittest.TestCase.run` | Renamed attribute to `cls.batch`; no expected value changed |

## Stage 3 (python/msp.py)

No corrections were needed. The first execution of `python/msp.py`:
- produced byte-identical curated results/totals to the Stage 1 COBOL baseline;
- passed all 25 Stage 2 tests unchanged with `MSP_COMMAND='python3 python/msp.py'`;
- passed all 23 focused unit tests in `tests_python/`.

No ledger value, Stage 2 test, starter file, or evidence file was edited to obtain a pass.
