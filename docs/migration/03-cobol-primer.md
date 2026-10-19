# 03 — COBOL primer for engineers who have never read COBOL

Every construct below is taught with a line from this repository (`cobol/`, starter
`be0b00e`). Read with `01-cobol-explanation.md` (what the program does) and
`04-legacy-walkthrough.md` (CMS-EX3 traced line by line).

## 1. A program is four DIVISIONs

```cobol
identification division.        *> batch.cob 1  – name of the program
program-id. msp-batch.
environment division.           *> batch.cob 3  – which files exist and how they are read
input-output section.
file-control.
    select claims-file assign to input-path
        organization sequential file status input-status.
data division.                  *> batch.cob 14 – every variable, declared up front
procedure division.             *> batch.cob 57 – the code
```

There are no local variables, no heap and no function signatures in the Python sense:
all storage is declared in the DATA DIVISION, sized at compile time, and lives for the
whole run. `WORKING-STORAGE` is the program's own memory; `FILE SECTION` holds the
record buffer each `READ`/`WRITE` uses; `LINKAGE SECTION` describes memory owned by a
caller (§6).

## 2. Paragraphs and PERFORM

A *paragraph* is a label followed by statements ending in a period:
`process-record.` (batch.cob 136), `fatal-io.` (263). `PERFORM fatal-io` jumps to the
paragraph and comes back at its end — like calling a function with no arguments and no
return value; it reads and writes the shared WORKING-STORAGE. `PERFORM VARYING … UNTIL`
is the loop:

```cobol
perform varying char-index from 1 by 1 until char-index > 11      *> validate.cob
```

Python equivalent: `for char_index in range(1, 12):`. COBOL indexes from **1**, and
`raw-id(char-index:1)` is *reference modification* — the substring starting at position
`char-index` of length 1 (`raw_id[char_index-1:char_index]`). `GOBACK` returns from a
subprogram (like `return`); `STOP RUN` ends the whole process (like `sys.exit`).
`EVALUATE TRUE / WHEN …` is an if/elif chain; the first true `WHEN` wins.

## 3. PIC: the shape of every field

`PIC` (picture) fixes type and size:

| Declaration | Meaning | Python mental model |
| --- | --- | --- |
| `raw-id pic x(12)` (claim.cpy 3) | 12 bytes of any character, space-padded | `bytes` of length 12 |
| `record-count pic 9(10)` (batch.cob 45) | unsigned 10-digit decimal, stored as 10 ASCII digits | `int` 0…9,999,999,999 that prints zero-padded |
| `claim-gross pic 9(10) comp-3` (claim.cpy 22) | same range, packed decimal (below) | `int` |
| `input-length binary-long` (batch.cob 36) | 32-bit binary integer | `int` |
| `claim-has-contract pic 9` (claim.cpy 27) | one digit | `bool` |

Moving a `9(10)` into display text produces exactly 10 zero-padded digits — that is why
`payment_cents` prints as `0000050000`. Moving text into a shorter `X` field truncates on
the right; into a longer one pads with spaces. `9` fields have **no sign**: a negative
result would silently lose its sign, which is why `payment.cob` tests the zero cases
*before* it subtracts (§4 of the walkthrough).

**COMP-3 (packed decimal)** stores two decimal digits per byte plus a sign nibble:
`pic 9(10) comp-3` takes 6 bytes; `1250000` is `x"00001250000F"`. It is exact decimal
arithmetic — no binary floating point — so cents never round. Python's `int` is the
faithful replacement; `float` is not. `deductions pic 9(11) comp-3` (payment.cob 6) has
one extra digit so deductible + coinsurance (two 10-digit maxima) cannot overflow.

`REDEFINES` gives a second view of the same bytes: `raw-dos-parts redefines raw-dos`
(claim.cpy 13) lets the code read `raw-dos-month` without copying.

## 4. Copybooks

