# COBOL for new engineers, taught with this program

This page is for an engineer who has never read COBOL and has to maintain,
review, or migrate a program like the one in `cobol/`. Every concept is
explained with a line from this repository, and with its Python equivalent
where that helps. It covers only what you need to read *this* code. It is not
a complete COBOL course.

> Context: this is a synthetic educational program, not CMS production code. It
> is compiled here with GnuCOBOL 3.1.2 on Linux (ASCII). Production mainframe
> COBOL (IBM Enterprise COBOL on z/OS, EBCDIC) adds JCL, VSAM, CICS and DB2,
> none of which appear here.

## 1. Why COBOL looks the way it does

COBOL (1959) was designed for business record processing, so that
non-specialists could read the code. Three ideas explain most of the
strangeness:

1. **Data is described by its layout, not its type.** A field is "10
   characters" or "10 decimal digits", not `str` or `int`. The layout *is* the
   contract with files and other programs.
2. **Memory is declared up front, statically.** All variables live in the DATA
   DIVISION. There are no local variables, no `new`, no garbage collection.
3. **Decimal arithmetic is native.** Money is stored as exact decimal digits,
   which is why COBOL has stayed in finance and government for decades.

## 2. Program structure: the four DIVISIONs

```cobol
identification division.        *> name of the program
program-id. calculate-payment.
environment division.           *> files and the outside world (batch.cob only)
data division.                  *> every variable, with its exact layout
procedure division using claim-interface.   *> the code
```

| COBOL | What it means | Python analogy |
|---|---|---|
| `IDENTIFICATION DIVISION` / `PROGRAM-ID` | The program's name, used by `CALL` | module or function name |
| `ENVIRONMENT DIVISION`, `FILE-CONTROL`, `SELECT … ASSIGN TO` | Binds a logical file name to a path variable and an organization | `open(path, mode)` |
| `DATA DIVISION` → `FILE SECTION` | The record layout of each file | the shape of the bytes you read and write |
| `WORKING-STORAGE SECTION` | Variables owned by this program. They persist for the life of the run | module-level globals |
| `LINKAGE SECTION` | Variables that belong to the **caller**, passed in | function parameters (by reference) |
| `PROCEDURE DIVISION USING x` | The executable code; `USING` lists the parameters | `def f(x):` |

## 3. Paragraphs, PERFORM, GOBACK, STOP RUN

The PROCEDURE DIVISION is divided into **paragraphs**: a name followed by a
period, for example `finish-line.` in `batch.cob` line 105. A paragraph is like
a function with no parameters and no return value. It reads and writes the
shared WORKING-STORAGE.

| COBOL | Meaning | Python analogy |
|---|---|---|
| `perform finish-line` | Run that paragraph, then come back | `finish_line()` operating on globals |
| `perform until eof-flag = 1 … end-perform` | Loop while a condition is false | `while not eof:` |
| `perform varying char-index from 1 by 1 until char-index > 12` | Counted loop (1-based) | `for i in range(1, 13):` |
| `goback` | Return to the caller. In the main program it ends the program | `return` |
| `stop run` | End the **entire run unit** immediately, from anywhere | `sys.exit(2)` |
| `move 2 to return-code` | Set the process exit status | the value passed to `sys.exit` |

Watch for: control can fall through from one paragraph into the next unless
something stops it. `main` ends in `goback.` so it never falls into
`finish-line`. `fatal-io` uses `stop run` because it is reached from deep
inside nested PERFORMs and must abort the whole batch. In Python this became
`raise FatalBatchError`.

## 4. PIC clauses: how data is described

`PIC` (PICTURE) defines a field's size and kind character by character.

| Clause in this code | Meaning | Storage | Python |
|---|---|---|---|
| `pic x(12)` (`raw-id`) | 12 alphanumeric bytes, space-padded | 12 bytes | `bytes` of length 12 |
| `pic x` (`raw-full`) | one byte | 1 byte | `bytes` of length 1 |
| `pic 9` (`claim-has-contract`) | one unsigned decimal digit | 1 byte, ASCII digit | `bool` / small `int` |
| `pic 9(10)` (`record-count`) | 10 unsigned digits, "display" (one character per digit) | 10 bytes | `int`, printed with `f"{n:010d}"` |
| `pic 9(15)` (`payment-total`) | 15 unsigned digits | 15 bytes | `int` |
| `pic 9(10) comp-3` (`claim-charges`) | 10 digits **packed decimal** | 6 bytes | `int` (cents) |
| `binary-long` (`claim-length`) | 32-bit binary integer | 4 bytes | `int` |
| `pic x(4097)` (`input-record`) | fixed buffer | 4,097 bytes | `bytearray` |

