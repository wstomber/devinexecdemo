# 03 — COBOL primer for engineers who have never read COBOL

Every example below is from this repository's code. Line numbers refer to
`cobol/batch.cob`, `cobol/validate.cob`, `cobol/payment.cob`, `cobol/copybooks/claim.cpy`.
This is GnuCOBOL 3.1.2 free-format source running on Linux (ASCII). COBOL keywords are
case-insensitive; this code uses lowercase.

## 1. DIVISIONs: the four fixed sections of a program

A COBOL program is split into DIVISIONs, always in this order:

| Division | Purpose | Here |
|---|---|---|
| `identification division.` | Name of the program (`program-id.`) | `msp-batch`, `validate-claim`, `calculate-payment` |
| `environment division.` | Binds logical files to the outside world | batch.cob 3–11 (`select claims-file assign to input-path ...`) |
| `data division.` | **All** variables, declared up front. No local variables exist elsewhere. | batch.cob 12–44 |
| `procedure division.` | The executable code | batch.cob 45 onward |

Inside the DATA DIVISION, `file section` describes file record buffers, `working-storage section`
is static program memory (it keeps its value between calls), and `linkage section` describes
memory that belongs to a caller (see §5).

Python equivalent: there isn't one. Python declares variables where they are used; in COBOL
you read the DATA DIVISION first to know every piece of state the program can touch.

## 2. Paragraphs and PERFORM: functions without arguments

A procedure division is a list of **paragraphs**: a name followed by a period, then statements
until the next paragraph name. batch.cob has `main`, `finish-line`, `process-record`,
`write-result`, `write-totals`, `close-files`, `fatal-io`.

- `perform finish-line` (batch.cob 86) runs that paragraph and comes back — like calling a
  function with no parameters and no return value. All communication is through shared
  working-storage variables (`input-length`, `input-record`, `record-count`, ...).
- `perform until eof-flag = 1 ... end-perform` (78–94) is a `while` loop.
- `perform varying char-index from 1 by 1 until char-index > 12` (validate.cob 17) is a
  `for char_index in range(1, 13)` loop.
- `goback` returns from the program (to the caller or the OS). `stop run` (batch.cob 184)
  ends the whole run unit immediately — this is how `fatal-io` aborts from anywhere.
- `evaluate true / when ... / when other` (validate.cob 18–31) is an `if/elif/else` chain;
  the first true `when` wins.

The period matters: it ends a sentence and closes any open `if`. This code uses explicit
`end-if` / `end-perform` scope terminators to avoid that trap.

## 3. PIC clauses and COMP-3: the type system

A `pic` (PICTURE) clause describes a field's exact size and kind:

| Declaration | Meaning | Python view |
|---|---|---|
| `raw-id pic x(12)` (claim.cpy 64) | 12 bytes of any characters, space padded | `bytes` of length 12 |
| `record-count pic 9(10)` (batch.cob 34) | unsigned 10-digit decimal, stored as display digits | `int` 0..9,999,999,999, printed zero-padded to 10 |
| `payment-total pic 9(15)` (38) | 15-digit unsigned | `int`, printed with `:015d` |
| `claim-charges pic 9(10) comp-3` (claim.cpy 76) | **packed decimal**: two digits per byte plus a sign nibble (6 bytes for 10 digits) | `int`; exact, no binary rounding |
| `deductions pic 9(11) comp-3` (payment.cob 6) | 11 digits, because deductible + coinsurance can exceed 10 digits | `int` (Python never overflows) |
| `char-index binary-long` (validate.cob 5) | 32-bit binary integer | `int` |

Key properties: no `9(n)` here has a sign or decimal point, so every amount is a whole number
of cents and can never be negative. COMP-3 is exact decimal arithmetic — the reason COBOL
financial code doesn't drift — and the reason the Python must use `int`, never `float`.
If a COMPUTE result has more digits than the target PIC, COBOL silently truncates high digits
unless `ON SIZE ERROR` is coded; this code sizes fields so that cannot happen within the
README maxima (payment ≤ 9,999,999,999; total ≤ 10,000 × that = 14 digits ≤ `9(15)`).

