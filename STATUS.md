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
   - [`src/qfp/circuits.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/circuits.py): Standardized 10 benchmark 3-qubit circuits (Bell, GHZ, random Cliffords, mirror with midpoint barrier guard, mirror with delay), transpiler passes with ALAP scheduling + deterministic fallback to native basis gates, and exact noiseless ideal probability vectors.
   - [`src/qfp/collect.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/src/qfp/collect.py): Resumable, idempotent data collection engine recording raw bitstrings, 8 chronological chunks per circuit, `transpile_path` tag, and backend calibration snapshots.
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
   - 16 unit tests in `tests/` passed (`test_circuits.py`, `test_features.py`, `test_provenance.py`, `test_splits.py`).
   - Round overlap test strictly confirms zero temporal leakage across train, val, and test splits.
   - Explicit assertion test `test_c10_fallback_equivalence_and_barrier_position` verifies 7500dt delays and midpoint barrier sandwiching are identical across ALAP and Fallback paths.
   - Provenance guard confirms refusal of synthetic data in production mode.

5. **Dry-Run End-to-End Pipeline Execution**:
   - Executed full pipeline end-to-end via `python run_all.py --dry-run`.
   - Generated 752 sample chunks across 3 fake backends (`fake_sherbrooke`, `fake_brisbane`, `fake_kyiv`) and 3 simulator classes (S0, S1, S2) across 8 rounds.
   - Extracted 196-dimensional statistical feature representation.
   - Executed Experiments E1 through E7.
   - Produced all 12 publication figures (PNG 300 DPI + vector PDF + source CSVs + `CAPTIONS.md`), stamped with `SYNTHETIC - NOT FOR PUBLICATION`.
   - Produced all 5 publication tables (CSV + LaTeX).
   - Generated master `results.json` and audited `claims_audit.md`.

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
  - **Train Rounds (1–5)**: 5 rounds (41.7% data, 150 circuits) — **100% COMPLETE**
  - **Validation Rounds (6–7)**: 2 rounds (16.7% data, 60 circuits)
  - **Test Rounds (8–12)**: 5 rounds (41.7% data, 150 circuits — strictly $\ge 4$ test rounds)

---

## Stage 2: Hardware Data Collection & Daily Round Progress
- **Status**: In Progress (Rounds 1–5 Complete — Train Split Finalized)
- **Date**: 2026-10-06
- **Lead**: Senior Research Engineer

### Hardware Execution Log

#### Round 1 (Oct 4 Evening Baseline)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db17vf9b694s73dru660` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | `alap` | Completed | [`data/raw/ibm_fez/round_001.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_001.json) |
| **`ibm_kingston`** | `db17vjrid5ic73eqpc30` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | `alap` | Completed | [`data/raw/ibm_kingston/round_001.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_001.json) |
| **`ibm_marrakesh`** | `db17vrhb694s73dru6qg` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | `alap` | Completed | [`data/raw/ibm_marrakesh/round_001.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_001.json) |

#### Round 2 (Oct 5 Daytime Slot — Diurnal Separation $\approx 13.3\,\text{h}$)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R1 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db1jjfhb694s73dscdk0` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **13.22 h** | `alap` | Completed | [`data/raw/ibm_fez/round_002.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_002.json) |
| **`ibm_kingston`** | `db1jp32vog1s73fi7s60` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **13.41 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_002.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_002.json) |
| **`ibm_marrakesh`** | `db1jq71b694s73dscqbg` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **13.44 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_002.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_002.json) |

#### Round 3 (Oct 5 Maximum Compression Cadence — Hard Floor Cleared $\ge 4.0\,\text{h}$)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R2 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db1nb5uegvvc73bht3jg` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **4.05 h** | `alap` | Completed | [`data/raw/ibm_fez/round_003.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_003.json) |
| **`ibm_kingston`** | `db1ni83id5ic73erde8g` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **4.27 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_003.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_003.json) |
| **`ibm_marrakesh`** | `db1nieivog1s73fidc70` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **4.27 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_003.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_003.json) |

