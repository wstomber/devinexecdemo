# 03 — COBOL primer, taught with this code

For engineers who have never read COBOL. Every example is from `cobol/`.

## Program shape: DIVISIONs

Each `.cob` file is one program with four divisions, in order:

```cobol
identification division.        *> name:  program-id. calculate-payment.
environment division.           *> files: select claims-file assign to input-path ...
data division.                  *> every variable, declared up front
procedure division using claim-interface.   *> the code
```

`batch.cob` is the main program (`msp-batch`); `validate.cob`, `payment.cob`
and `cwf.cob` are subprograms it `CALL`s. `*>` starts a comment.

## Paragraphs and PERFORM

Code is split into **paragraphs**: a name ending in a period
(`finish-line.`, `process-record.`). `perform finish-line` runs that paragraph
and comes back — like a function call with no arguments and no locals; all
data is shared. `perform varying i from 1 by 1 until i > 12 ... end-perform`
is a `for` loop (`validate.cob` 17). `goback` returns from the program
(`return`); `stop run` ends the whole process (`batch.cob` 267, `sys.exit`).

## PIC clauses: declared shape of data

| Declaration | Meaning | Python view |
|---|---|---|
| `pic x(12)` | 12 bytes of text, space-padded on the right | `bytes` of length 12 |
| `pic 9(10)` | 10 decimal digits, unsigned, stored as text | `int` 0…9,999,999,999, printed `f"{n:010d}"` |
| `pic 9(10) comp-3` | same range, **packed decimal** (two digits per byte) | `int` |
| `pic 9` | one digit, used as a flag | `bool`/`int` |
| `binary-long` | 32-bit binary integer | `int` |

Fixed width matters: `move claim-payment to payment-display` (`pic 9(10)`)
is what makes the CSV print `0000050000`. A `pic x` field is padded with
spaces, so `raw-id = spaces` (`validate.cob` 15) means "all 12 bytes are
spaces". Comparing `pic x` fields compares the padded values.

## COMP-3 (packed decimal)

`claim.cpy` stores parsed amounts as `pic 9(10) comp-3`: exact base-10
integers, never binary floating point. The `9(11)` for `deductions` in
`payment.cob` 6 exists because two 10-digit amounts can sum to 11 digits.
Python's `int` is exact and unbounded, so the translation keeps exactness but
must not rely on width to reject anything — widths are enforced by the input
format (10 digit characters) instead.

## Copybooks

`copy "claim.cpy".` pastes a shared declaration file in place, like a C
`#include`. `claim.cpy` declares `claim-interface` (the raw 92-byte record,
parsed fields, results); `cwf.cpy` declares the `B`/`H` reference tables.
Every program that copies them sees the same byte layout.

## REDEFINES and level numbers

`01` starts a record; `05`, `10`, `15` nest fields inside it. `raw-dos-parts
redefines raw-dos` gives a second view (year/month/day) of the same 8 bytes —
like slicing `dos[4:6]`.

## LINKAGE SECTION and CALL ... USING (by reference)

```cobol
call "validate-claim" using claim-interface          *> batch.cob 148
procedure division using claim-interface.            *> validate.cob 9
```

The subprogram's `linkage section` declares data it does **not** own; the
caller passes the address. Every `move ... to claim-reason` in
`validate.cob` writes directly into the caller's record — a mutable object
passed by reference. Python: `validate(claim, line)` mutates `claim`.

## INITIALIZE

`initialize claim-interface` (`batch.cob` 143) sets every alphanumeric field
to spaces and every numeric field to zero. This is the per-record **state
reset**: without it, a contract from record 1 could leak into record 2.
Python creates a fresh `Claim` per record.

## NUMERIC class test

`if raw-charges is not numeric` is true unless every byte is `0`–`9`. Spaces,
`+`, `-`, `.` all fail. Python's `int(" +1_0 ")` returns 10 and `"١".isdigit()`
is true, so the translation uses an explicit ASCII digit set (`is_numeric`).

## STRING

```cobol
string "@" record-count into claim-id end-string           *> "@0000000007"
string record-count "," function trim(claim-id) "," ... into output-record
```

Concatenation into a fixed field. `function trim` removes leading/trailing
spaces. Fields without `trim` keep their full PIC width (zero-padded numbers).

## EVALUATE

`evaluate true when cond-1 ... when other ... end-evaluate` is an
`if/elif/else` chain (`validate.cob` 18–31; `batch.cob` `evaluate input-status`).

## File status

Each file has a two-character status (`input-status`, `cwf-status`): `00` OK,
`10` end of file, `35` file not found, `30` permanent I/O error. `batch.cob`
checks it after every open/read/write and `perform fatal-io` on anything
unexpected; the fatal message prints the three statuses. Python maps these to
`OSError` → exit 2.

`claims-file` is `organization sequential` with 1-byte records, so the program
reads raw bytes and finds line ends itself (`batch.cob` 93–109).
`cwf-file` is `organization line sequential`: the runtime splits lines, drops
CR bytes and truncates to the 64-byte record.

## Collation: ASCII here, EBCDIC on a mainframe

`raw-id(i:1) >= "A" and <= "Z"` is a byte-range test. Under GnuCOBOL with
ASCII collation that range is exactly the 26 uppercase letters. On an IBM
mainframe with EBCDIC, `A`–`Z` is not contiguous (`I`→`J` and `R`→`S` have
gaps containing other characters), digits sort **after** letters, and space
sorts before both. A range test ported unchanged could accept extra characters
or order differently. The Python uses explicit sets (`UPPER`, `DIGITS`) and so
does not depend on collation; this matches the ASCII GnuCOBOL baseline tested
here, not an EBCDIC build.

## Reference modification

`raw-id(char-index:1)` is one byte at a 1-based position; `cwf-record(45:20)`
is 20 bytes starting at byte 45. Python: `rec[44:64]`. Off-by-one between
1-based COBOL and 0-based Python is the most common translation trap.
