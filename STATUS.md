# Project Status & Milestone Tracking

## Stage 0: Setup, Environment, Architecture & Dry-Run Pipeline Verification
- **Status**: Completed
- **Date**: 2026-09-28
- **Lead**: Senior Research Engineer

### What Was Done
1. **Environment Setup & Dependency Verification**:
   - Environment: Python 3.10.11 (64-bit AMD64).
   - Core libraries pinned in [requirements.txt](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/requirements.txt):
     - `qiskit==2.5.2`
     - `qiskit-ibm-runtime==0.50.0`
     - `qiskit-aer==0.17.2`
     - `pylatexenc==2.11`
     - `scikit-learn==1.7.2`
     - `scipy==1.15.3`
     - `numpy==2.2.6`
     - `matplotlib==3.10.8`
     - `pandas==2.3.3`
     - `pyyaml==6.0.3`
     - `pytest==9.1.1`
   - Verified that IBM Quantum API tokens are strictly guarded via environment variables (`QISKIT_IBM_TOKEN`) and local account storage; added `.env`, `*.token`, and credentials to [.gitignore](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/.gitignore).
   - Saved environment metadata and random seeds to [results/env.json](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/results/env.json).

2. **Core Library Architecture (`src/qfp/`)**:
   - [`src/qfp/provenance.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/provenance.py): Provenance enforcement (`ibm_hardware`, `aer_ideal`, `aer_noise_model`, `synthetic_dryrun`), refusal of synthetic data in production figures, and SHA256 cryptographic manifest generation.
   - [`src/qfp/budget.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/budget.py): `QPUBudgetGuard` tracking monthly QPU allowance (600s), enforcing 85% safety cap (510.0s), and reading execution metrics via `job.usage()`.
   - [`src/qfp/circuits.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/circuits.py): Standardized 10 benchmark 3-qubit circuits (Bell, GHZ, random Cliffords, mirror with midpoint barrier guard, mirror with delay), transpiler passes with ALAP scheduling, and exact noiseless ideal probability vectors.
   - [`src/qfp/collect.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/collect.py): Resumable, idempotent data collection engine recording raw bitstrings, 8 chronological chunks per circuit, and backend calibration snapshots.
   - [`src/qfp/simulate.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/simulate.py): S0 (ideal statevector), S1 (calibration-derived AerSimulator), S2 (adaptive impersonator with empirical readout confusion fitted strictly from training rounds of |000> and |111>).
   - [`src/qfp/features.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/features.py): 196-dimensional statistical feature extraction engine (probabilities, marginals, parities, ZZ correlators, TVD/Hellinger/KL, entropy, calibration readout confusion) + baseline subsets (`histogram_only` 80-dim, `calibration_properties` 11-dim).
   - [`src/qfp/splits.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/splits.py): Chronological round-level splitting (zero overlap between train, val, test), forward-chaining CV, random leakage baseline split, round-level bootstrap resampling.
   - [`src/qfp/models.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/models.py): Supervised classifiers (Logistic Regression, SVM-RBF, Random Forest, HistGradientBoosting, MLP) with standard scaling fitted on training only.
   - [`src/qfp/detect.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/detect.py): Integrity anomaly detectors (Mahalanobis, Centroid-TVD, One-Class SVM, Isolation Forest, Mahalanobis-NN) trained only on genuine target data, threshold calibrated on validation set, continuous trust score mapping.
   - [`src/qfp/metrics.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/metrics.py): ROC-AUC, EER, TPR@1% FPR, TPR@5% FPR, FAR/FRR at pre-fixed threshold, AAR, TVD drift matrix, 95% bootstrap CIs.
   - [`src/qfp/plotting.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/plotting.py): IEEE style plotting engine for Figures 1 to 12 with colorblind-safe palette, 300 DPI PNG, vector PDF, and CSV source exports.

3. **Executable Pipeline Scripts (`scripts/`)**:
   - [`scripts/01_select_backends.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/01_select_backends.py): Discover operational backends & optimize 3-qubit layouts.
   - [`scripts/02_budget_probe.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/02_budget_probe.py): QPU usage probe & total projection vs 85% cap.
   - [`scripts/03_collect_round.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/03_collect_round.py): Per-round data collection.
   - [`scripts/04_simulate.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/04_simulate.py): Matching S0, S1, S2 generation.
   - [`scripts/05_build_features.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/05_build_features.py): Feature matrix construction.
   - [`scripts/06_run_experiments.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/06_run_experiments.py): E1 to E7 experiment execution & `results.json` compilation.
   - [`scripts/07_make_figures.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/07_make_figures.py): Publication figures & `CAPTIONS.md`.
   - [`scripts/08_make_tables.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/08_make_tables.py): Tables T1 to T5 (CSV + LaTeX).
   - [`scripts/09_claims_audit.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/scripts/09_claims_audit.py): Automated claims audit & `claims_audit.md`.

