# Chronological Fingerprinting and Spoofing Detection of IBM Quantum Backends

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Qiskit 2.5](https://img.shields.io/badge/qiskit-2.5.2-purple.svg)](https://qiskit.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A rigorous, reproducible research framework investigating whether black-box measurement statistics from fixed quantum circuits can uniquely fingerprint IBM Quantum backends across chronological collection rounds, and whether noise-model simulators can successfully impersonate genuine hardware.

---

## Repository Structure

```text
.
├── configs/
│   └── study.yaml              # Backends, physical layouts, circuits, shots, splits, budget
├── src/qfp/                    # Core library implementation
│   ├── __init__.py
│   ├── budget.py               # 85% QPU budget safety guard & execution time projector
│   ├── circuits.py             # 10 benchmark circuits (Bell, GHZ, Clifford, Mirror)
│   ├── collect.py              # Resumable, idempotent hardware & dryrun collector
│   ├── detect.py               # Integrity detectors (Mahalanobis, OC-SVM, IsoForest, TVD)
│   ├── features.py             # 196-dim statistical feature extraction engine
│   ├── metrics.py              # ROC-AUC, EER, TPR@1/5% FPR, FAR/FRR, round bootstrap CIs
│   ├── models.py               # Supervised classifiers (LR, SVM, RF, GradBoost, MLP)
│   ├── plotting.py             # IEEE style plotting engine (Figs 1-12 + source CSVs)
│   ├── provenance.py           # Strict provenance enforcement (ibm_hardware vs dryrun)
│   ├── simulate.py             # S0 (ideal), S1 (calibration), S2 (adaptive) simulators
│   └── splits.py               # Round-level chronological and leakage splits
├── scripts/                    # Numbered, deterministic pipeline workflow
│   ├── 01_select_backends.py   # Discover operational backends & optimize 3-qubit layouts
│   ├── 02_budget_probe.py      # Probe 1 circuit, measure QPU time, project allowance
│   ├── 03_collect_round.py     # Collect an individual round (idempotent & resumable)
│   ├── 04_simulate.py          # Generate matching S0, S1, S2 adversary rounds
│   ├── 05_build_features.py    # Compile raw records into feature matrix
│   ├── 06_run_experiments.py   # Execute Experiments E1 through E7
│   ├── 07_make_figures.py      # Generate publication Figures 1-12
│   ├── 08_make_tables.py       # Generate publication Tables T1-T5 (CSV + LaTeX)
│   └── 09_claims_audit.py      # Systematically audit empirical findings vs claims
├── data/                       # Append-only production data (strictly ibm_hardware)
├── dryrun/                     # Synthetic test pipeline outputs (tagged synthetic_dryrun)
├── results/                    # Production metrics, figures, tables, and results.json
├── tests/                      # Unit test suite (provenance, splits, features, circuits)
├── Makefile                    # Automation target for POSIX environments
├── run_all.py                  # Cross-platform reproduction runner
├── METHODS_NOTES.md            # Factual technical protocol and execution log
├── LIMITATIONS_OBSERVED.md     # Observed hardware & experimental limitations
├── requirements.txt            # Pinned dependency specifications
└── STATUS.md                   # Chronological project progress & milestones
```

---

## Non-Negotiable Research Integrity Rules

1. **Strict Provenance Guard**: Every data row carries an immutable provenance tag (`ibm_hardware`, `aer_ideal`, `aer_noise_model`, or `synthetic_dryrun`). Figure and table scripts strictly refuse to evaluate synthetic data in publication mode.
2. **Chronological Splitting**: Train (rounds 1-4), validation (rounds 5-6), test (rounds 7-8). Samples are chunked within rounds, but splitting is strictly by whole `round_id`. Random splitting is evaluated solely as a labeled leakage comparison.
3. **QPU Budget Protection**: The IBM Open Plan allowance (10 minutes = 600s in 28 days) is strictly guarded. Before submission, projected QPU seconds are checked and must never exceed 85% ($510.0$ seconds).
4. **Append-Only Immutability**: Raw measurement files are never modified or overwritten.

---

## Quickstart & Dry-Run Pipeline Verification

To verify the entire experimental workflow locally using fake backend snapshots:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit tests
python -m pytest tests/

# 3. Execute the full end-to-end dry-run pipeline
python run_all.py --dry-run
```

All dry-run artifacts, figures (watermarked "SYNTHETIC - NOT FOR PUBLICATION"), tables, metrics, and claims audits will be created inside `dryrun/`.

---

## Hardware Execution Workflow (Stages 1-2)

When ready to execute on real IBM Quantum hardware:

```bash
# 1. Authenticate with IBM Quantum (never commit tokens)
export QISKIT_IBM_TOKEN="your_ibm_api_token"

# 2. Select operational backends and optimize layouts
python scripts/01_select_backends.py

# 3. Probe QPU execution time and confirm budget feasibility
python scripts/02_budget_probe.py

# 4. Collect rounds at scheduled intervals (e.g. 2 rounds per day)
python scripts/03_collect_round.py --round-id 1

# 5. Generate matching simulations, features, and run experiments
python scripts/04_simulate.py
python scripts/05_build_features.py
python scripts/06_run_experiments.py
python scripts/07_make_figures.py
python scripts/08_make_tables.py
python scripts/09_claims_audit.py
```

---

## License
MIT License. Copyright (c) 2026.
