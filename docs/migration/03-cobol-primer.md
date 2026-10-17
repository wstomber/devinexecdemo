# 03 — A COBOL primer using this batch program

This guide explains only the COBOL constructs used by this repository's batch,
validation, and payment programs. Line citations refer to the source files shown.

## Four DIVISIONs

COBOL programs use named divisions. Here, `IDENTIFICATION DIVISION` names the
program, `ENVIRONMENT DIVISION` describes files, `DATA DIVISION` declares file,
working, and shared data, and `PROCEDURE DIVISION` contains executable paragraphs.
The short validation and payment programs omit divisions that they do not need.

```cobol
identification division.
program-id. msp-batch.
environment division.
input-output section.
file-control.
    select claims-file assign to input-path
data division.
working-storage section.
...
procedure division.
main.
```

Source: [`batch.cob`](../../cobol/batch.cob#L1-L45). Python has no equivalent
section markers: imports, constants, data classes, functions, and the `main`
entry point appear in [`msp.py`](../../python/msp.py#L1-L13) and below.

## Paragraphs, PERFORM, GOBACK, and STOP RUN

A paragraph starts with a name such as `main.` or `process-record.` and ends at
the next paragraph boundary or program end. `PERFORM paragraph-name` runs a
paragraph; `PERFORM UNTIL` and `PERFORM VARYING` express loops. `GOBACK` returns
from a program or subprogram. `STOP RUN` terminates the run unit.

```cobol
perform until eof-flag = 1
    read claims-file
    ...
end-perform
...
perform varying id-index from 1 by 1 until id-index > id-count
    ...
end-perform
...
goback.
fatal-io.
    ...
    stop run.
```

Source: [`batch.cob`](../../cobol/batch.cob#L78-L104), [duplicate loop and
fatal exit](../../cobol/batch.cob#L131-L141) and
[`fatal-io`](../../cobol/batch.cob#L180-L184). Python uses a `for` loop over
`enumerate(frame_lines(...))`, helper-function calls, `return`, and
`raise SystemExit(main())` ([`msp.py`](../../python/msp.py#L140-L168),
[`msp.py`](../../python/msp.py#L229-L230)).

## PIC X, PIC 9, and packed decimal COMP-3

`PIC X(n)` reserves `n` alphanumeric character positions; `PIC X` is one
position. `PIC 9(n)` declares numeric decimal digits. For example, `PIC 9(10)`
has ten decimal digits. The parsed claim amounts use `PIC 9(10) COMP-3`: packed
decimal stores two decimal nibbles per byte, with a sign nibble in the last byte.
Ten digits plus a sign nibble require 11 nibbles; storage rounds up to **6 bytes**
(12 nibbles, including a spare nibble). Values remain exact decimal integers,
not binary floating point.

```cobol
10 raw-charges pic x(10).
...
05 claim-charges pic 9(10) comp-3.
...
01 deductions pic 9(11) comp-3.
```

Source: [`claim.cpy`](../../cobol/copybooks/claim.cpy#L2-L22) and
[`payment.cob`](../../cobol/payment.cob#L5-L8). Python represents parsed cents
as `int` fields on an immutable `Claim`; Python integers do not have the same
fixed storage width, so the ten-byte input grammar enforces the per-field range
([`Claim`](../../python/msp.py#L24-L35),
[`validate`](../../python/msp.py#L84-L121)).

## Copybooks

A copybook is reusable COBOL source included where the `COPY` statement appears.
This shared record definition keeps the caller and called programs aligned on
field names, widths, and types.

```cobol
copy "claim.cpy".
```

Source: [`batch.cob`](../../cobol/batch.cob#L40-L45),
[`validate.cob`](../../cobol/validate.cob#L7-L9),
[`payment.cob`](../../cobol/payment.cob#L9-L11), and
[`claim.cpy`](../../cobol/copybooks/claim.cpy#L1-L22). Python centralizes the
parsed interface in the `Claim` data class and uses `Rejection` for invalid
records ([`msp.py`](../../python/msp.py#L24-L45)).

## LINKAGE SECTION and CALL ... USING

`LINKAGE SECTION` declares data supplied by a caller. `PROCEDURE DIVISION USING`
receives that record; without a `BY VALUE` phrase, these calls use the COBOL
default of passing the argument by reference. `validate-claim` and
`calculate-payment` therefore see the same `claim-interface` storage and can
write parsed values, status, payment, and reason back into it.

```cobol
linkage section.
copy "claim.cpy".
procedure division using claim-interface.
```

The caller uses:

```cobol
call "validate-claim" using claim-interface
...
call "calculate-payment" using claim-interface
```

Sources: [`validate.cob`](../../cobol/validate.cob#L7-L10),
[`payment.cob`](../../cobol/payment.cob#L9-L12), and
[`batch.cob`](../../cobol/batch.cob#L129-L144). Python uses explicit return
values instead of mutating a caller-owned record:
`validate` returns `Claim | Rejection` and `calculate_payment` returns a
`(status, cents, reason)` tuple ([`msp.py`](../../python/msp.py#L84-L121),
[`msp.py`](../../python/msp.py#L124-L138)).

## INITIALIZE

`INITIALIZE claim-interface` resets each elementary field according to its
category: alphanumeric fields become spaces and numeric fields become zero.
Here it runs for every record before raw bytes and parsed values are populated,
preventing a previous contract or amount from leaking into the next record.

```cobol
initialize claim-interface
move spaces to claim-id
string "@" record-count into claim-id end-string
```

Source: [`batch.cob`](../../cobol/batch.cob#L119-L131). Python has no shared
mutable record to clear: `validate` constructs a fresh `Claim` or `Rejection`
for each line, while `process_batch` initializes per-batch collections and
counters ([`msp.py`](../../python/msp.py#L84-L121),
[`msp.py`](../../python/msp.py#L140-L168)).

## IS NUMERIC on PIC X

`IS NUMERIC` is a class condition: it tests whether the bytes in an alphanumeric
field satisfy COBOL's numeric-character class. This code applies it to the
raw fixed-width amount text before moving that text into packed-decimal fields.
The sequence matters: malformed text is rejected before conversion or
arithmetic.

```cobol
if raw-charges is not numeric or raw-gross is not numeric
   or raw-primary is not numeric or raw-deductible is not numeric
   or raw-coinsurance is not numeric
    goback
end-if
```

Source: [`validate.cob`](../../cobol/validate.cob#L34-L50). Python is stricter
about the required byte encoding: `_is_ascii_digits` explicitly checks each
byte against `b"0123456789"` before `int()` is called
([`msp.py`](../../python/msp.py#L80-L82),
[`msp.py`](../../python/msp.py#L95-L103)).

## STRING ... INTO and zero-padded numeric fields

`STRING ... INTO` concatenates source values into a receiving field. In this
program, `record-count`, `payment-display`, and the totals counters are numeric
items declared at fixed PIC widths. When moved into the string, they occupy
their declared decimal width, so leading zeros are part of the CSV interface.
The code trims only the fixed-width text status, ID, and reason.

```cobol
string record-count "," function trim(claim-id) ","
    function trim(claim-status) "," payment-display ","
    function trim(claim-reason) into output-record
end-string
```

Source: [`batch.cob`](../../cobol/batch.cob#L34-L39),
[`batch.cob`](../../cobol/batch.cob#L145-L157), and
[`batch.cob`](../../cobol/batch.cob#L95-L101). Python spells out the widths in
format specifications (`:010d` and `:015d`)
([`msp.py`](../../python/msp.py#L171-L178)).

## Reference modification and EVALUATE TRUE

Reference modification selects a substring by one-based start and length:
`raw-id(char-index:1)` selects one character at `char-index`. `EVALUATE TRUE`
then evaluates its `WHEN` clauses in order, like an ordered decision chain.
Here, the ID scanner tracks when trailing padding has begun and rejects any
later non-space character.

```cobol
evaluate true
  when raw-id(char-index:1) = space
    move 1 to id-ended
  when id-ended = 1
    goback
  when raw-id(char-index:1) >= "A" and <= "Z"
    continue
...
end-evaluate
```

Source: [`validate.cob`](../../cobol/validate.cob#L16-L32). Python iterates the
12 raw ID bytes and uses explicit byte ranges and membership tests
([`_valid_id`](../../python/msp.py#L64-L77)).

## FILE STATUS, `"00"`, `"10"`, and fatal-io

The `FILE STATUS` item receives a two-character status after file operations.
In this program, `"00"` is successful I/O and `"10"` is the sequential-read
end-of-file condition. Other statuses take the fatal path. `fatal-io` writes a
diagnostic, sets return code 2, and stops the run unit.

```cobol
select claims-file assign to input-path
    organization sequential file status input-status.
...
evaluate input-status
  when "10" ...
  when "00" ...
  when other perform fatal-io
end-evaluate
```

Source: [`batch.cob`](../../cobol/batch.cob#L5-L11),
[`batch.cob`](../../cobol/batch.cob#L26-L29),
[`batch.cob`](../../cobol/batch.cob#L78-L93), and
[`batch.cob`](../../cobol/batch.cob#L180-L184). Python represents file failures
as `OSError`, catches them with `FatalBatchError`, prints to standard error, and
returns 2 ([`msp.py`](../../python/msp.py#L209-L226)).

## FUNCTION MIN, MAX, and TRIM

`FUNCTION MIN` and `FUNCTION MAX` return the smaller or larger numeric argument.
`FUNCTION TRIM` removes surrounding spaces from text before CSV concatenation.
These are intrinsic functions; they do not invoke repository code.

```cobol
compute payment-cap = function min(claim-gross, charge-basis)
compute reduction-amount = function max(deductions, claim-primary)
...
function trim(claim-reason)
```

Source: [`payment.cob`](../../cobol/payment.cob#L24-L35) and
[`batch.cob`](../../cobol/batch.cob#L151-L155). Python uses built-in `min` and
`max`; it emits the already-trimmed decoded ID and static status/reason strings
([`msp.py`](../../python/msp.py#L93-L103),
[`msp.py`](../../python/msp.py#L124-L138)).

## ASCII and EBCDIC collation: a porting trap

The ID check uses `>= "A" AND <= "Z"` and the analogous digit range
([`validate.cob`](../../cobol/validate.cob#L23-L26)). Under the ASCII collation
used by this GnuCOBOL/Linux build, letters and digits in these ranges are
contiguous, so this check has the intended ASCII behavior. In common EBCDIC
collating sequences, letters are split into groups (`A`–`I`, `J`–`R`, `S`–`Z`)
with nonletters in the code-point gaps. A single comparison range from `"A"` to
`"Z"` can therefore admit intervening nonletters on an EBCDIC runtime. This is
a general encoding/collation portability warning, **not** a claim about CMS
systems. A port to an EBCDIC environment should use a character-class test or
explicitly test each permitted range under that environment's collating
sequence. Python's implementation here processes bytes and applies the ASCII
byte ranges directly (`_valid_id`, [`msp.py`](../../python/msp.py#L64-L77)).