`copy "claim.cpy".` (batch.cob 55, validate.cob, payment.cob, cwf.cob) pastes the file
`cobol/copybooks/claim.cpy` in at compile time. All four programs therefore share one
layout of `claim-interface` — like a shared dataclass definition, except it is a byte
layout, so a field's position matters, not just its name. `01`, `05`, `10`, `15` are
level numbers: higher numbers are nested inside the previous lower number (a group).

## 5. Files, records and FILE STATUS

`select results-file … organization line sequential file status output-status`
(batch.cob 10–11): a text file, one record per line; after every `OPEN`/`READ`/`WRITE`/
`CLOSE` the runtime stores a two-character code in `output-status`. `"00"` is success,
`"35"` is "file not found", `"30"` a permanent I/O error. COBOL does not raise
exceptions: the program must check the status itself, and this one does after every
operation (`if output-status not = "00" perform fatal-io`, batch.cob 243). The fatal
message prints all three statuses, e.g. `file status 35/  /  ` (input missing; outputs
never opened, so still spaces).

The claim input is deliberately *not* line sequential: `fd claims-file record contains
1 characters` (batch.cob 16) reads one byte at a time so CR/LF handling and the 4,096-byte
limit are coded explicitly (batch.cob 93–135) rather than left to the runtime.

## 6. CALL … USING and LINKAGE (by reference)

```cobol
call "validate-claim" using claim-interface                  *> batch.cob 148
procedure division using claim-interface.                     *> validate.cob 9
```

`CALL` runs another compiled program. `USING` passes the **address** of
`claim-interface`; the callee's `LINKAGE SECTION` (via the same copybook) describes that
memory. When `validate-claim` executes `move "BAD_ID" to claim-reason`, it writes
straight into the caller's record. Python equivalent: passing one mutable object that
the function updates in place — or, more idiomatically, returning a new value. Nothing is
returned explicitly; all results are side effects on shared memory.

## 7. INITIALIZE

`initialize claim-interface` (batch.cob 143) sets every alphanumeric field to spaces and
every numeric field to zero. Because storage is permanent (§1), without it the second
record would still see the first record's values — for example `claim-has-contract = 1`
left over from a rejected record. In Python, building a fresh object per record gives
this for free; the trap is reusing a dict or class attribute across records.

## 8. The NUMERIC class test

`if raw-charges is not numeric` (validate.cob) is true unless **every** byte of the
10-byte `PIC X` field is `0`–`9`. Spaces, signs, decimal points, underscores and non-ASCII
digits all fail. Python's `str.isdigit()` accepts `'٣'` and `'³'`, and `int()` accepts
`' 12'`, `'+12'` and `'1_2'`, so neither is a substitute; the port checks each byte
against `b"0123456789"`.

## 9. STRING

```cobol
string record-count "," function trim(claim-id) "," … released-display
    into output-record
end-string                                                      *> batch.cob 182–187
```

Concatenates pieces into `output-record` (cleared to spaces first, line 181). `FUNCTION
TRIM` removes leading and trailing spaces, so a 12-byte `CMS-EX3     ` prints as
`CMS-EX3`. `string "@" record-count into claim-id` (batch.cob 145) builds the provisional
ID `@0000000021` because `record-count` is a 10-digit display field. When the line
sequential file is written, trailing spaces of the record are dropped.

## 10. EBCDIC collation

COBOL compares alphanumeric data by the machine's character order. This code runs under
GnuCOBOL on Linux (ASCII), where `"A"`–`"Z"` and `"0"`–`"9"` are contiguous and digits sort
before letters. On an IBM mainframe (EBCDIC) letters are in three non-contiguous blocks
(`A`–`I`, `J`–`R`, `S`–`Z`) with other code points between them, and digits sort *after*
letters. So `raw-id(char-index:1) >= "A" and <= "Z"` (validate.cob) admits extra
non-letter bytes under EBCDIC, and any alphabetic ordering of mixed letters/digits
changes. The port reproduces the **ASCII** behaviour that was actually executed and
tested here; moving the COBOL to EBCDIC hardware would itself need re-testing. Date and
amount comparisons are on numeric fields and are unaffected.