**`9(10)` means "nine repeated ten times"**: ten digit positions, so the
maximum is 9,999,999,999. In cents, that is $99,999,999.99 per field.

**No `S` means unsigned.** `pic 9(10)` cannot hold a negative number. That is
part of why negative and signed inputs are rejected.

**No `V` means no decimal point.** There is no implied decimal (`9(8)V99`)
anywhere. Every amount is whole cents, so `0001300000` is 1,300,000 cents =
$13,000.00.

### Packed decimal (`COMP-3`) and why it guarantees exact money

`COMP-3` stores two decimal digits per byte, plus a final half-byte (nibble)
for the sign. A 10-digit field needs 11 nibbles, so it occupies 6 bytes: the
value 1,300,000 is held as the digit nibbles `0 0 0 1 3 0 0 0 0 0` followed by
a sign nibble. Arithmetic on it is
done **in decimal**, not in binary floating point. 0.1 + 0.2 is exactly 0.3,
and every cent is exact.

The Python equivalent is a plain `int` holding cents. The dangerous
translation is `float`: `float("13000.00") - float("12500.00")` happens to
work here, but sums over thousands of claims and values like 0.1 do not stay
exact. `python/msp.py` never uses `float`.

### Field width is a business rule, and overflow is silent

COBOL stores a result into whatever width the receiving field has. If a
`COMPUTE` result does not fit, the high-order digits are **silently
truncated** unless the code says `ON SIZE ERROR`. This program has no
`ON SIZE ERROR`, so its widths are chosen to make overflow impossible:

- `deductions pic 9(11)`: deductible + coinsurance can reach 19,999,999,998
  (11 digits). A `9(10)` field here would have silently lost the leading `1`.
- `payment-total pic 9(15)`: 10,000 records × 9,999,999,999 fits in 14 digits.

Python's `int` never overflows. That is safer, but it means a translation will
not reproduce a COBOL truncation bug if one exists. Here the widths make
overflow impossible, so the behavior is identical. The maximum-value tests
(MAX-PAY, MAX-DEDUCT, edge batch EDGE-MAX) prove it.

## 5. Level numbers, group items and copybooks

```cobol
01 claim-interface.              *> group: the whole parameter block
   05 claim-raw.                 *> group: the 73 raw bytes
      10 raw-id       pic x(12). *> bytes 1-12
      10 raw-charges  pic x(10). *> bytes 13-22
      …
   05 claim-charges   pic 9(10) comp-3.   *> parsed value
```

- **Level numbers** (01, 05, 10) express nesting. A group item with no PIC is
  simply the concatenation of its children's bytes.
- `move input-record(1:73) to claim-raw` (`batch.cob` 129) copies 73 bytes
  into the group. That **simultaneously fills all eight raw fields by
  position**. No parsing happens; the layout *is* the parser. Python does this
  with explicit slices (`ID_FIELD = slice(0, 12)`, and so on).
- **`COPY "claim.cpy"`** pastes the copybook text in at compile time, like a C
  `#include`. All three programs copy the same layout, which is how they agree
  on the shape of a claim. A copybook is therefore an interface definition.
  Changing it means recompiling every program that copies it. In Python the
  equivalent is the shared `Claim` and `Result` dataclasses.

## 6. CALL, LINKAGE and pass-by-reference

```cobol
call "validate-claim" using claim-interface      *> batch.cob 131
…
procedure division using claim-interface.        *> validate.cob 31
    move "INVALID" to claim-status               *> writes the CALLER's memory
```

By default COBOL passes parameters **by reference**. When `validate-claim`
moves `"BAD_ID"` to `claim-reason`, it writes directly into `batch.cob`'s
`claim-interface`. There is no return value: the "result" is whatever the
called program left in the shared block. `batch.cob` then reads `claim-status`
to decide whether to call `calculate-payment`.

Python made this explicit: `validate()` returns `(Claim, None)` or
`(None, Result)`, and `calculate()` returns a new `Result`. Nothing is mutated
behind the caller's back.

## 7. Statements you will meet in this code

