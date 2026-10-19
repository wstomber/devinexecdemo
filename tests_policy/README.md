# Stage 2 independent tests (written before any Python)

* `expectations.json` holds the hand-derived ledger: 92 records run as one batch. Each one has
  a `source` citation, an `arithmetic` derivation and a `kind`:
  * `policy` cases rest on CMS text (Pub. 100-05 Ch. 5 §40.8–40.8.3, Examples 1 and 3;
    Pub. 100-04 Ch. 27 §20; Pub. 100-05 Ch. 5 §10.1);
  * `interface` cases rest on the README's demo contract (layout, reason codes, precedence,
    limits, IDs, CWF reject codes). These are this repository's decisions, not CMS policy.
* `cwf_reference.json` is new synthetic CWF reference data, written for this ledger
  (MBIs `7…`). It does not reuse `fixtures/cwf.json`.
* `test_ledger.py` runs the ledger and reconciles its totals; `test_batch.py` covers
  framing, CRLF/no final newline, empty input, duplicate IDs, the 4,096/4,097-byte and
  10,000/10,001-record limits, usage/path errors, and missing or malformed CWF files.
* The program under test is chosen with `MSP_COMMAND` (shlex-split, default `build/msp-batch`):

```sh
python3 -m unittest discover -s tests_policy -v                                   # COBOL
MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v  # Python
```

No expected value was copied from COBOL output or `fixtures/expected.json`. Only after
the derivation was written did I cross-check it against the starter ledger: CMS-EX1
(150,000) and CMS-EX3 (50,000) agree with `fixtures/expected.json` records 1 and 2.

The ledger and CWF tests were then run against COBOL, and all 92 records matched on the first
run. These test-construction mistakes were fixed before that run; none came from a ledger
value: (1) 34 case names were longer than the 12-byte ID field, so they were renamed;
(2) the non-ASCII length test used 46×`é` = 92 bytes (a valid length) instead of 47×`é` = 94 bytes;
(3) the transport test put a line with no newline before another record, which joined
the two lines into one. Neither the ledger nor the batch tests are a proof of Medicare correctness. They check the scoped
rules as this repository interprets them.
