# Fatal-path comparison

MATCH = both exit 2, nothing on stdout, same first stderr line (COBOL's `; file status ii/oo/tt` suffix on the generic fatal line is not compared). Later stderr lines differ by design: COBOL prints its file-status codes and libcob implicit-CLOSE warnings, Python prints `fatal batch failure; discard outputs`. Full stderr of both is kept beside this file.

| case | cobol_exit | python_exit | cobol_stdout_bytes | python_stdout_bytes | cobol_stderr_first_line | python_stderr_first_line | result |
|---|---|---|---|---|---|---|---|
| usage-0-args | 2 | 2 | 0 | 0 | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | MATCH |
| usage-3-args | 2 | 2 | 0 | 0 | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | MATCH |
| usage-5-args | 2 | 2 | 0 | 0 | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | MATCH |
| same-input-and-results | 2 | 2 | 0 | 0 | `paths must be distinct` | `paths must be distinct` | MATCH |
| same-cwf-and-totals | 2 | 2 | 0 | 0 | `paths must be distinct` | `paths must be distinct` | MATCH |
| missing-input | 2 | 2 | 0 | 0 | `fatal batch failure; discard outputs` | `fatal batch failure; discard outputs` | MATCH |
| missing-cwf | 2 | 2 | 0 | 0 | `fatal batch failure; discard outputs` | `fatal batch failure; discard outputs` | MATCH |
| results-dir-missing | 2 | 2 | 0 | 0 | `fatal batch failure; discard outputs` | `fatal batch failure; discard outputs` | MATCH |
| cwf-blank-line | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| cwf-unknown-type | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| cwf-B-bad-dates | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| cwf-B-bad-msp | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| cwf-B-col45 | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| cwf-H-bad-charges | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| cwf-1001-B | 2 | 2 | 0 | 0 | `invalid CWF reference record` | `invalid CWF reference record` | MATCH |
| line-4097 | 2 | 2 | 0 | 0 | `input line exceeds 4096 bytes` | `input line exceeds 4096 bytes` | MATCH |
| line-4098-no-lf | 2 | 2 | 0 | 0 | `fatal batch failure; discard outputs` | `fatal batch failure; discard outputs` | MATCH |
| records-10001 | 2 | 2 | 0 | 0 | `batch exceeds 10000 records` | `batch exceeds 10000 records` | MATCH |
| records-10001-blank | 2 | 2 | 0 | 0 | `batch exceeds 10000 records` | `batch exceeds 10000 records` | MATCH |
| duplicate-valid-id | 2 | 2 | 0 | 0 | `duplicate claim ID: F00000      ` | `duplicate claim ID: F00000      ` | MATCH |
| duplicate-rejected-id | 2 | 2 | 0 | 0 | `duplicate claim ID: F00000      ` | `duplicate claim ID: F00000      ` | MATCH |

**21 MATCH, 0 MISMATCH.**
