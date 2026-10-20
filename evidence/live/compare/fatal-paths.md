# Fatal-path comparison

Each scenario runs in a fresh directory whose OUTPUT and TOTALS start as `stale\n`.
Contract: exit 2, diagnostic on stderr, nothing on stdout, outputs discarded by the caller.

| Scenario | COBOL exit | Python exit | stderr (C/P) | leftover outputs identical | Result |
| --- | ---: | ---: | --- | --- | --- |
| usage: no arguments | 2 | 2 | True/True | YES | MATCH |
| usage: three arguments | 2 | 2 | True/True | YES | MATCH |
| usage: five arguments | 2 | 2 | True/True | YES | MATCH |
| identical output and totals | 2 | 2 | True/True | YES | MATCH |
| identical input and cwf | 2 | 2 | True/True | YES | MATCH |
| missing input | 2 | 2 | True/True | YES | MATCH |
| missing CWF | 2 | 2 | True/True | YES | MATCH |
| malformed CWF (unknown type) | 2 | 2 | True/True | YES | MATCH |
| malformed CWF (blank line) | 2 | 2 | True/True | YES | MATCH |
| CWF 1001 beneficiaries | 2 | 2 | True/True | YES | MATCH |
| duplicate ID at record 3 | 2 | 2 | True/True | YES | MATCH |
| duplicate of rejected identifiable ID | 2 | 2 | True/True | YES | MATCH |
| 4097-byte line after 2 records | 2 | 2 | True/True | YES | MATCH |
| 4097-byte final line without LF | 2 | 2 | True/True | YES | MATCH |
| 10001 records | 2 | 2 | True/True | YES | MATCH |
| unwritable output directory | 2 | 2 | True/True | YES | MATCH |
| unwritable totals directory | 2 | 2 | True/True | YES | MATCH |
| input is a directory | 2 | 2 | True/True | YES | MATCH |