4. **Testing & Quality Assurance**:
   - 15 unit tests in `tests/` passed (`test_circuits.py`, `test_features.py`, `test_provenance.py`, `test_splits.py`).
   - Round overlap test strictly confirms zero temporal leakage across train, val, and test splits.
   - Provenance guard confirms refusal of synthetic data in production mode.

5. **Dry-Run End-to-End Pipeline Execution**:
   - Executed full pipeline end-to-end via `python run_all.py --dry-run`.
   - Generated 752 sample chunks across 3 fake backends (`fake_sherbrooke`, `fake_brisbane`, `fake_kyiv`) and 3 simulator classes (S0, S1, S2) across 8 rounds.
   - Extracted 196-dimensional statistical feature representation.
   - Executed Experiments E1 through E7.
   - Produced all 12 publication figures (PNG 300 DPI + vector PDF + source CSVs + `CAPTIONS.md`), stamped with `SYNTHETIC - NOT FOR PUBLICATION`.
   - Produced all 5 publication tables (CSV + LaTeX).
   - Generated master `results.json` and audited `claims_audit.md`.

### Key Metrics Obtained in Dry-Run Verification
- **Total Samples**: 752 (192 hardware-like samples, 560 simulator samples across S0, S1, S2)
- **Dimensionality**: 196 statistical output features, 80 histogram-only, 11 calibration-properties
- **E1 Chronological Identification Accuracy**: 0.979 $\pm$ 0.021 (Random Forest, 95% bootstrap CI: [0.958, 1.000])
- **Budget Projection**: 240 circuit runs projected to consume ~271.7 - 283.7 QPU seconds (~45.3% - 47.3% of the 600s Open Plan allowance), strictly within the 85% safety cap (510.0s).

---

## Stage 1 Checkpoint: Discovery & QPU Budget Approval
- **Status**: Completed & Approved by Author
- **Date**: 2026-10-04
- **Lead**: Senior Research Engineer

### Multi-Backend Probe Verification Results
Per the author's conditional approval, budget probes (full 10-circuit rounds at 2048 shots) were executed across all three Heron r2 operational backends:
1. **`ibm_kingston`**: Job ID `db07h15j371s73do0fdg`, Measured usage = **8.000s** (Queue: 2.16s, Wall: 16.38s)
2. **`ibm_marrakesh`**: Job ID `db17pfrid5ic73eqp3t0`, Measured usage = **8.000s** (Queue: 3.96s, Wall: 24.46s)
3. **`ibm_fez`**: Job ID `db17psivog1s73fhp4v0`, Measured usage = **8.000s** (Queue: 2.04s, Wall: 14.68s)

