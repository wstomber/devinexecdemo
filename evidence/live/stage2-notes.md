# Stage 2 notes — independent ledger and batch tests (before any Python)

- Ledger: `tests_policy/expectations.json` (99 cases: 51 policy, 48 interface), generated
  from the hand-typed values in `tests_policy/ledger_source.py`. Sources: CMS Pub. 100-05
  Ch. 5 §40.8–40.8.3, Pub. 100-04 Ch. 27 §20, Pub. 100-05 Ch. 5 §10.1, `docs/rules.md`,
  README interface. Not copied from COBOL output, `fixtures/expected.json` or
  `fixtures/cwf.json`; CWF reference data (6 `B`, 3 `H` records) is new.
- CMS-EX3 in the ledger: payment 50000, `ACCEPTED`/`DISPOSITION_01`, released 50000.
- Runner: `tests_policy/msp_harness.py`; program chosen by `MSP_COMMAND`
  (default `build/msp-batch`). Tests: `test_ledger.py` (whole ledger as one batch in order,
  so state-reset cases follow the rejected record they depend on; each case alone; ledger
  integrity; output widths) and `test_batch.py` (CRLF, missing final newline, final lone CR,
  empty input, blank lines, duplicate IDs incl. rejected records, missing/malformed/blank CWF,
  1,000/1,001 B and H records, 4,096/4,097-byte lines, 10,000/10,001 records, usage and
  identical-path errors, byte-level malformed fields, silent stdout).
- Run against COBOL: `evidence/live/stage2-tests-cobol.log` — 14 tests OK.

## Ledger authoring correction (before the first passing run)

| # | Case | What happened | Cause | Fix |
| --- | --- | --- | --- | --- |
| 1 | `BAD-LEN-93` | COBOL returned `LONG93 … BAD_AMOUNT`; ledger expected `@…`/`BAD_LENGTH` | my hand-typed raw string was 92 bytes with misaligned fields, not 93 bytes | rebuilt the raw value from its 10-byte fields plus one extra byte (`len == 93`); expectation unchanged |
| 2 | 44 cases | case names longer than 12 bytes or containing `+` cannot be claim IDs | case name was reused as the claim ID | claim ID `LDG-nnn` for those cases (`claim_id_note` in the ledger); expectations unchanged |

No expected payment, reason, CWF decision or released amount was changed to match COBOL.
