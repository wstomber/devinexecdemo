# Stage 4 — COBOL vs Python comparison summary

Commands (logs next to this file): `verify-baseline-python.log`, `make-compare.log`, `verify-compare-curated.log`;
side-by-sides by `tools/side_by_side.py`, edge batch by `tools/edge_batch.py --seed 20261019 --count 2000`
(2,099 records: the 99 ledger records then 2,000 seeded byte-level mutations), fatal paths by `tools/fatal_parity.py`.

| batch | records | MATCH | MISMATCH | totals | results.csv byte-identical | totals.csv byte-identical | payment_cents | released_cents |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |
| [curated](curated/side-by-side.md) | 33 | 33 | 0 | MATCH | True | True | 10001694602 | 10000450202 |
| [synthetic](synthetic/side-by-side.md) | 1000 | 1000 | 0 | MATCH | True | True | 485289809347 | 344091123732 |
| [edge](edge/side-by-side.md) | 2099 | 2099 | 0 | MATCH | True | True | 72570433965 | 53945942182 |

Fatal paths: [22 / 22 MATCH](fatal/fatal-parity.md) (exit code, stdout, stderr byte-for-byte incl. libcob warnings, output-file existence and SHA-256).

Mismatches investigated: none occurred in Stage 4 (Stage 3 corrections are in `../corrections.md`).

CMS-EX3: COBOL and Python both `PAID 0000050000 SECONDARY_PAYABLE ACCEPTED DISPOSITION_01 0000050000` (curated record 2; ledger record 1 of the edge batch).

Limits: parity shows the Python matches this COBOL on these batches and scenarios only. It is not proof of Medicare correctness, and untested inputs (e.g. other runtime I/O failures, other GnuCOBOL versions) are not covered.