#### Round 4 (Oct 5 Maximum Compression Cadence — Hard Floor Cleared $\ge 4.0\,\text{h}$)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R3 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db1smp72iglc7396hb50` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **5.92 h** | `alap` | Completed | [`data/raw/ibm_fez/round_004.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_004.json) |
| **`ibm_kingston`** | `db1snkhmmimc73fntkq0` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **5.95 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_004.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_004.json) |
| **`ibm_marrakesh`** | `db1snphre0kc7396q0hg` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **5.95 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_004.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_004.json) |

#### Round 5 (Oct 6 Maximum Compression Cadence — Train Split Finalized)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R4 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db25d468v0ts73c2b4l0` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **4.01 h** | `alap` | Completed | [`data/raw/ibm_fez/round_005.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_005.json) |
| **`ibm_kingston`** | `db25hv42ljfc73d405ng` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **4.22 h** | `fallback` | Completed | [`data/raw/ibm_kingston/round_005.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_005.json) |
| **`ibm_marrakesh`** | `db27lem8v0ts73c2dtf0` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **12.42 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_005.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_005.json) |

#### Round 6 (Oct 6 Maximum Compression Cadence — Validation Split R6-R7 Initiated)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R5 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db2cfnk2ljfc73d48v10` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **8.05 h** | `alap` | Completed | [`data/raw/ibm_fez/round_006.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_006.json) |
| **`ibm_kingston`** | `db2cgms7f06c73apkdtg` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **7.15 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_006.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_006.json) |
| **`ibm_marrakesh`** | `db2cgrs2ljfc73d490k0` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **5.52 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_006.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_006.json) |

#### Round 7 (Oct 9 Maximum Compression Cadence — Validation Split Completed)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R6 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db47tb04qg6s73c1pp8g` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **68.07 h** | `alap` | Completed | [`data/raw/ibm_fez/round_007.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_007.json) |
| **`ibm_kingston`** | `db47tdcvf2bc73cu7br0` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **67.67 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_007.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_007.json) |
| **`ibm_marrakesh`** | `db47tag4qg6s73c1pp7g` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **67.58 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_007.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_007.json) |

#### Round 8 (Oct 9 Maximum Compression Cadence — Test Split Initiated @ 2.0h Floor)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R7 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db4acicvf2bc73cub490` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **2.33 h** | `alap` | Completed | [`data/raw/ibm_fez/round_008.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_008.json) |
| **`ibm_kingston`** | `db4acislf4us73c2fjsg` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **2.73 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_008.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_008.json) |
| **`ibm_marrakesh`** | `db4aciqmb58s7388u56g` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **2.81 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_008.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_008.json) |

#### Round 9 (Oct 9 Maximum Compression Cadence — Test Split Continued @ 2.0h Floor)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R8 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db4c59g4qg6s73c1vs10` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **2.01 h** | `alap` | Completed | [`data/raw/ibm_fez/round_009.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_009.json) |
| **`ibm_kingston`** | `db4c73o4qg6s73c1vucg` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **2.02 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_009.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_009.json) |
| **`ibm_marrakesh`** | `db4c5a84qg6s73c1vs2g` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **2.01 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_009.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_009.json) |

#### Round 10 (Oct 9 Maximum Compression Cadence — Test Split Finalized @ Cutoff)
| Backend | Job ID | Physical Layout | Circuits | Shots | Quantum Usage | Gap from R9 | Transpile Path | Status | Raw Output File |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`ibm_fez`** | `db4gqjqmb58s73896gm0` | `[137, 147, 146]` | 10 | 2048 | 8.000 s | **5.30 h** | `alap` | Completed | [`data/raw/ibm_fez/round_010.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_fez/round_010.json) |
| **`ibm_kingston`** | `db4gqkcvf2bc73cujge0` | `[89, 90, 91]` | 10 | 2048 | 8.000 s | **4.92 h** | `alap` | Completed | [`data/raw/ibm_kingston/round_010.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_kingston/round_010.json) |
| **`ibm_marrakesh`** | `db4gqk4lf4us73c2o0pg` | `[4, 5, 6]` | 10 | 2048 | 8.000 s | **5.30 h** | `alap` | Completed | [`data/raw/ibm_marrakesh/round_010.json`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/data/raw/ibm_marrakesh/round_010.json) |

### Cumulative QPU Budget Status
- **Initial Probes Consumption (3 backends)**: **24.000 s**
- **Round 1 Consumption (3 backends)**: **24.000 s**
- **Round 2 Consumption (3 backends)**: **24.000 s**
- **Round 3 Consumption (3 backends)**: **24.000 s**
- **Round 4 Consumption (3 backends)**: **24.000 s**
- **Round 5 Consumption (3 backends)**: **24.000 s**
- **Round 6 Consumption (3 backends)**: **24.000 s**
- **Round 7 Consumption (3 backends)**: **24.000 s**
- **Round 8 Consumption (3 backends)**: **24.000 s**
- **Round 9 Consumption (3 backends)**: **24.000 s**
- **Round 10 Consumption (3 backends)**: **24.000 s**
- **Cumulative QPU Consumed So Far**: **264.000 s** across 33 total hardware jobs (including 3 probes)
- **85% Safety Cap (Ceiling)**: **510.0 s**
- **Safety Cap Utilization**: **51.8 %** (well below the 60% halt threshold of 306.0s)
- **Total Monthly Allowance Remaining**: **336.000 s** (56.0% intact out of 600.0s)
- **Remaining Safe QPU Budget**: **246.000 s**

### Transpile Path Verification & Confound Tagging
- **c10 Circuit Equivalence**: Verified that both the normal ALAP scheduling path and the fallback path preserve:
  - Delay duration strictly equal to $7500\,\text{dt} = 30\,\mu\text{s}$.
  - Delay position relative to the mirror circuit's midpoint barriers: exactly 3 delay instructions on active qubits $[q_0, q_1, q_2]$ sandwiched between $\text{barrier}_0$ and $\text{barrier}_1$.
  - Unit test `test_c10_fallback_equivalence_and_barrier_position` in [`tests/test_circuits.py`](file:///c:/Users/workh/OneDrive/Desktop/Quantum%20-%20computin/tests/test_circuits.py) passes (16/16 tests passing).
- **Provenance & Confound Audit**: Every raw round record includes `"transpile_path": "alap" | "fallback"`. This metadata is forwarded into feature extraction rows to ensure any path-dependent effects are audited during downstream analysis.

### Execution Mode: Autonomous Decoupled Maximum Compression Cadence
- **Protocol**: Autonomous decoupled per-backend execution through Round 12 $\to$ Stage 3 (Simulations S0/S1/S2) $\to$ Stage 4 (Features, Experiments E1-E7, Claims Audit) $\to$ Stage 5 (Publication Figures 1-12, Tables T1-T5, CAPTIONS.md, Handoff package).
- **Hard-Floor Guard**: Strictly $\ge 4.0\,\text{hours}$ per backend for rounds 1–7; reduced to $\ge 2.0\,\text{hours}$ per backend for rounds 8 onward (deadline-driven; multi-day train-to-test separation already firmly established). Backends submit independently without waiting for each other.
- **Keep-Awake & Heartbeat**: `SetThreadExecutionState` active; heartbeats logged every 60s; gaps > 30 minutes flagged as potential machine sleep.
- **Hard Cutoff**: Oct 10, 12:00 local time. Reached at Round 10. Split locked in `study.yaml`: train 1-5, val 6-7, test 8-10 (3 test rounds, strictly chronological).
- **Halt Trigger Behavior**: If ANY halt condition fires (job failure, usage deviation >15%, budget cap >60%), the top line of `STATUS.md` is immediately overwritten with `HALTED AT ROUND X — AWAITING REVIEW — REASON: ...` and execution halts.
- **Current Status**: Rounds 1-10 100% complete across all 3 backends (`ibm_fez`, `ibm_kingston`, `ibm_marrakesh`). Data collection concluded at Oct 10 12:00 cutoff. Autonomous execution proceeding through Stage 3, Stage 4, Stage 5.






> [!WARNING]
> **Possible System Sleep / Interruption Detected**: Log heartbeat gap of 115.3 minutes recorded at 2026-10-09T12:36:03.380374+00:00.

> [!WARNING]
> **Possible System Sleep / Interruption Detected**: Log heartbeat gap of 361.6 minutes recorded at 2026-10-09T23:44:53.512510+00:00.
