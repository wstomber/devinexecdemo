# Fatal and usage paths: COBOL vs Python

MATCH = both exit 2, neither writes stdout, neither leaves a complete totals file. Partial results files are discarded by contract (README) and are not compared; stderr wording is not part of the interface and is not compared.

| case | COBOL exit | Python exit | COBOL stderr | Python stderr | result |
|---|---|---|---|---|---|
| no-arguments | 2 | 2 | True | True | MATCH |
| two-arguments | 2 | 2 | True | True | MATCH |
| four-arguments | 2 | 2 | True | True | MATCH |
| input-equals-output | 2 | 2 | True | True | MATCH |
| output-equals-totals | 2 | 2 | True | True | MATCH |
| missing-input | 2 | 2 | True | True | MATCH |
| missing-output-directory | 2 | 2 | True | True | MATCH |
| line-4097-bytes | 2 | 2 | True | True | MATCH |
| line-4097-bytes-no-newline | 2 | 2 | True | True | MATCH |
| line-8000-bytes-after-valid | 2 | 2 | True | True | MATCH |
| records-10001 | 2 | 2 | True | True | MATCH |
| duplicate-valid | 2 | 2 | True | True | MATCH |
| duplicate-rejected-bad-flag | 2 | 2 | True | True | MATCH |
| duplicate-rejected-bad-amount | 2 | 2 | True | True | MATCH |
