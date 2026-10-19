PYTHON ?= python3
COBC ?= cobc
COBFLAGS ?= -Wall -debug
BASELINE ?= build/msp-batch
CANDIDATE ?=
export CANDIDATE

.PHONY: build baseline generate compare test doctor capture-baseline clean
build: build/msp-batch

build/msp-batch: cobol/batch.cob cobol/validate.cob cobol/payment.cob cobol/cwf.cob cobol/copybooks/claim.cpy cobol/copybooks/cwf.cpy
	mkdir -p build
	$(COBC) -x -free $(COBFLAGS) -I cobol/copybooks -o $@ cobol/batch.cob cobol/validate.cob cobol/payment.cob cobol/cwf.cob

baseline: build
	$(PYTHON) tools/verify.py baseline --command '$(BASELINE)' --report build/baseline-report.json

generate:
	$(PYTHON) tools/fixtures.py --cwf-source fixtures/cwf.json --output build/cwf.dat
	$(PYTHON) tools/fixtures.py --source fixtures/curated.json --output build/curated.dat
	$(PYTHON) tools/fixtures.py --count 1000 --seed 20261017 --output build/synthetic.dat --readable-output build/synthetic.json

compare: build generate
	$(PYTHON) tools/verify.py compare --command '$(BASELINE)' --candidate "$$CANDIDATE" --report build/comparison-report.json

test: baseline
	$(PYTHON) -m unittest discover -s tests -v

doctor:
	$(PYTHON) tools/capture_baseline.py --check-only --compiler '$(COBC)'

capture-baseline: build
	$(PYTHON) tools/capture_baseline.py --command '$(BASELINE)' --compiler '$(COBC)'

clean:
	rm -rf build tools/__pycache__ tests/__pycache__

.PHONY: demo demo-live demo-refresh
demo: build generate
	-git fetch -q origin pull/23/head 2>/dev/null
	$(PYTHON) demo/server.py

demo-live: build generate
	-git fetch -q origin pull/23/head 2>/dev/null
	$(PYTHON) demo/server.py --require-devin-key

demo-refresh: build generate
	$(PYTHON) demo/server.py --run-once
