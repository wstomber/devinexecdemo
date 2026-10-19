# Fatal-path parity (COBOL vs Python)

Each scenario runs in its own directory under `cobol/` and `python/` with the raw stdout, stderr, exit code and output files kept. `outputs` compares whether OUT/TOT exist afterwards and their SHA-256.

| scenario | exit C / P | stderr (COBOL) | stderr same | outputs same | result |
| --- | --- | --- | --- | --- | --- |
| usage-no-args | 2 / 2 | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | True | True | MATCH |
| usage-three-args | 2 / 2 | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | True | True | MATCH |
| usage-five-args | 2 / 2 | `usage: msp-batch INPUT CWF OUTPUT TOTALS` | True | True | MATCH |
| same-paths | 2 / 2 | `paths must be distinct` | True | True | MATCH |
| missing-input | 2 / 2 | `fatal batch failure; discard outputs; file status 35/  /` | True | True | MATCH |
| missing-cwf | 2 / 2 | `fatal batch failure; discard outputs; file status   /  /` | True | True | MATCH |
| malformed-cwf-type | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| malformed-cwf-blank | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| malformed-cwf-date | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| malformed-cwf-msp-mixed | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| malformed-h-charges | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| cwf-1001-b | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| cwf-1001-h | 2 / 2 | `invalid CWF reference record ⏎ fatal batch failure; discard outputs; file status   /  /   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of cwf-file ('CWF')` | True | True | MATCH |
| line-4097 | 2 / 2 | `input line exceeds 4096 bytes ⏎ fatal batch failure; discard outputs; file status 00/00/00 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of totals-file ('TOT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| line-4098-no-newline | 2 / 2 | `fatal batch failure; discard outputs; file status 00/00/00 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of totals-file ('TOT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| line-5000 | 2 / 2 | `fatal batch failure; discard outputs; file status 00/00/00 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of totals-file ('TOT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| line-4097-crlf-ok | 0 / 0 | `` | True | True | MATCH |
| records-10001 | 2 / 2 | `batch exceeds 10000 records ⏎ fatal batch failure; discard outputs; file status 00/00/00 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of totals-file ('TOT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| duplicate-id | 2 / 2 | `duplicate claim ID: F00001       ⏎ fatal batch failure; discard outputs; file status 00/00/00 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of totals-file ('TOT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| duplicate-id-rejected | 2 / 2 | `duplicate claim ID: F00001       ⏎ fatal batch failure; discard outputs; file status 00/00/00 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of totals-file ('TOT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| output-dir-missing | 2 / 2 | `fatal batch failure; discard outputs; file status 00/30/   ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |
| totals-dir-missing | 2 / 2 | `fatal batch failure; discard outputs; file status 00/00/30 ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of results-file ('OUT') ⏎ libcob: cobol/batch.cob:267: warning: implicit CLOSE of claims-file ('IN')` | True | True | MATCH |

**22 MATCH / 0 MISMATCH** of 22 scenarios.
