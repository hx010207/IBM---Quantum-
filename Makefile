# Makefile for Quantum Fingerprinting & Spoofing Detection

PYTHON ?= python

.PHONY: all dryrun test clean select probe simulate features experiments figures tables audit

all: test features experiments figures tables audit

dryrun: test
	$(PYTHON) scripts/01_select_backends.py --dry-run
	$(PYTHON) scripts/02_budget_probe.py --dry-run
	$(PYTHON) -c "import subprocess, sys; [subprocess.run([sys.executable, 'scripts/03_collect_round.py', '--round-id', str(r), '--dry-run'], check=True) for r in range(1, 9)]"
	$(PYTHON) scripts/04_simulate.py --dry-run --rounds 8
	$(PYTHON) scripts/05_build_features.py --dry-run
	$(PYTHON) scripts/06_run_experiments.py --dry-run
	$(PYTHON) scripts/07_make_figures.py --dry-run
	$(PYTHON) scripts/08_make_tables.py --dry-run
	$(PYTHON) scripts/09_claims_audit.py --dry-run

test:
	$(PYTHON) -m pytest tests/

features:
	$(PYTHON) scripts/05_build_features.py

experiments:
	$(PYTHON) scripts/06_run_experiments.py

figures:
	$(PYTHON) scripts/07_make_figures.py

tables:
	$(PYTHON) scripts/08_make_tables.py

audit:
	$(PYTHON) scripts/09_claims_audit.py

clean:
	rm -rf __pycache__ .pytest_cache
