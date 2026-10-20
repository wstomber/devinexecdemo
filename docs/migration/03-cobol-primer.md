# 03 — COBOL primer for engineers who have never read COBOL

Every concept here is taught with code from this repository's `cobol/`
directory. Line numbers are per file.

## 1. DIVISIONs: the four fixed sections of a program

Each program is laid out top to bottom in four parts:

```cobol
identification division.        *> name: program-id. msp-batch.   (batch.cob l.1-2)
environment division.           *> which files exist and how they are organised (l.3-13)
data division.                  *> every variable, declared up front (l.14-56)
procedure division.             *> the code (l.57-)
```

`batch.cob` holds four programs, one after another (`msp-batch`,
`validate-claim`, `calculate-payment` and `cwf-check` come from the four files
compiled together). Each one ends with `end program`. Read a program as you would
a Python module. The DATA DIVISION is its globals, and the PROCEDURE DIVISION is
its functions.

## 2. Paragraphs and PERFORM

A paragraph is a label followed by a period, such as `finish-line.` (batch.cob
l.122). `perform finish-line` runs that paragraph and returns, much like calling
a function with no arguments. Paragraphs share every variable, so there are no
locals. `perform until eof-flag = 1 ... end-perform` is a `while` loop. `perform
varying id-index from 1 by 1 until id-index > id-count` is a `for` loop with
1-based indexes (batch.cob l.150).

`goback` returns from the current program. `stop run` ends the whole process
(batch.cob l.267). In `validate-record`, `goback` works like an early `return`:
the reason code most recently moved into `claim-reason` is the one the caller
sees.

## 3. PIC clauses: a variable's type is its picture

| Declaration | Meaning | Python analogue |
| --- | --- | --- |
| `pic x(12)` (`raw-id`) | 12 bytes of characters, space-padded | `bytes` of length 12 |
| `pic 9(10)` (`record-count`) | 10 decimal digits, stored as ASCII digits | `int` 0..9,999,999,999, displayed zero-padded |
| `pic 9(10) comp-3` (`claim-charges`) | 10 digits **packed decimal** (two digits per byte) | exact `int`, never `float` |
| `pic 9(15)` (`payment-total`) | 15-digit total | `int` |
| `binary-long` (`claim-length`) | 32-bit binary integer | `int` |
| `pic 9` (`claim-has-contract`) | one digit used as a flag | `bool` |

No PIC has a `V` (implied decimal point) or an `S` (sign). Every amount is
unsigned integer cents. Moving a larger value into a smaller PIC silently drops
the high digits. That is why the deduction sum is `pic 9(11)` (payment.cob l.8).
Two 10-digit maxima add up to 11 digits.

`STRING record-count "," ... INTO output-record` (batch.cob l.182) concatenates.
A `pic 9(10)` field is always rendered as 10 digits, which is why the CSV shows
`0000000001`. The Python port reproduces this with `f"{n:010d}"`.

## 4. COMP-3 (packed decimal)

`comp-3` stores the digit pairs 1,2,3 as the bytes `x"12" x"3F"`. The last
nibble holds the sign. Arithmetic on these fields is exact decimal arithmetic.
COBOL payment systems use it so that cents never round. In Python, the faithful
equivalent is `int` cents (or `decimal.Decimal`). **`float` is never correct
here.**

## 5. Copybooks: shared record layouts

`copy "claim.cpy".` pastes `cobol/copybooks/claim.cpy` in at compile time, like
a C `#include`. All four programs copy the same `claim-interface`, so they agree
byte for byte on the layout. `raw-dos-parts redefines raw-dos` gives the same 8
bytes a second view, as year/month/day. Think of it as a `memoryview` slice over
the same bytes.

## 6. LINKAGE SECTION and CALL ... USING (by reference)

`call "validate-claim" using claim-interface` (batch.cob l.148) passes the
*address* of the caller's record. The callee declares it in its `linkage
section` (validate.cob l.7–8) and writes straight into it. COBOL's default is
BY REFERENCE, which works like passing a mutable object in Python. The port
models this with a mutable `Claim` dataclass that each function updates in
place.

## 7. INITIALIZE: the per-record reset

`initialize claim-interface` (batch.cob l.143) sets every alphanumeric field to
spaces and every numeric field to zero. Without it, `claim-has-contract = 1` from
a rejected record would leak into the next one. The Python equivalent is creating
a fresh `Claim(...)` for every record. Ledger cases RESET-REJ → RESET-NEXT prove
the reset.

## 8. NUMERIC class test

`if raw-charges is not numeric` (validate.cob l.35) is true unless every byte is
`0`–`9`. Spaces, `+`, `-`, `.` and tabs all fail. Python's `str.isdigit()`
accepts `'٣'` (Arabic-Indic three) and `int()` accepts `' +1_0'`, so the port
uses an explicit ASCII digit set (`msp.DIGITS`).

## 9. File status

Every `select ... file status input-status` (batch.cob l.6–13) names a two-byte
code that is set after each OPEN, READ, WRITE or CLOSE. `"00"` means OK and
`"10"` means end of file. Anything else here leads to `fatal-io`. There are no
exceptions. Every I/O statement is followed by an `if ... status not = "00"`
check. Python raises `OSError` instead, and the port maps it to exit 2.

`organization line sequential` (the CWF and output files) means text lines.
`organization sequential` with `record contains 1 characters` (the claims file)
reads raw bytes one at a time. The COBOL does its own framing for that file.

## 10. EBCDIC collation: why `>= "A" and <= "Z"` is not portable

validate.cob l.23 checks letters with `raw-id(char-index:1) >= "A" and <= "Z"`.
In ASCII (GnuCOBOL here), A–Z are 0x41–0x5A with no gaps, so the test is
exact. On an IBM mainframe the native code page is EBCDIC. There, `A`–`I`,
`J`–`R` and `S`–`Z` are three separate runs (0xC1–0xC9, 0xD1–0xD9, 0xE2–0xE9),
and the range also takes in bytes such as 0xCA–0xD0 that are not letters. Digits
(0xF0–0xF9) also sort *after* letters in EBCDIC, so any string comparison or
sort that mixes letters and digits orders differently. When porting a mainframe
program, confirm which collating sequence produced the reference outputs. This
repository is ASCII. The port uses explicit byte sets, which are exact under ASCII
and would need re-review if the input encoding changed.
