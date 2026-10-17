# Fatal-path parity (COBOL vs Python), 2026-10-17T21:36:27Z

| case | program | exit | results.csv bytes | results sha256 | totals.csv bytes | first stderr line |
|---|---|---|---|---|---|---|
| dup | `build/msp-batch` | 2 | 100 | `4176be99edd01460…` | 0 | duplicate claim ID: EDGE-OK |
| dup | `python3 python/msp.py` | 2 | 100 | `4176be99edd01460…` | 0 | fatal batch failure; discard outputs; duplicate claim ID: EDGE-OK |
| long | `build/msp-batch` | 2 | 100 | `4176be99edd01460…` | 0 | input line exceeds 4096 bytes |
| long | `python3 python/msp.py` | 2 | 100 | `4176be99edd01460…` | 0 | fatal batch failure; discard outputs; input line exceeds 4096 bytes |
| limit | `build/msp-batch` | 2 | 570047 | `56850418c249fbdb…` | 0 | batch exceeds 10000 records |
| limit | `python3 python/msp.py` | 2 | 570047 | `56850418c249fbdb…` | 0 | fatal batch failure; discard outputs; batch exceeds 10000 records |

Cases: dup = two records with the same identifiable claim ID; long = 4,097-byte line; limit = 10,001 records. Both programs exit 2, leave byte-identical partial files, and tell the caller to discard outputs (the CLI contract in README.md: fatal => non-zero exit, outputs must not be used). stderr wording is diagnostic only and is not part of the contract.
