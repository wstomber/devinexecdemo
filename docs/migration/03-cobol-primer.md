# 03 — A COBOL primer for engineers who have never read COBOL

All examples come from this repository's `cobol/` directory. Compiled with GnuCOBOL in free format (`cobc -free`).

## DIVISIONs: the four fixed sections of every program
A COBOL program is split into DIVISIONs in a fixed order:
* `identification division.` names the program: `program-id. calculate-payment.` (payment.cob:1-2). Other programs `CALL` it by that name.
* `environment division.` maps logical files to physical ones. In batch.cob:6-13, `select claims-file assign to input-path` binds a file name to the variable `input-path`.
* `data division.` declares **all** variables up front. `file section` describes record buffers, `working-storage section` holds program-lifetime variables (static, kept between CALLs), and `linkage section` describes memory owned by the caller.
* `procedure division.` holds the code.

## Paragraphs and PERFORM
Code is organized into named **paragraphs** (`main.`, `finish-line.`, `process-record.` in batch.cob). A paragraph runs until the next paragraph name. `perform finish-line` calls it like a no-argument subroutine and then returns. All state is global to the program. `perform varying char-index from 1 by 1 until char-index > 12 … end-perform` is a `for` loop (validate.cob:17). `goback` returns from the program, much like `return`, and `stop run` ends the whole process (batch.cob:267).

## PIC clauses: every variable has a fixed shape
* `pic x(12)`: 12 bytes of any characters (a fixed-width string, space-padded).
* `pic 9(10)`: 10 decimal digits stored as text ("display" numeric), so `0000050000` is 50,000.
* `binary-long`: a 32-bit integer.
* Moving a value into a smaller field truncates it silently, and a shorter string is padded with spaces. Comparing two alphanumeric fields pads the shorter one with spaces, so `"A"` equals `"A   "`. This is why the Python strips trailing spaces from IDs and paths.

## COMP-3 (packed decimal)
`pic 9(10) comp-3` (claim.cpy:21-28) stores 10 decimal digits two per byte. Arithmetic on these fields is exact base-10 arithmetic, so there is never any binary floating point. The Python equivalent is a plain `int` of cents. `compute payment-cap = function min(claim-gross, charge-basis)` is exact integer math.

## Copybooks
`copy "claim.cpy".` pastes the shared record layout into the program at compile time, like a C `#include`. All four programs see the same `claim-interface` layout: raw 92 bytes, then parsed fields, then results. `redefines` (claim.cpy:13) gives a second view of the same bytes: `raw-dos-parts` splits the 8-byte date into year, month and day without copying.

## LINKAGE SECTION and CALL … USING (by reference)
`call "validate-claim" using claim-interface` (batch.cob:148) passes the **address** of the caller's record. The callee declares it in `linkage section` and changes it in place. There is no return value: results come back by mutating the shared record. The Python passes a `Claim` object and mutates its attributes for the same reason.

## INITIALIZE
`initialize claim-interface` (batch.cob:143) sets every alphanumeric field to spaces and every numeric field to zero. It runs once per record, so a contract parsed for record 5 cannot affect record 6. Python gets the same guarantee by creating a new `Claim()` per record.

## NUMERIC class test
`if raw-charges is not numeric` (validate.cob:35) is true unless **every** byte is `0`-`9`. Spaces, signs, decimal points, TAB, NUL and non-ASCII bytes all fail. Python's `str.isdigit()` and `int()` are more permissive: they accept Unicode digits, `+`, surrounding whitespace and `_`. That is why `is_digits` checks membership in an explicit ASCII byte set.

## STRING
`string record-count "," function trim(claim-id) "," … into output-record` (batch.cob:182) concatenates fields. A `pic 9(10)` source contributes all 10 digits, which is why CSV numbers are zero-padded (`0000050000`). `function trim` removes leading and trailing spaces.

## File status
Each `select` names a two-character status variable (`file status input-status`). After every OPEN, READ, WRITE or CLOSE the program checks it: `00` = OK, `10` = end of file, `3x` = permanent error (`35` = not found, `30` = I/O error, `31` = bad name). Any unexpected status goes to `fatal-io` → exit 2.

## LINE SEQUENTIAL vs record sequential
The claims file is read as a sequential file of 1-byte records (`record contains 1 characters`), so the program sees every raw byte and does its own framing. The CWF file is `line sequential`, so the GnuCOBOL runtime splits lines. Under GnuCOBOL 3.1.2 that runtime drops CR bytes and truncates lines at the 64-byte record (see `evidence/live/cobol-probes.log`). Python reproduces this deliberately in `cwf_lines`.

## EBCDIC collation (why the range checks are a trap)
`raw-id(char-index:1) >= "A" and <= "Z"` (validate.cob:23) is correct here because GnuCOBOL uses ASCII, where `A`-`Z` is a contiguous range. On an IBM mainframe the native code page is EBCDIC. There the letters fall in three runs (A-I, J-R, S-Z) with other characters between them, and digits sort **after** letters. The same source compiled there would accept characters such as `}` or `\` inside the "letter" range and would order IDs differently. Python avoids the issue by testing set membership (`UPPER`, `DIGITS`) instead of ranges. Never port a COBOL range check as `"A" <= c <= "Z"` without first confirming the source platform's collating sequence.
