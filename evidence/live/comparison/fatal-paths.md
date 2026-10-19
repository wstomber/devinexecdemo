# Fatal-path comparison

Each case starts with `o.csv`/`t.csv` containing `previous`. Compared: exit code, and the final bytes of both output files (untouched, truncated or partial).

| Case | COBOL exit | Python exit | Output files identical | Results lines (COBOL/Python) | stdout empty | Result |
| --- | ---: | ---: | --- | --- | --- | --- |
| usage-3-args | 2 | 2 | True | 1/1 | True | MATCH |
| usage-5-args | 2 | 2 | True | 1/1 | True | MATCH |
| same-output-totals | 2 | 2 | True | 1/1 | True | MATCH |
| trailing-space-alias | 2 | 2 | True | 1/1 | True | MATCH |
| missing-input | 2 | 2 | True | 1/1 | True | MATCH |
| missing-cwf | 2 | 2 | True | 1/1 | True | MATCH |
| malformed-cwf | 2 | 2 | True | 1/1 | True | MATCH |
| cwf-1001-B | 2 | 2 | True | 1/1 | True | MATCH |
| empty-input-path | 2 | 2 | True | 1/1 | True | MATCH |
| input-is-directory | 2 | 2 | True | 1/1 | True | MATCH |
| unopenable-results | 2 | 2 | True | 1/1 | True | MATCH |
| unopenable-totals | 2 | 2 | True | 0/0 | True | MATCH |
| duplicate-id | 2 | 2 | True | 3/3 | True | MATCH |
| duplicate-invalid-id | 2 | 2 | True | 2/2 | True | MATCH |
| line-4097 | 2 | 2 | True | 2/2 | True | MATCH |
| records-10001 | 2 | 2 | True | 10001/10001 | True | MATCH |
| cwf-is-directory (not fatal) | 0 | 0 | True | 2/2 | True | MATCH |
