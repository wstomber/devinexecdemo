# Devin task: explain, characterize, then migrate the COBOL batch to Python

Work in this repository on a new branch. It is a synthetic educational CMS MSP
prospective-payment demonstration, not production CMS source or a full claims
processor. Read README.md and docs/rules.md, including the source page references,
scoped assumptions, and the published Example 4 inconsistency.

Implement and execute the migration; do not stop with a plan.

1. Inspect and explain the COBOL batch driver, validation module, payment module,
   and shared copybook. State the formula, contractual acceptance interpretation,
   validation precedence, valid-zero reason precedence, file contract, limits,
   exit codes, and assumptions. Explain the published $500 contractual acceptance
   example in business terms.
2. Build and run the existing COBOL baseline. Create characterization tests
   **before** writing the Python implementation. Show the commands/results and
   commit these tests separately so their ordering is reviewable. Derive tests
   from observed interface behavior and the existing independent ledger without
   replacing that ledger. Add tests for gaps you discover.
3. Implement a small Python CLI at `python/msp.py` (or document your chosen path).
   Preserve `INPUT OUTPUT TOTALS`, fixed-width parsing, CSV headers, assigned
   sequence numbers, identifiers, statuses, reason codes, precedence, invalid
   versus valid-zero distinction, counts, total, record limits, and fatal behavior.
   Use integer cents or exact decimal arithmetic; never binary floating point.
   Treat identifiers as text, missing amounts as errors, and monetary limits
   deliberately. Do not translate only the happy path.
4. Add focused unit tests for the new implementation and batch integration tests.
   Cover the contractual cap, deductible plus coinsurance, primary and deductions
   at/above caps, full-payment precedence, zero/one-cent/max boundaries, malformed
   input, duplicate IDs, consecutive records, and totals. Report and run your
   candidate's unit-test command separately from the starter's infrastructure tests.
5. Execute at least:

   ```sh
   make build baseline generate test
   python3 tools/verify.py baseline --command 'python3 python/msp.py' \
     --report build/python-baseline-report.json
   make compare CANDIDATE='python3 python/msp.py'
   python3 tools/verify.py compare --candidate 'python3 python/msp.py' \
     --input build/curated.dat --report build/curated-comparison-report.json
   ```

   Run the candidate unit tests too. The 1,000 valid synthetic records expand
   coverage; matching them does not establish policy correctness. Include the
   malformed curated batch. Check both exact amounts and status/reason behavior.
6. Review the result and open a PR. Report the exact commands, results, record
   counts and totals, reports, any unexecuted checks, limitations, and remaining
   risks. Explain business-rule correctness separately from output parity. Do not
   claim a comparison ran if the candidate or required runtime was unavailable.

Keep the existing `cobol/` baseline, `fixtures/`, `tools/`, starter infrastructure
tests, and verification contract unchanged. Add candidate code and new tests in
separate files. Do not replace independent expectations with candidate or COBOL
output. Do not weaken tests, ignore errors, or change reason codes to obtain a
pass. Treat discrepancies between source, baseline behavior, and interpretation
as explicit review items; report them before making any policy changes.

The deliverable is a working Python migration with reviewable tests and measured
comparison evidence. No web interface, cloud deployment, or performance claims
are required.
