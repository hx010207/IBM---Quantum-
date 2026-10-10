# Methods Notes & Experimental Protocol Log

This document records the exact, immutable technical details, parameters, library versions, and rationale for the implementation phase of the research project:
**"Chronological Fingerprinting and Spoofing Detection of IBM Quantum Backends from Black-Box Measurement Statistics"**

---

## 1. Research Question & Objective
Can black-box measurement statistics from fixed quantum circuits identify an IBM Quantum backend across days under a strict chronological split, and can a calibration-derived or adaptive noise-model simulator impersonate a real backend without detection?

---

## 2. Experimental Environment & Dependency Versions
- **Operating System**: Windows (AMD64)
- **Python Version**: 3.10.11 (64-bit)
- **Qiskit Core**: `qiskit==2.5.2`
- **Qiskit IBM Runtime**: `qiskit-ibm-runtime==0.50.0`
- **Qiskit Aer Simulator**: `qiskit-aer==0.17.2`
- **Scipy**: `1.15.3`
- **NumPy**: `2.2.6`
- **Scikit-Learn**: `1.7.2`
- **XGBoost**: `3.2.0`
- **Matplotlib**: `3.10.8`
- **PyYAML**: `6.0.3`
- **Pytest**: `9.1.1`
- **Pylatexenc**: `2.11`
- **Master Random Seed**: `42`
- **Stochastic Replicate Seeds**: `[42, 43, 44, 45, 46]`

---

## 3. Physical Layout & Backend Topology
- **Selection Criteria**: On Day 1 (`scripts/01_select_backends.py`), operational backends are queried from the author's instance. For each backend, a connected 3-qubit linear chain $q_0 - q_1 - q_2$ with the lowest aggregate two-qubit gate error is selected from backend calibration data.
- **Physical Layout Constraint**: The chosen physical layout is permanently fixed across all rounds and never altered.
- **Transpiler Invariance**: Logical circuits are transpiled with fixed `initial_layout`, `optimization_level=1`, `scheduling_method='alap'`, and `seed_transpiler=42`.

---

## 4. Benchmark Circuit Suite Rationale (10 Circuits)
1. **`c01_prep_000` (State Prep |000>)**:
   - *Target sensitivity*: Ground state readout fidelity, asymmetric bit-flip noise $0 \to 1$.
2. **`c02_prep_111` (State Prep |111>)**:
   - *Target sensitivity*: Excited state decay during readout, bit-flip noise $1 \to 0$.
3. **`c03_bell_01` (Bell State on edge 0-1)**:
   - *Target sensitivity*: Two-qubit entangling gate error on physical pair (0, 1), spectator dephasing on $q_2$.
4. **`c04_bell_12` (Bell State on edge 1-2)**:
   - *Target sensitivity*: Two-qubit entangling gate error on physical pair (1, 2), spectator dephasing on $q_0$.
5. **`c05_ghz_012` (GHZ State $0 \to 1 \to 2$)**:
   - *Target sensitivity*: Coherent multipartite entanglement, forward entangling direction sensitivity.
6. **`c06_ghz_210` (GHZ State $2 \to 1 \to 0$)**:
   - *Target sensitivity*: Reverse entangling direction asymmetry (validating bidirectional gate calibration differences).
7. **`c07_clifford_depth8` (Seeded Random Clifford, depth ~8)**:
   - *Target sensitivity*: Randomized gate Pauli channel accumulation at shallow depth.
8. **`c08_clifford_depth24` (Seeded Random Clifford, depth ~24)**:
   - *Target sensitivity*: Deep circuit coherent error accumulation and unitary over-rotation compounding.
9. **`c09_mirror_depth12` (Seeded Mirror Circuit, depth ~12)**:
   - *Design details*: Random forward unitary $U$, reflection `barrier`, and inverse $U^\dagger$.
   - *Compiler Guard*: Barrier at the midpoint strictly prevents transpiler passes from canceling $U^\dagger U$ into an empty identity wire.
   - *Target sensitivity*: Coherent error reversibility and state return probability.
10. **`c10_mirror_depth24_delay` (Mirror Circuit with Delay, depth ~24 + delay)**:
    - *Design details*: Random forward unitary $U$, barrier, calibrated idle delay ($30.0\,\mu\text{s} = 7500\,\text{dt}$ for $dt = 4.0\,\text{ns}$), barrier, inverse $U^\dagger$.
    - *Target sensitivity*: Pure environmental $T_1$ relaxation and $T_2$ dephasing during circuit execution ($\sim 0.2 \times T_2$ on Heron r2 processors).

