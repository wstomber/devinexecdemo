# Corrections log (live run)

Every correction made during the live run, with its cause. Stage 2 entries were made before any Python existed.

| # | Stage | What failed | Cause | Correction |
| --- | --- | --- | --- | --- |
| 1 | 2 | Ledger serializer raised on 34 case IDs | Test-construction error: names longer than the 12-byte ID field | Renamed to ≤12 chars (no expected value changed) |
| 2 | 2 | `test_non_ascii_bytes_are_invalid_not_fatal` got `BAD_ID` | Test error: 46×`é` = 92 bytes is a legal length | Use 47×`é` = 94 bytes |
| 3 | 2 | `test_transport_bound` (4,096 bytes, no newline) exited 2 | Test error: an unterminated line followed by another record joins them into one 4,188-byte line | Put the unterminated long line last |
| 4 | 3 | Every Stage 2 test failed with `MSP_COMMAND='python3 python/msp.py'` (exit 2) | Invocation, not code: `tests_policy/common.run` executes in a temporary cwd, so the relative script path did not resolve | Ran the unchanged Stage 2 tests with an absolute path, `MSP_COMMAND="python3 $PWD/python/msp.py"`; no test or Python change |

No Python logic correction was needed. The first implementation passed all 23 Stage 2 tests, the 29 unit tests, and an identical run of `evidence/live/cobol-probes.sh` (35 runtime file-handling probes).
