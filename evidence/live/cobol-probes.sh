#!/usr/bin/env bash
# Stage 1 characterization probes of the COBOL runtime's file handling (GnuCOBOL 3.1.2).
# These observe interface/runtime behavior only; no payment values are taken from here.
set -u
B=${MSP_COMMAND:-$(pwd)/build/msp-batch}
W=$(mktemp -d); cd "$W"
GOODB="B1EG4TE5MK732020010199999999----------------"
mk(){ python3 -c "
import sys
i,c,g,p,d,k,a,f,m,s=sys.argv[1:]
print(i.ljust(12)+''.join(x.zfill(10) if x!='-' else '-'*10 for x in (c,g,p,d,k,a))+f+m+s)" "$@"; }
mk ORDINARY 100000 80000 20000 10000 5000 - N 1EG4TE5MK73 20250315 > in.dat
mk DUPCHK 1500000 1400000 1250000 0 0 - N 5HIST000001 20250315 >> in.dat
probe(){ rm -f o.csv t.csv; $B in.dat cwf.dat o.csv t.csv 2>err.txt; rc=$?
  echo "$1: exit=$rc rows=$(sed -n '2,3p' o.csv 2>/dev/null | cut -d, -f2,6,7 | tr '\n' ' ')"; }
printf '%s\n' "$GOODB" > cwf.dat; probe "B record, LF"
printf '%s\r\n' "$GOODB" > cwf.dat; probe "B record, CRLF"
printf '%s\r\r\n' "$GOODB" > cwf.dat; probe "B record, CR CR LF"
printf 'B1EG4TE5MK73\r2020010199999999----------------\n' > cwf.dat; probe "CR inside a CWF line (dropped)"
printf '%s' "$GOODB" > cwf.dat; probe "no final newline"
printf '%s          \n' "$GOODB" > cwf.dat; probe "B + 10 trailing spaces"
printf '%s%sX\n' "$GOODB" "$(printf ' %.0s' {1..19})" > cwf.dat; probe "X at byte 64"
printf '%s%sX\n' "$GOODB" "$(printf ' %.0s' {1..20})" > cwf.dat; probe "X at byte 65 (ignored)"
printf '%s                    H5HIST000001202503150001500000\nB5HIST00000120200101999999992025010120251231\n' "$GOODB" > cwf.dat; probe "bytes past 64 discarded, not a new record"
printf '%s\t\n' "$GOODB" > cwf.dat; probe "TAB at byte 45"
printf 'B1EG4TE5MK7\t2020010199999999----------------\n' > cwf.dat; probe "TAB inside MBI (kept as data)"
printf 'B1EG4TE5MK7\0002020010199999999----------------\n' > cwf.dat; probe "NUL inside MBI (kept as data)"
printf '\f%s\n' "$GOODB" > cwf.dat; probe "form feed before B"
printf '' > cwf.dat; probe "empty CWF file"
printf '\r' > cwf.dat; probe "CWF file containing only CR"
printf '\n' > cwf.dat; probe "CWF blank line"
printf '\r\n' > cwf.dat; probe "CWF CRLF-only line"
printf 'B1eg4te5mk732020010199999999----------------\n' > cwf.dat; probe "lowercase MBI in CWF (accepted, never matches)"
printf 'B1EG4TE5MK732026010199999999----------------\n%s\n' "$GOODB" > cwf.dat; probe "duplicate B MBI (first wins)"
printf 'B1EG4TE5MK7320201301999999992025019920250000\n' > cwf.dat; probe "numeric but impossible CWF dates (accepted)"
printf 'B1EG4TE5MK732020010199999999--------20251231\n' > cwf.dat; probe "half-dashed MSP period"
printf 'b1EG4TE5MK732020010199999999----------------\n' > cwf.dat; probe "lowercase record type"
printf '' > cwf.dat; for i in $(seq 1000); do echo "B$(printf 'X%010d' $i)2020010199999999----------------"; done >> cwf.dat; probe "1000 B records"
echo "$GOODB" >> cwf.dat; probe "1001 B records"
printf '' > cwf.dat; for i in $(seq 1000); do echo "H$(printf 'X%010d' $i)202501010000000001"; done >> cwf.dat; probe "1000 H records"
echo "H5HIST000001202503150001500000" >> cwf.dat; probe "1001 H records"
mkdir -p cwfdir; rm -f o.csv t.csv; $B in.dat cwfdir o.csv t.csv 2>/dev/null; echo "CWF path is a directory: exit=$? rows=$(sed -n '2,3p' o.csv | cut -d, -f2,6,7 | tr '\n' ' ')"
printf '%s\n' "$GOODB" > cwf.dat
head -1 in.dat > dup.dat; head -1 in.dat >> dup.dat; echo old > o.csv; echo old > t.csv
$B dup.dat cwf.dat o.csv t.csv 2>/dev/null; echo "duplicate ID at record 2: exit=$? results_lines=$(wc -l < o.csv) totals_bytes=$(wc -c < t.csv)"
echo old > o.csv; echo old > t.csv; printf 'X\n' > bad.cwf; $B in.dat bad.cwf o.csv t.csv 2>/dev/null
echo "bad CWF: exit=$? results=$(cat o.csv) totals=$(cat t.csv) (outputs untouched)"
echo old > o.csv; $B nope.dat cwf.dat o.csv t.csv 2>/dev/null; echo "missing input: exit=$? results=$(cat o.csv) (untouched)"
mkdir -p indir; rm -f o.csv; $B indir cwf.dat o.csv t.csv 2>/dev/null; echo "input is a directory: exit=$? results_lines=$(wc -l < o.csv)"
echo old > o.csv; $B in.dat cwf.dat o.csv nodir/t.csv 2>/dev/null; echo "unopenable totals: exit=$? results_bytes=$(wc -c < o.csv)"
$B a b c 2>/dev/null; echo "3 arguments: exit=$?"; $B a b c d e 2>/dev/null; echo "5 arguments: exit=$?"
$B in.dat cwf.dat o.csv o.csv 2>/dev/null; echo "same output/totals string: exit=$?"
$B in.dat cwf.dat o.csv "o.csv " 2>/dev/null; echo "'o.csv' vs 'o.csv ' (trailing space): exit=$?"
$B in.dat cwf.dat o.csv ./o.csv 2>/dev/null; echo "'o.csv' vs './o.csv' alias: exit=$? (aliases not detected)"
rm -f o.csv; $B "in.dat " cwf.dat o.csv t.csv 2>/dev/null; echo "input path with trailing space: exit=$?"
$B "" cwf.dat o.csv t.csv 2>/dev/null; echo "empty input path: exit=$?"
rm -rf "$W"
