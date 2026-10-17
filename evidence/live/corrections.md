# Corrections

No corrections to `python/msp.py` were required after the first test run.

The initial focused unit-test run failed because the test helper used a 10-byte
field width when replacing the 12-byte claim ID, producing malformed test records
and therefore `BAD_LENGTH` instead of the intended `BAD_ID`. The helper now uses
the ID's actual 12-byte width. This was a test-helper correction, not a processor
correction.