---

## 5. Sampling, Sample Definition & Chronological Splitting (Schedule B)
- **Shots**: 2048 shots per circuit per round.
- **Sample Chunking**: The chronological sequence of 2048 measurement bitstrings per circuit is partitioned into 8 contiguous chunks of 256 shots each.
- **Sample Unit**: A sample vector consists of the statistical features extracted from one chunk across all 10 circuits.
- **Split Scheme (Schedule B - 12 Rounds across 3 Backends = 360 circuits)**:
  - The fundamental unit of splitting is the whole `round_id`. Chunks from the same round NEVER cross split boundaries.
  - Training Set: Rounds 1, 2, 3, 4, 5 (41.7% of data, 150 circuits).
  - Validation Set: Rounds 6, 7 (16.7% of data, 60 circuits, used for tuning and threshold calibration).
  - Final Test Set: Rounds 8, 9, 10, 11, 12 (41.7% of data, 150 circuits, strictly $\ge 4$ test rounds evaluated out-of-sample).
- **Leakage Baseline**: A random chunk-level split is evaluated strictly as an explicit labeled comparison to demonstrate the inflation caused by ignoring round-level correlation.

---

## 6. Adversary Classes & Simulator Models
1. **$S_0$ (Ideal Simulation)**:
   - Pure noiseless statevector sampling on the logical benchmark circuits.
2. **$S_1$ (Calibration-Derived Impersonator)**:
   - Instantiated via `AerSimulator.from_backend(target_backend)` using calibration data refreshed for the operational period.
   - Run on identical transpiled circuits, physical layout, shots, and circuit ordering.
3. **$S_2$ (Adaptive Impersonator)**:
   - $S_1$ augmented with an empirical per-qubit readout-confusion matrix $M_q$:
     $$M_q = \begin{pmatrix} 1 - P(1|0) & P(0|1) \\ P(1|0) & 1 - P(0|1) \end{pmatrix}$$
   - Calibrated *exclusively* from training-period $|000\rangle$ and $|111\rangle$ calibration circuits.
   - Evaluated strictly on untouched circuits and subsequent rounds.
- **Attacker Capabilities & Limitations**:
  - Attacker possesses full calibration snapshots and layout knowledge.
  - Attacker lacks pulse-level control, assumes stationary Markovian noise, and cannot simulate non-Markovian memory, spectator crosstalk, or two-level system (TLS) defect dynamics.

---

## 7. Statistical Feature Extraction (196 Dimensions)
Concatenated across the 10 benchmark circuits:
1. Outcome probabilities: $8 \times 10 = 80$ dims
2. Per-qubit marginals $P(q_k = 1)$: $3 \times 10 = 30$ dims
3. Parity statistics $P(\text{odd})$: $1 \times 10 = 10$ dims
4. Pairwise $ZZ$ correlators $\langle Z_i Z_j \rangle$: $3 \times 10 = 30$ dims
5. Distances to ideal: TVD, Hellinger, KL divergence: $3 \times 10 = 30$ dims
6. Shannon Entropy: $1 \times 10 = 10$ dims
7. Readout confusion estimates from calibration circuits: 6 dims
- **Total Feature Dimensionality**: 196 features.

---

## 8. QPU Budget Guard & Safety Enforcement
- IBM Open Plan allowance: 10 minutes (600 seconds) of QPU execution time per rolling 28-day window.
- **Safety Cap**: Strictly capped at 85% ($510.0$ seconds).
- **Enforcement Mechanism**: `QPUBudgetGuard` measures actual quantum seconds per completed job via `job.usage()`, persists cumulative state in `data/interim/budget_state.json`, and halts execution before submission if a projected job exceeds the 85% limit.

---

## 9. Hardware Execution Timing & Billing Quantization Analysis
Direct empirical inspection of raw IBM Quantum Runtime job metrics across `ibm_kingston`, `ibm_marrakesh`, and `ibm_fez` establishes the following ground truth regarding continuous vs. quantized billing:

1. **Physical Circuit Execution Time (Continuous Measurement)**:
   - Available via `job.metrics()['circuits_execution_time_ns']`.
   - Measured down to nanosecond precision on Heron r2 processors:
     - `ibm_fez`: $5,367,484,928\,\text{ns} = \mathbf{5.3675\,\text{s}}$
     - `ibm_kingston`: $5,421,131,520\,\text{ns} = \mathbf{5.4211\,\text{s}}$
     - `ibm_marrakesh`: $5,590,533,888\,\text{ns} = \mathbf{5.5905\,\text{s}}$
   - True physical circuit execution accounts for $\sim 5.4 - 5.6\,\text{s}$ per 10-circuit round at 2048 shots.

