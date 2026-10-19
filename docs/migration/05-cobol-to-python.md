# COBOL → Python: what changed, what had to stay the same, and why

The goal of the migration was **behavioral equivalence for this interface**:
for every input, the Python writes byte-identical `results.csv` and
`totals.csv` and returns the same exit code as the COBOL. That lets a
downstream system swap programs without noticing. That goal decides which
COBOL behaviors were kept exactly and which were only re-expressed.

## Construct-by-construct mapping

| COBOL construct (where) | Python in `python/msp.py` | What changed and why |
|---|---|---|
| Copybook `claim.cpy`, a shared mutable block | `@dataclass(frozen=True) Claim` and `Result` | Immutable values replace by-reference mutation. A new object per record makes state reset structural instead of something you must remember (`INITIALIZE`) |
| `claim-raw` group overlay (`move input-record(1:92) to claim-raw`) | `ID_FIELD`, `AMOUNT_FIELDS`, `CONTRACT_FIELD`, `FULL_FLAG` slices | Byte positions are now named constants. Same offsets (0-based in Python, 1-based in COBOL) |
| `pic 9(10) comp-3` packed decimal | `int` cents | Both are exact. Python `int` is unbounded; the 10-digit input width still bounds every value (see "Overflow" below) |
| `claim-has-contract` + `claim-contract` | `contract: Optional[int]` | One field instead of two that must agree |
| `IS NUMERIC` on `pic x(10)` | `is_numeric`: every byte in `DIGITS` | **Not** `str.isdigit()`, which accepts Unicode digits such as `"²"` and `"٣"`. **Not** `int()`, which accepts `"+5"`, `" 5"` and `"1_000"` |
| `>= "A" and <= "Z"` range tests | `ID_CHARACTERS` frozenset | An explicit allow-list, independent of ASCII/EBCDIC collating sequence |
| `IF … GOBACK` chains (precedence) | `if … return` chains in the same order | Order preserved exactly; it is the reason-code contract |
| `CALL "validate-claim" USING …` | `validate(record, record_no) -> (Claim, None) \| (None, Result)` | Explicit return value instead of side effects |
| `CALL "calculate-payment"` | `calculate(claim) -> Result` | Pure function; easy to unit test |
| `function min` / `function max` | `min` / `max` | Same |
| WORKING-STORAGE counters and `occurs 10000` table | `Batch` object with `seen_ids: set` | Per-batch object, not process globals. Linear search becomes O(1) set lookup; the 10,000 limit becomes an explicit `MAX_RECORDS` check |
| 1-byte sequential reads + `finish-line` | `read_records` generator + `finish_line` | Same framing rules (LF, a single trailing CR stripped, final unterminated line, blank line = record, >4,096 fatal), read in 64 KiB chunks |
| `STRING record-count …` with `pic 9(10)` | `f"{n:010d}"`, `f"{total:015d}"` | Zero padding was implicit in the PIC; now it is explicit |
| `function trim` + line-sequential trailing-space trimming | IDs `rstrip(b" ")`; no padding is ever written | The output has no trailing spaces in either program |
| `fatal-io` + `stop run`, `return-code 2` | `raise FatalBatchError` → `main()` returns 2 | An exception unwinds from any depth, like `stop run` |
| `DISPLAY … UPON SYSERR` | `print(..., file=sys.stderr)` | Message wording is diagnostic only, not part of the contract |
| `ACCEPT … FROM ARGUMENT-VALUE` | `sys.argv[1:]` | Same arity and distinct-path checks |

## What had to stay exactly the same (and how it is proven)

| Behavior | Why it matters | Proof |
|---|---|---|
| Integer-cent arithmetic | One float rounding error is a wrong payment | MAX-PAY, MAX-OTAF (1 cent at the 10-digit maximum); synthetic total of 514,352,570,951 cents matches exactly |
| OTAF replaces charges | The $500 vs $1,500 difference | CMS-EX3 / EX3-NO-OTAF in Layers A and B, plus curated parity |
| Validation precedence and reasons | Downstream systems route rejected claims by reason | V7 tests; 24-record adversarial edge batch is byte-identical |
| Malformed vs valid zero | A malformed claim must never be silently treated as "$0, fine" | AMT-SPACE vs GROSS-ZERO/OTAF-ZERO |
| Provisional `@` IDs and duplicate detection | Identity is the audit trail | B6/B7 tests; fatal-path parity |
| Framing and transport limits | Same files must give the same records | `FramingTests`; edge batch with no final newline, bare CR and CRLF |
| Counts, totals and exit codes | Reconciliation and job control | totals byte-identical on every batch; `fatal-parity.md` |

## Traps a straightforward translation would have fallen into

1. **`float` for money.** `Decimal` or `int` only. This code has no
   floating-point operations at all.
2. **`str.isdigit()` or `int()` for validation.** Both accept input COBOL
   rejects. Python's `int(b" 5")` succeeds; COBOL's `NUMERIC` test fails.
3. **Reading with `open(path)` in text mode.** Universal newlines would turn a
   bare CR into a line break and decode non-ASCII bytes, changing the record
   count. The Python reads bytes.
4. **Skipping blank lines.** COBOL counts a blank line as a `BAD_LENGTH`
   record; skipping it would shift every record number and change the totals.
5. **Treating a malformed contract as `BAD_CONTRACT`.** COBOL reports
   `BAD_AMOUNT`.
6. **Forgetting duplicate checks on rejected records.** COBOL makes a
   duplicate identifiable ID fatal even if that record is invalid.
7. **Reordering the zero-reason checks** "for readability". `PRIMARY_AT_CAP`
   must win over `DEDUCTIONS_AT_CAP`.
8. **Using `strip()` on IDs.** Leading spaces must be rejected, not trimmed.

## Overflow: a difference that cannot occur here

COBOL silently truncates results that do not fit their PIC; Python does not.
The program's widths make truncation impossible for any valid input: amounts
≤ 9,999,999,999, deductions ≤ 19,999,999,998 in a `9(11)`, and a total of at
most 10,000 × 9,999,999,999 in a `9(15)`. So no input exists for which the
two programs differ on this point. If a future change widens an input field
or raises the record limit, re-check the COBOL widths before comparing.

## What did *not* carry over and was deliberately left out

- GnuCOBOL runtime switches (`COB_LS_NULLS`, `COB_LS_VALIDATE`): there is
  nothing equivalent in Python, and the byte-level framing makes them
  irrelevant.
- `-debug` runtime checks: Python raises on index and type errors by
  default.
- stderr wording: kept similar, but not byte-identical, and not part of the
  contract.

## The CWF check

| COBOL | Python | Note |
| --- | --- | --- |
| `cwf.cpy` `occurs 1000 times` tables + `perform varying` linear search | `CwfReference.beneficiaries` (dict, first entry wins) and `history` (frozenset of `(mbi, dos, charges)`) | Same answers; first-entry-wins kept so duplicate `B` records behave alike |
| `load-cwf` / `parse-cwf`, fatal on any bad record | `load_cwf` raising `FatalBatchError` | Bytes in, CR stripped, same limits |
| `check-claim`: set reason, test, `goback` | `cwf_check` returning a new `Result` via `replace` | Same order: entitlement, duplicate, MSP primary not billed |
| `move claim-payment to claim-released` only when accepted | `released_cents=result.payment_cents` only when `ACCEPTED` | A rejection keeps the calculated payment and releases 0 |