**Verification Outcome**: All 3 backends demonstrated identical quantum execution time (0.00% variance vs kingston's 8.0s), solidly passing the $\pm 15\%$ equivalence criterion.

### Schedule B Locked in `configs/study.yaml`
- **Experimental Scope**: 3 backends $\times$ 12 chronological rounds $\times$ 10 circuits = 360 circuit runs (737,280 shots).
- **Projected QPU Consumption**: $36 \times 8.000\text{s} = \mathbf{288.0\text{s}}$ (48.0% of the 600s Open Plan allowance, leaving 222.0s buffer below the 510.0s safety cap).
- **Chronological Split**:
  - **Train Rounds (1–5)**: 5 rounds (41.7% data, 150 circuits)
  - **Validation Rounds (6–7)**: 2 rounds (16.7% data, 60 circuits)
  - **Test Rounds (8–12)**: 5 rounds (41.7% data, 150 circuits — strictly $\ge 4$ test rounds)

---

## Stage 2: Hardware Data Collection & Daily Round Progress
- **Status**: In Progress (Rounds 1 & 2 Complete — Batch 1 of 6)
- **Date**: 2026-10-05
- **Lead**: Senior Research Engineer

### Hardware Execution Log (Batch 1: Rounds 1 & 2)

#### Round 1 (Oct 4 Evening Baseline)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db17vf9b694s73dru660` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | Completed | [`data/raw/ibm_fez/round_001.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_001.json) |
| **`ibm_kingston`** | `db17vjrid5ic73eqpc30` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | Completed | [`data/raw/ibm_kingston/round_001.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_001.json) |
| **`ibm_marrakesh`** | `db17vrhb694s73dru6qg` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | Completed | [`data/raw/ibm_marrakesh/round_001.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_001.json) |

#### Round 2 (Oct 5 Daytime Slot — Diurnal Separation $\approx 13.3\,\text{h}$)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Wall-Clock Gap from R1 | Calibration Date | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db1jjfhb694s73dscdk0` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **13.22 h** | 2026-10-05 10:38:50 | Completed | [`data/raw/ibm_fez/round_002.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_002.json) |
| **`ibm_kingston`** | `db1jp32vog1s73fi7s60` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **13.41 h** | 2026-10-05 10:42:35 | Completed | [`data/raw/ibm_kingston/round_002.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_002.json) |
| **`ibm_marrakesh`** | `db1jq71b694s73dscqbg` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **13.44 h** | 2026-10-05 10:48:47 | Completed | [`data/raw/ibm_marrakesh/round_002.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_002.json) |

#### Round 3 (Oct 5 Maximum Compression Cadence — Hard Floor Cleared $\ge 4.0\,\text{h}$)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Wall-Clock Gap from R2 | Calibration Date | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db1nb5uegvvc73bht3jg` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **4.05 h** | 2026-10-05 15:40:02 | Completed | [`data/raw/ibm_fez/round_003.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_003.json) |
| **`ibm_kingston`** | `db1ni83id5ic73erde8g` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **4.27 h** | 2026-10-05 15:42:10 | Completed | [`data/raw/ibm_kingston/round_003.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_003.json) |
| **`ibm_marrakesh`** | `db1nieivog1s73fidc70` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **4.27 h** | 2026-10-05 15:45:15 | Completed | [`data/raw/ibm_marrakesh/round_003.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_003.json) |

### Cumulative QPU Budget Status
- **Initial Probes Consumption (3 backends)**: **24.000 s**
- **Round 1 Consumption (3 backends)**: **24.000 s**
- **Round 2 Consumption (3 backends)**: **24.000 s**
- **Round 3 Consumption (3 backends)**: **24.000 s**
- **Cumulative QPU Consumed So Far**: **96.000 s** across 12 total jobs
- **85% Safety Cap (Ceiling)**: **510.0 s**
- **Safety Cap Utilization**: **18.8 %** (well below the 50% visibility threshold)
- **Total Monthly Allowance Remaining**: **504.000 s** (84.0% intact out of 600.0s)
- **Remaining Safe QPU Budget**: **414.000 s**

### Execution Mode: Autonomous Maximum Compression Cadence
- **Protocol**: Autonomous execution through Round 12 $\to$ Stage 3 (Simulations S0/S1/S2) $\to$ Stage 4 (Features, Experiments E1-E7, Claims Audit).
- **Hard-Floor Guard**: Strictly $\ge 4.0\,\text{hours}$ per backend maintained between rounds.
- **Halt Trigger Behavior**: If ANY halt condition fires (job failure, usage deviation >15%, budget cap >60%), the top line of `STATUS.md` is immediately overwritten with `HALTED AT ROUND X — AWAITING REVIEW — REASON: ...` and execution halts.
- **Current Status**: Round 4 locked until 4.0h floor clears at $\approx 19:47$ local time (~14:17 UTC).