2. **IBM Cloud Billing Quantization (`job.usage()` & `service.usage()`)**:
   - `job.usage()` returns an integer value (`<class 'int'>`) equal to `qpu_charge_time_seconds = 8` integer seconds (corresponding to 0.119 Resource Units).
   - In the IBM Cloud Quantum Platform billing service, `service.usage()['usage_consumed_seconds']` debits strictly in **whole integer seconds** (e.g. 8s per job).
   - IBM's charging policy rounds up or quantizes job charge times to integer seconds.

3. **Implications for Budget Projections**:
   - Because billing is quantized to exactly **8 integer seconds** per 10-circuit round (2048 shots), budget projections are deterministic rather than stochastic:
     - 1 round across 3 backends = $3 \times 8\,\text{s} = \mathbf{24\,\text{s}}$.
     - Full 12-round study = $36 \times 8\,\text{s} = \mathbf{288\,\text{s}}$.
   - This guarantees that no sub-second jitter can cause unexpected budget exhaustion. The 12-round study will consume exactly $288.0\,\text{s}$ ($48.0\%$ of the 600s allowance), preserving a $222.0\,\text{s}$ buffer below the 510.0s safety cap.

---

## 10. Maximum Compression Collection Cadence & Deadline-Driven Operational Window
- **Protocol Transition**: To satisfy the submission deadline for MARC 2027 (Oct 15, 2026), the data collection cadence was shifted effective Oct 5 from a diurnal-alternating schedule (~10–12 hours between rounds, spanning ~5 days) to a maximum-compression cadence.
- **Hard-Floor Preservation**: Rounds 3 through 12 are executed back-to-back immediately as the hard 4.0-hour safety floor clears per backend (`min_gap_hours = 4.0`). The 4.0-hour floor is non-negotiable to maintain valid chronological separation and capture non-trivial drift across distinct backend states and asynchronous recalibrations.
- **Resulting Temporal Window**: Total observation window is compressed to approximately $\sim 2.0 - 2.5$ days rather than the originally envisioned 5 days.
- **Reporting Requirement**: In accordance with scientific integrity guidelines, this compressed observation window is explicitly recognized and documented as a deadline-driven limitation in `LIMITATIONS_OBSERVED.md` and will be clearly reported in the paper's Limitations section.

---

## 11. Transpilation Path Invariance & Fallback Confound Control
- **Occurrence**: During Round 5 collection on `ibm_kingston` (Job `db25hv42ljfc73d405ng`), Qiskit's `ALAPScheduleAnalysis` raised a transient `TranspilerError` due to missing `cz` gate duration data during backend maintenance. Transpilation succeeded deterministically using the native basis gates + coupling map fallback path (`transpile_path: fallback`). All other 14 training rounds across `ibm_fez`, `ibm_marrakesh`, and `ibm_kingston` used standard ALAP scheduling (`transpile_path: alap`).
- **Circuit Equivalence**: Unit test `test_c10_fallback_equivalence_and_barrier_position` confirms that `c10_mirror_depth24_delay` under the fallback path preserves identical dephasing delay duration ($7500\,\text{dt} = 30\,\mu\text{s}$) and identical relative placement sandwiched strictly between the midpoint entry and exit barriers (`barrier_0 < delay < barrier_1`).
- **Confound Audit**: In Stage 4 (`scripts/06_run_experiments.py` & `scripts/09_claims_audit.py`), an explicit sanity check verifies that the single fallback collection round (`ibm_kingston` Round 5) does not behave as an outlier relative to ALAP rounds from the same backend. Empirical inspection confirms distance from the Kingston ALAP centroid is within 0.68 standard deviations (mean Euclidean distance 0.978 vs 0.789 $\pm$ 0.279), with 100% classification accuracy into `ibm_kingston` when evaluated out-of-round, demonstrating no detectable confounding effect.

---

