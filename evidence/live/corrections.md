# Stage 3 corrections

| # | Symptom (failing test/probe) | Root cause | Fix |
|---|---|---|---|
| 1 | First `tests_python` discovery run failed to import `msp` (`ModuleNotFoundError`). | `unittest discover -s tests_python` adds the test directory rather than the repository root as the import location. | Import the implementation through the repository namespace package: `from python.msp import ...`. |
| 2 | `test_validation_precedence` failed two assertions for `BAD_LENGTH` and `BAD_ID`. | Expected provisional claim IDs were strings, while validation returns claim IDs as bytes. | Compare against byte strings for both provisional IDs. |
| 3 | Fatal parity mismatched file-status text in `output-dir-missing` and `totals-dir-missing`; Python emitted `35` where COBOL emitted `30`. | `ENOENT` maps to `35` for input-file open failure, but output and totals open failures use COBOL status `30`, including missing parent directories. | Keep input status mapping and set output/totals open failures to `30`. |
| 4 | Self-review found that validation tests did not combine later invalid fields with each earlier precedence case, framing tests omitted exact-limit CRLF and oversized CRLF/no-newline cases, and CWF parser tests did not cover a non-ASCII byte beyond column 64. | The initial tests exercised individual reasons, boundaries, and ignored ASCII suffix bytes, but did not prove their ordering or the high-byte suffix behavior. | Add combined invalid-field precedence cases, framing boundaries, and an ignored high-byte suffix; no implementation behavior change was needed. |
