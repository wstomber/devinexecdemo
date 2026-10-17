# 05 — COBOL-to-Python translation guide

The Python implementation preserves the selected byte-level interface and
payment behavior while changing program structure and memory/output handling.
The example remains a synthetic educational batch, not a complete CMS system.

## Structure and data

COBOL divides a program into named divisions, paragraphs, and shared records.
The batch driver calls validation and payment subprograms using a shared
`claim-interface`. Python places constants and related code in one module,
uses `Claim` and `Rejection` data classes for parsed outcomes, and exposes
small functions: `frame_lines`, `validate`, `calculate_payment`,
`process_batch`, formatting helpers, and `main`
([`msp.py`](../../python/msp.py#L12-L45),
[`msp.py`](../../python/msp.py#L48-L61),
[`msp.py`](../../python/msp.py#L84-L168)).

COBOL's `INITIALIZE claim-interface` clears raw and parsed fields before every
record (`batch.cob:125-131`). Python returns a newly constructed immutable
`Claim` or `Rejection` for each record; batch-level seen IDs and counters are
local to `process_batch` (`msp.py:84-121,140-168`). This is the state-reset
equivalent, not a field-for-field mechanical translation.

## Batch processing and output behavior

The COBOL driver opens output files before reading input and writes a header
and each record as it goes (`batch.cob:66-76,145-160`). A fatal condition later
in the stream can therefore leave partial output files; callers must discard
them (`batch.cob:180-184`).

Python reads the input as bytes, frames and processes the entire batch in
memory, and only then formats the output (`msp.py:209-226`). It writes each
complete file to a temporary file in that destination's directory and replaces
the destination with `os.replace` (`msp.py:181-205`). Each replacement is
atomic for its own file, but the results and totals pair is **not** a
transaction: if the second replacement fails after the first succeeds, the
outputs can be from different attempts. A fatal input/batch validation error
occurs before output writing; discard outputs on any nonzero exit regardless.

## Invariants that must stay identical

- Process bytes, not decoded text, until fixed-width byte slicing and framing
  are complete.
- Apply validation in this order: length, ID, amount text/contract syntax,
  contract range, flag. Keep the provisional `@%010d` ID until ID validation
  succeeds; a later rejection retains its real ID.
- Keep amounts as integer cents. Ten ASCII digits represent 0 through
  9,999,999,999; `D + K` can be the 11-digit value 19,999,999,998.
- Apply payment-in-full, primary-at-cap, deductions-at-cap, then positive
  payment. Use `min(G, contract-or-C) - max(D+K, P)` only after the zero
  branches.
- Retain LF framing, one-CR stripping, final partial lines, blank physical
  records, the 4,096-byte post-strip bound, and the 10,000-record limit.
- Detect duplicate real IDs even when an occurrence has a later validation
  rejection. `@` IDs are generated and excluded from duplicate tracking.
- Preserve exact CSV headers, widths, ASCII encoding, trailing newlines, and
  fatal CLI exit code 2.

## Translation traps

### ASCII numeric bytes are not general “digit” text

The input grammar is bytes in exactly `b"0123456789"`; see
[`_is_ascii_digits` and `validate`](../../python/msp.py#L80-L103). Do not replace
it with `str.isdigit()` or permissive integer parsing. `str.isdigit()` accepts
many Unicode digit characters. `int()` accepts leading signs, surrounding
whitespace, underscores in digit strings, and Unicode decimal digits, so it
does not enforce a ten-byte ASCII field. The tests include `+`, spaces,
underscore, Arabic-Indic U+0663, and full-width digits
([`test_ascii_digit_fields_reject_non_ascii_and_other_characters`](../../tests_python/test_msp.py#L82-L95)).

### Avoid floating point for cents

Binary floating-point values are not exact representations of all decimal
fractions. Parse validated digit bytes as integers, calculate in cents, and
format the integer results; this program never needs a float or `Decimal`
([`calculate_payment`](../../python/msp.py#L124-L138)).

### Bytes, text, and physical lines

`Path.read_bytes()` preserves the input byte sequence. `frame_lines` splits on
LF, removes a single trailing CR from each line, processes a nonempty final
partial line, and preserves blank lines between delimiters
([`msp.py`](../../python/msp.py#L48-L61)). A blank line is an empty record, not
EOF: it becomes `BAD_LENGTH`. Decode an ID only after its raw bytes passed the
ASCII ID check (`msp.py:90-94`).

### Malformed contract versus out-of-range contract

Only the exact ten-byte sentinel `----------` means no contract. A present
contract must be ten ASCII digits; malformed text is `BAD_AMOUNT`. Only after
it parses does `A > C` become `BAD_CONTRACT`
([`validate`](../../python/msp.py#L95-L105)).

### Duplicates include rejected records with real IDs

`process_batch` checks a non-provisional ID immediately after validation and
before deciding whether the record is rejected or paid. Therefore a record
with a valid ID but bad amount, contract, or flag still reserves that ID for
duplicate detection (`msp.py:149-153`). Do not move duplicate checking into
the valid-claim path.

### The 4,096-byte boundary includes CRLF handling

The COBOL input buffer can hold 4,097 raw bytes while a trailing CR may be
removed at line end. Thus 4,096 data bytes plus CRLF are accepted; 4,097 data
bytes are fatal, whether terminated by LF or at EOF. Python mirrors this by
checking the raw line bound before stripping a final CR and then checking the
post-strip length (`msp.py:55-60`). The named cases are in
[`test_line_size_limits_and_crlf_buffer_edge`](../../tests_python/test_msp.py#L105-L112).

### Widths differ between COMP-3 and Python integers

COBOL `PIC 9(10) COMP-3` has a fixed ten-digit range (stored in 6 bytes).
Python `int` is arbitrary precision; reject non-ten-byte or non-ASCII fields
before conversion so values cannot silently exceed the COBOL contract. The
11-digit deductions sum is intentionally supported in both implementations.

### CSV formatting is part of the interface

COBOL's fixed-width numeric items in `STRING ... INTO` produce leading zeroes.
Python must use explicit widths: record number and payment `:010d`, totals
counts `:010d`, total cents `:015d`
([formatters](../../python/msp.py#L171-L178)). A numerically equal but
un-padded output is still a mismatch.

## CMS-EX3 as a migration check

For `C=1,500,000`, `G=1,400,000`, `P=1,250,000`, `D=155,600`, `K=0`,
`A=1,300,000`, and `full=N`, the contract replaces charges. The cap is
1,300,000 and the reduction is `max(155,600,1,250,000)`, leaving
50,000 cents. Without `A`, the cap is 1,400,000 and the result is 150,000
cents. This is a selected published example, not a claim that the demo models
all Medicare payment circumstances.