## 12. Cadence Compression for Rounds 8 Onward (2.0-Hour Floor) & Correlation Accounting
- **Protocol Adjustment**: For rounds 8 onward only, the per-backend minimum separation gap was reduced from 4.0h to 2.0h (`min_gap_hours = 2.0`). Rounds 1–7 remain completely unchanged (spanning Oct 4 through Oct 9, with multi-day train-to-test separation firmly established: e.g. R1–R5 collected Oct 4–6, R6 collected Oct 6, R7 collected Oct 9, establishing $>67$ hours of real-world physical drift separation between training and test sets).
- **Reason for Change**: Hard submission deadline constraint (MARC 2027) requiring all data collection to conclude by Oct 10 12:00 local time to allow complete experimental synthesis and paper finalization. Because train-to-test separation is already several days, reducing the floor for test rounds does not compromise the core chronological separation claim.
- **Statistical Consequence**: Because test rounds 8–12 are spaced approximately 2–3 hours apart, consecutive test rounds exhibit higher temporal correlation than earlier rounds.
- **Methodological Controls**:
  - In E3 (cross-day persistence), E5 (open-set), and all longitudinal evaluations, analyses compute and report the **exact elapsed wall-clock hours** derived directly from raw execution timestamps rather than assuming uniform round spacing.
  - Confidence intervals are computed via round-level bootstrap resampling, accompanied by explicit notes and documentation that test rounds are not fully independent due to the compressed 2.0h cadence.

---

## 13. Data Collection Cutoff and Split Locking (Oct 10 12:00 Local Cutoff)
- **Cutoff Enforcement**: At the hard deadline cutoff of Oct 10 12:00 local time (06:30 UTC), hardware collection concluded at Round 10, the highest common round completed across all three operational backends (`ibm_fez`, `ibm_kingston`, `ibm_marrakesh`).
- **Split Definition Locked in study.yaml**:
  - **Training Split**: Rounds 1, 2, 3, 4, 5 (5 rounds; 40 sample chunks per circuit per backend; establishing multi-day historical baseline).
  - **Validation Split**: Rounds 6, 7 (2 rounds; 16 sample chunks per circuit per backend; threshold calibration and hyperparameter validation).
  - **Test Split**: Rounds 8, 9, 10 (3 rounds; 24 sample chunks per circuit per backend; out-of-sample chronological evaluation).
- **Methodological Integrity**: Zero temporal overlap between splits ($t_{\text{train}} < t_{\text{val}} < t_{\text{test}}$). Test set retains 3 discrete rounds separated by $\ge 2.0\,\text{h}$ per backend. Total hardware jobs = 30 collection rounds + 3 initial probes = 33 jobs, consuming 264.000 QPU seconds ($51.8\%$ of the 510.0s safety cap).
- **Reason**: Hard deadline constraint (MARC 2027) requiring data collection to end by Oct 10 12:00 local time to allow complete experimental synthesis (Stage 3 simulations, Stage 4 experiments E1–E7, Stage 5 figures and tables).

---

## 14. Pre-Manuscript Implementation & Artifact Audit Outcomes
A comprehensive implementation audit was conducted on October 10, 2026, confirming the following empirical and methodological parameters:

1. **Artifact & Feature Provenance Verification (E2, E4, E5)**:
   - Zero metadata leakage: Feature vectors (196-dim `full` and 80-dim `histogram_only`) contain no timestamps, transpile paths, round identifiers, backend labels, or calibration table properties.
   - Physical drivers: Top features separating hardware from simulators are physical decoherence and dephasing from the $30\,\mu\text{s}$ ($7500\,\text{dt}$) delay in circuit $c_{10}$ (`c10_mirror_depth24_delay__marginal_q2`: 0.1001, `dist_hellinger`: 0.0909, `marginal_q1`: 0.0893, `dist_tvd`: 0.0839, `zz_1_2`: 0.0771).
   - Re-running E2 on `histogram_only` (80 raw bitstring outcome probabilities across the 10 circuits):
     - Logistic Regression: Test Acc = 1.0000, ROC-AUC = 1.0000
     - Random Forest: Test Acc = 1.0000, ROC-AUC = 1.0000
     - SVM-RBF: Test Acc = 0.9271, ROC-AUC = 0.9990
   - Label-shuffle control: Permuting training/test labels drops E2 Random Forest ROC-AUC to 0.4125 (vs 1.0000) and E4 Mahalanobis ROC-AUC to 0.3976–0.6250, demonstrating genuine physical separation rather than statistical artifacts.

