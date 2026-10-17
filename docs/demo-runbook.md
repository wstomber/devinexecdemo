# Demonstration runbook

Audience: CMS, in a customer-facing Cognition interview. Explain that this is a
synthetic educational starter based on a small public-rule subset, not CMS source
or a complete payment system. Do not use real beneficiary data.

1. **Baseline.** Run `make clean build baseline generate test` in a prepared
   environment. Open `build/baseline-report.json`: 30 records, 12 paid, 9 zero,
   9 invalid, total 10,000,450,202 cents. Show that `make compare` currently
   reports `NOT_RUN` and fails because no Python candidate exists.
2. **Inspect rules.** Open `docs/rules.md`, the shared copybook, and the payment
   paragraph. Explain how validating before numeric conversion and resetting each
   interface protects a batch. Show the lower-contract example `CMS-EX3`:
   $15,000 charges; $14,000 gross; $12,500 primary; $13,000 obligatory acceptance;
   $1,556 historical deductible; $500 secondary. Ask Devin to explain why the
   $13,000 total acceptance amount becomes the charge basis. Show the cited PDF
   pages 83–84 and the separate note about Example 4's inconsistency.
3. **Migrate with Devin.** Give Devin this repository and paste `DEVIN_TASK.md`.
   Ask it to inspect and explain the COBOL and write characterization tests
   **before** implementing Python. Keep the COBOL baseline, existing fixtures,
   expected ledger, serializer, and harness unchanged. Review its initial
   explanation and tests before showing the migration result.
4. **Run unit tests.** Have Devin report the exact test command it added for the
   candidate, its results, and examples of contract-cap, deduction-cap, malformed
   input, batch-total, and one-cent assertions. `make test` is the starter's
   infrastructure suite, not a substitute for those new Python unit tests.
5. **Compare.** After its candidate exists, run:

   ```sh
   make baseline generate test
   python3 tools/verify.py baseline --command 'python3 python/msp.py' \
     --report build/python-baseline-report.json
   make compare CANDIDATE='python3 python/msp.py'
   python3 tools/verify.py compare --candidate 'python3 python/msp.py' \
     --input build/curated.dat --report build/curated-comparison-report.json
   ```

   Review the report fields, counts, total, and any discrepancies. The valid seeded
   batch and malformed curated batch serve different coverage needs. A failed
   comparison should become a review item; do not change expectations to hide it.
6. **Review.** Inspect the candidate diff and new tests. Check exact cents,
   validation order, zero reason precedence, lower contract versus payment in
   full, overflow, and state reset. Ask for commands executed, limitations, and
   remaining policy risks. Distinguish parity from business-rule correctness;
   both implementations can agree and still be wrong outside the scoped evidence.

The replay stubs in the harness tests are temporary fault injections, not a
migration or a staged application defect. They demonstrate that missing rows,
wrong totals, and even a one-cent change with a reconciled total are detected.
There are no artificial COBOL bugs, invented benchmark claims, or implied
production-readiness claims. Let the observed test results be the evidence.
