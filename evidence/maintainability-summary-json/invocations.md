# `--summary-json` CLI invocation examples

These commands were run from the repository root after the implementation.
The curated input is `build/curated.dat`. Successful CLI invocations produce
no stdout or stderr; their output artifacts are listed below.

## No flag

```sh
python3 python/msp.py build/curated.dat build/invocation-examples/no-flag-results.csv build/invocation-examples/no-flag-totals.csv
```

Exit code: `0`; stdout/stderr: empty. The totals file ends with:

```text
0000000030,0000000012,0000000009,0000000009,000010000450202
```

## Flag before the positionals

```sh
python3 python/msp.py --summary-json build/invocation-examples/before.json build/curated.dat build/invocation-examples/before-results.csv build/invocation-examples/before-totals.csv
```

Exit code: `0`; stdout/stderr: empty. `build/invocation-examples/before.json`:

```json
{"records": 30, "paid": 12, "zero": 9, "invalid": 9, "payment_cents": 10000450202}
```

## `--summary-json=PATH`

```sh
python3 python/msp.py build/curated.dat build/invocation-examples/equals-results.csv build/invocation-examples/equals-totals.csv --summary-json=build/invocation-examples/equals.json
```

Exit code: `0`; stdout/stderr: empty. `build/invocation-examples/equals.json`
contains the same JSON object shown above.

## Collision with input

```sh
python3 python/msp.py build/curated.dat build/invocation-examples/collision-results.csv build/invocation-examples/collision-totals.csv --summary-json build/curated.dat
```

Exit code: `2`; stdout: empty; stderr:

```text
--summary-json PATH must differ from INPUT, OUTPUT and TOTALS
```

## Unwritable summary destination

The summary parent directory `build/invocation-examples/missing-summary-dir/`
does not exist.

```sh
python3 python/msp.py build/curated.dat build/invocation-examples/unwritable-results.csv build/invocation-examples/unwritable-totals.csv --summary-json build/invocation-examples/missing-summary-dir/summary.json
```

Exit code: `2`; stdout: empty; stderr:

```text
fatal batch failure; discard outputs; cannot write summary JSON: [Errno 2] No such file or directory: '/home/ubuntu/repos/devinexecdemo/build/invocation-examples/missing-summary-dir/.summary.json.gb2ess1r.tmp'
```

## Fatal duplicate claim ID

The fatal input is two copies of the same valid 73-byte claim record followed
by LF. The command uses `build/invocation-examples/fatal-duplicate.dat`.

```sh
python3 python/msp.py build/invocation-examples/fatal-duplicate.dat build/invocation-examples/fatal-results.csv build/invocation-examples/fatal-totals.csv --summary-json build/invocation-examples/fatal.json
```

Exit code: `2`; stdout: empty; stderr:

```text
fatal batch failure; discard outputs; duplicate claim ID: DUP
```

The JSON summary is not created on this fatal run.