2. **Genuine-Sample Dynamics & E5 vs E1 Reconciliation**:
   - Validation-calibrated thresholds ($\text{FPR} = 0.05$ on R6–7) and test False Rejection Rates (FRR):
     - `ibm_fez` (threshold 16.4954): Val FRR = 0.0625; Test FRR = 0.4167 (mean score drifted: train 7.34 $\to$ R6 13.91 $\to$ R7 14.49 $\to$ test 15.87).
     - `ibm_kingston` (threshold 23.5880): Val FRR = 0.0625; Test FRR = 0.2083 (mean score: train 7.24 $\to$ R6 15.47 $\to$ R7 22.22 $\to$ test 20.56).
     - `ibm_marrakesh` (threshold 28.6738): Val FRR = 0.0625; Test FRR = 0.9583 (mean score drifted from train 7.04 $\to$ R6 23.76 $\to$ R7 24.91 $\to$ test 35.03).
   - Reconciliation: E5 achieves 100% open-set rejection of `ibm_marrakesh` on `ibm_fez`'s detector because Marrakesh's test distribution is displaced to an anomaly score of 36.50 ($\gg 16.4954$ threshold). In contrast, closed-set E1 models (44–74% accuracy) must classify drifting test samples across devices whose individual centroids shift over 5 days.

3. **Model Selection & Confidence Interval Characterization**:
   - Primary model designated on validation rounds (R6–7): **Logistic Regression** (Val Acc: 0.6875, Bal Acc: 0.6875, Macro F1: 0.6830).
   - Test performance on all five models (Rounds 8–10, no test selection):
     - Logistic Regression (Designated Primary): Test Acc = **0.6667** | Round-CI: [0.583, 0.708] | Chunk-CI: [0.569, 0.778]
     - SVM-RBF: Test Acc = **0.7361** | Round-CI: [0.625, 0.875] | Chunk-CI: [0.625, 0.833]
     - MLP: Test Acc = **0.5139** | Round-CI: [0.417, 0.667] | Chunk-CI: [0.389, 0.625]
     - Random Forest: Test Acc = **0.4444** | Round-CI: [0.250, 0.792] | Chunk-CI: [0.333, 0.556]
     - Gradient Boosting: Test Acc = **0.4028** | Round-CI: [0.208, 0.583] | Chunk-CI: [0.292, 0.514]
   - Per-round test breakdown:
     - Round 8: LogReg 0.7083, SVM 0.7083, RF 0.2500, GB 0.2083, MLP 0.4583
     - Round 9: LogReg 0.5833, SVM 0.6250, RF 0.2917, GB 0.4167, MLP 0.4167
     - Round 10: LogReg 0.7083, SVM 0.8750, RF 0.7917, GB 0.5833, MLP 0.6667
   - Resampling units: E1 resamples clusters of chunks across rounds with replacement; E3 intervals are chunk-level within each single evaluated round.

4. **Record Recovery & Exclusion Audit**:
   - Tagged records:
     - `ibm_kingston` Round 5: `transpile_fallback` (ALAP `cz` gate duration bug; native basis transpilation).
     - `ibm_kingston` Round 9: `post_hoc_api_retrieval` (job `db4c73o4qg6s73c1vucg` executed; local socket timeout recovered via API).
     - `ibm_kingston` Round 10: `post_hoc_api_retrieval` (job `db4gqkcvf2bc73cujge0` executed; local socket timeout recovered via API).
   - In all recovered records, measured bitstring counts from the QPU payload are unaltered.
   - Performance excluding recovered Kingston rounds:
     - E1 Test Accuracy: Logistic Regression 0.6071 (-0.0595), SVM-RBF 0.8214 (+0.0853), Random Forest 0.4107 (-0.0337).
     - E3 Persistence: R3 0.8333, R4 1.0000, R5 0.8750 (-0.0417), R6 0.6667, R7 0.3750, R8 0.5000, R9 0.2500 (+0.0417), R10 0.6250 (+0.0833).

5. **QPU Usage Ledger**:
   - Sum of `service.job(id).usage()` across all 33 IBM Quantum jobs: **240.000 s** (30 rounds $\times$ 8.0s) + **24.000 s** (3 probes $\times$ 8.0s) = **264.000 s**.
   - Exactly matches `data/interim/budget_state.json` (discrepancy = 0.000 s).

6. **Log Evidence for Collection Halting at Round 10**:
   - `pipeline_autonomous.log` records a 361.6-minute (6.03-hour) host sleep beginning at 2026-10-09 23:14 local, which caused a client-side socket name resolution error while polling Kingston Round 10.
   - Orchestrator safety halt triggered at 2026-10-10 05:14:53 local (`exit code 1`).
   - At agent resumption (~10:30 local), only 1.5 hours remained before the 12:00 local cutoff—insufficient to satisfy the mandatory 2.0-hour inter-round floors for rounds 11 and 12 ($>4.0\,\text{h}$ required).