| Statement | Example | Meaning | Python |
|---|---|---|---|
| `MOVE` | `move "ZERO" to claim-status` | Assign, padding or truncating to the receiver's PIC. Alphanumeric receivers are space-padded on the right | `status = "ZERO"` |
| `MOVE` alphanumeric → numeric | `move raw-charges to claim-charges` | Converts digit characters to a number. **Undefined if the source is not digits**, hence the `NUMERIC` checks first | `int(field)` after validation |
| `IF … END-IF` | `if claim-primary >= payment-cap` | Condition | `if` |
| Abbreviated condition | `raw-id(i:1) >= "A" and <= "Z"` | The subject is implied on the right side | `b"A" <= c <= b"Z"` |
| Multiple values | `= "-" or "_"` | Either value | `c in b"-_"` |
| `EVALUATE TRUE … WHEN … WHEN OTHER` | `validate.cob` 40–53 | Switch where the **first** true `WHEN` wins | `if/elif/else` |
| `COMPUTE` | `compute payment-cap = function min(claim-gross, charge-basis)` | Arithmetic expression | `min(...)` |
| `ADD`, `SUBTRACT` | `add 1 to record-count` | In-place arithmetic | `+= 1` |
| Intrinsic functions | `function min`, `function max`, `function trim` | Built-ins | `min`, `max`, `.strip()` |
| `IS NUMERIC` | `if raw-charges is not numeric` | True only if **every** byte is `0`–`9` (for an unsigned PIC X field: no sign, no point, no spaces) | `all(b in DIGITS for b in field)` |
| `= SPACES` | `if raw-id = spaces` | Every byte is a space | `field == b" " * 12` |
| Reference modification | `input-record(input-length:1)` | Substring `(start:length)`, **1-based** | `record[n-1:n]` |
| `INITIALIZE` | `initialize claim-interface` | Reset every field: alphanumeric to spaces, numeric to zero | construct a fresh object |
| `STRING … INTO … END-STRING` | `string "@" record-count into claim-id` | Concatenate. A `pic 9(10)` source contributes all 10 digits, **including leading zeros** | `f"@{n:010d}"` |
| `ACCEPT … FROM ARGUMENT-VALUE` | `accept input-path from argument-value` | Read the next command-line argument | `sys.argv` |
| `DISPLAY … UPON SYSERR` | error messages | Write to stderr | `print(..., file=sys.stderr)` |
| `SET ENVIRONMENT` | `set environment "COB_LS_NULLS" to "N"` | Set a GnuCOBOL runtime option | n/a (Python has no equivalent setting) |
| `OCCURS 10000 TIMES` | `seen-id pic x(12) occurs 10000 times` | Fixed-size array. The size is part of the business limit | `set()` plus an explicit `MAX_RECORDS` check |
| `*>` | `*> Demo reason precedence…` | Comment (free format) | `#` |

## 8. Files and FILE STATUS

```cobol
select claims-file assign to input-path
    organization sequential file status input-status.
fd claims-file record contains 1 characters.
01 input-byte pic x.
```

- `organization sequential` with a 1-character record means the program reads
  the input **one byte at a time** and finds line ends itself. The comment at
  `batch.cob` 62–63 says why: GnuCOBOL's `LINE SEQUENTIAL` reading
  (text-line mode) truncates long lines in version-dependent ways, so the
  author took explicit control of framing.
- `organization line sequential` (the outputs) writes text lines with a
  newline. GnuCOBOL trims the trailing spaces of the fixed `pic x(160)`
  buffer, which is why output rows have no padding.
- After every `OPEN`, `READ`, `WRITE` and `CLOSE`, COBOL puts a two-character
  **file status** in the declared variable. `"00"` means success and `"10"`
  means end of file (`batch.cob` 80–92). Anything else is treated as fatal
  here. Without these checks, I/O errors in COBOL are easy to miss. Python
  raises `OSError` instead.

## 9. Historical gotchas worth knowing before you touch COBOL

1. **Collating sequence.** `>= "A" and <= "Z"` compares by the machine's
   character encoding. In ASCII, A–Z are contiguous. In **EBCDIC** (IBM
   mainframes) they are not: there are gaps between I and J and between R and
   S. On a mainframe this same line would accept a few non-letter bytes. The
   Python uses an explicit allowed-character set (`ID_CHARACTERS`), so it does
   not depend on encoding. Any real migration must decide which behavior is
   intended.
2. **Fixed-width records.** A field is identified by its byte position, not a
   delimiter. One extra byte shifts every following field, which is why length
   is the first check (`BAD_LENGTH`).
3. **Implicit state.** WORKING-STORAGE survives between records. Forgetting
   `INITIALIZE` would let a contract amount from record 7 leak into record 8.
   The RESET-SRC → RESET-NEXT tests exist for exactly this reason.
4. **Order is behavior.** In both `validate.cob` and `payment.cob`, the order
   of the `IF … GOBACK` blocks *is* the precedence rule. Reordering them
   changes which reason code is reported, and sometimes changes which records
   get paid.
5. **Silent truncation.** See §4: width is a business rule.
6. **Undefined numeric moves.** Moving non-digits to a numeric field produces
   garbage, not an error. That is why the comment at `validate.cob` 67 states
   that no numeric move precedes the class tests.

Next: `04-legacy-walkthrough.md` applies all of this to the three programs line
by line, and `05-cobol-to-python.md` shows what changed in the migration.