`05`/`10` level numbers build nested records: `claim-raw` (63) is a group of eight fields that
together occupy exactly 73 bytes, so `move input-record(1:73) to claim-raw` (batch.cob 129)
slices one line into eight fields in a single move — the role of Python's byte slices.

## 4. Copybooks: shared declarations

`copy "claim.cpy".` pastes the copybook text in at compile time, like a C `#include`.
All three programs copy the same `claim-interface` (batch.cob 44 into working-storage;
validate.cob 8 and payment.cob 10 into linkage). That guarantees the three programs agree on
the byte layout of the shared record. In Python the equivalent contract is the `Claim`/`Outcome`
dataclasses and the slice constants in `python/msp.py`.

## 5. LINKAGE SECTION and CALL ... USING (by reference)

`call "validate-claim" using claim-interface` (batch.cob 131) passes the caller's
`claim-interface` **by reference** (COBOL's default). The callee declares the same layout in
its `linkage section` and `procedure division using claim-interface` (validate.cob 9).
There is no copy and no return value: the callee writes `claim-status`, `claim-reason`,
`claim-id`, and parsed amounts directly into the caller's memory. payment.cob then reads and
writes the same block. Python replaces this with explicit return values
(`validate_record` returns a tuple; `calculate_payment` returns status, reason, cents).

## 6. INITIALIZE: resetting state

`initialize claim-interface` (batch.cob 126) sets every alphanumeric field to spaces and every
numeric field to zero — including `claim-has-contract` (back to 0) and `claim-payment`
(back to 0). Because the block is reused for all 10,000 records, forgetting this would let a
contract or payment from a previous record leak into the next. The Python creates fresh objects
per record, so leakage is structurally impossible; the Stage 2 `sequences` tests still check it.

## 7. NUMERIC class test

`if raw-charges is not numeric` (validate.cob 35) is true unless every byte of the PIC X field
is a digit `0`–`9`. Spaces, `+`, `-`, `.`, `_`, or any non-ASCII byte make it not numeric.
It runs before any `move raw-x to claim-x` (validate.cob 45–50), because moving non-digits into a
numeric field gives undefined/implementation-specific results. Python's `int("00000_0001")`,
`int(" +1")` and `"١".isdigit()` all succeed, which is why `python/msp.py` uses an explicit
ASCII digit set (`is_numeric`).

## 8. STRING: building text

`string "@" record-count into claim-id end-string` (batch.cob 128) concatenates `"@"` and the
10-digit display form of `record-count` → `@0000000001`. STRING does **not** clear the target
first, so the code does `move spaces to claim-id` just before (127). The output row is built the
same way (152–156) with `function trim(...)` removing padding; numbers keep their full
`pic 9(10)` width, which is why every count and payment is zero-padded to 10 digits.

## 9. File status

Each `select` names a two-character status variable (`file status input-status`, batch.cob 7).
After every OPEN/READ/WRITE/CLOSE the program checks it: `"00"` = OK, `"10"` = end of file
(81), anything else → `perform fatal-io` (92). Errors are not exceptions; if you don't check the
status, the program continues. This code checks every I/O operation. Python's `OSError` handling
in `main` plays the same role.

The input is declared `record contains 1 characters` (14–15) so the program reads **one byte at a
time** and frames lines itself (85–91) instead of trusting the runtime's LINE SEQUENTIAL rules.

## 10. EBCDIC collation (why the ID check is written as ranges)

`raw-id(char-index:1) >= "A" and <= "Z"` (validate.cob 23) compares by the platform's
**collating sequence**. On this ASCII build `A`–`Z` is a contiguous range of 26 letters.
On an IBM mainframe using EBCDIC (e.g. code page 037) letters sit in three blocks
(`A`–`I` X'C1'–X'C9', `J`–`R` X'D1'–X'D9', `S`–`Z` X'E2'–X'E9'), so the same range test would
also admit the code points in the gaps (for example X'D0' `}` and X'E0' `\` in CP037), and digits
sort *after* letters. This is an inference from the code-page tables; it was **not** tested on an
EBCDIC system. The Python uses an explicit set of allowed bytes, matching the ASCII build that
was tested, not a hypothetical EBCDIC deployment.
