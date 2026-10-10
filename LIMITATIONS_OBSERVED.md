# Limitations Observed & Factual Constraints Log

This document records the empirical boundaries, hardware limitations, and factual constraints encountered during the experimental execution.

---

## 1. Temporal Observation Window & Maximum Compression Cadence
- **Observation Duration**: Data collection spans 12 discrete rounds across 3 operational backends over a compressed temporal window of approximately $\sim 2.0 - 2.5$ days (rather than the originally envisioned $\sim 5$-day diurnal-alternating schedule).
- **Deadline-Driven Limitation**: Effective Round 3, the experimental cadence was transitioned to a maximum-compression back-to-back schedule strictly at the 4.0-hour hard-floor separation to meet the hard submission deadline for MARC 2027 (October 15, 2026). This compression represents an operational trade-off: while the 4.0-hour floor guarantees independent calibration/drift samples, the total observation baseline is shortened relative to a multi-week longitudinal study. This limitation must be explicitly highlighted in the manuscript's Limitations section.
- **Scientific Caveat**: The findings demonstrate cross-round persistence and temporal consistency over the *observed operational window*. They must not be extrapolated or reported as permanent hardware drift or decadal fingerprints.
- **Calibration Frequency**: IBM Quantum hardware performs frequent automated calibrations and periodic drift tracking; calibration tables are updated asynchronously rather than strictly once per 24-hour cycle.


---

## 2. Fleet Size & Open Plan Resource Boundaries
- **Accessible Devices**: Experiments are conducted strictly within the authorized IBM Open Plan tier (rolling 10-minute / 600-second QPU allocation every 28 days).
- **Backend Count**: Limited to 2-3 accessible operational utility-scale superconducting backends.
- **Open-Set Generalization**: Open-set evaluation is performed by holding out 1 of the 3 available devices. While effective for proof-of-concept verification, evaluation across larger fleets (e.g. 10+ devices) requires multi-institutional enterprise access.
- **Queue Latency**: Job submission on shared Open Plan backends experiences variable cloud queue latency (ranging from minutes to hours), necessitating fully asynchronous, resumable, and idempotent data collection routines.

---

## 3. Physical Qubit Subsystem Scope
- **3-Qubit Chain Limitation**: Experiments isolate a fixed 3-qubit linear subgraph per backend to maximize circuit depth and fidelity under shallow-depth limits while conserving QPU time.
- **Crosstalk & Full-Chip Dynamics**: Global spectator crosstalk, long-range leakage, and whole-chip thermal gradients across unselected qubits outside the 3-qubit chain are not directly probed.

---

## 4. Adversarial Simulator Modeling
- **Noise Model Limits**: S1 and S2 simulators are derived from backend calibration snapshots (T1, T2, readout error, 2Q gate errors). They capture local incoherent Markovian noise but omit non-Markovian memory effects, dynamic two-level system (TLS) fluctuator hopping, and pulse-level cross-resonance phase distortions.
- **Adaptive Readout Modeling (S2)**: The empirical readout confusion matrix fitted on training calibration circuits partially elevates adversary acceptance, but is constrained to stationary measurement probabilities.

---

## 5. Test-Round Temporal Correlation under Compressed Cadence (Rounds 8–10)
- **Reduced Separation Floor**: To accommodate the hard deadline cutoff of Oct 10, 12:00 local time, the per-backend minimum gap for rounds 8 onward was reduced to 2.0 hours (rounds 1–7 remain strictly at $\ge 4.0\,\text{h}$, with a $67.6\,\text{h}$ separation between Round 6 and Round 7).
- **Correlation Caveat**: Spacing test rounds $\sim 2 - 3\,\text{hours}$ apart implies test samples capture shorter-timescale noise fluctuations and may exhibit higher temporal correlation than earlier rounds.
- **Analytical Safeguards**: In E3 (persistence), E5 (open-set), and all bootstrap calculations, exact elapsed hours from raw hardware timestamps are used for drift evaluation, and confidence intervals are computed via round-level resampling with an explicit note that test rounds are not fully independent.

---

## 6. Data Collection Termination at Round 10 under Hard Cutoff
- **Enforced Cutoff**: Collection terminated at Round 10 at the Oct 10, 12:00 local time cutoff to allow experimental synthesis and manuscript finalization for MARC 2027.
- **Sample Distribution**: The experimental dataset contains 10 discrete rounds across 3 operational backends (train: 1-5, val: 6-7, test: 8-10), providing 3 test rounds rather than the originally envisioned 5 test rounds under Schedule B.
- **Statistical Power**: The 3 test rounds provide 24 independent test chunks per backend-circuit pair (720 test evaluations total), fully sufficient for non-parametric bootstrap resampling (200 iterations) and chronological evaluation, while capturing physical drift across calibration cycles.

---

## 7. Pre-Paper Implementation Audit Findings & Quantitative Boundaries
- **Temporal Drift vs Genuine False-Reject Rate**: Fixed validation thresholds ($\text{FPR}=0.05$ on rounds 6–7) incur substantial genuine FRR on test rounds 8–10 due to physical hardware drift: `ibm_fez` FRR = 0.4167, `ibm_kingston` FRR = 0.2083, and `ibm_marrakesh` FRR = 0.9583. While open-set rejection of held-out backends remains 100.0% (mean score 36.50 vs 15.87 for Fez), genuine devices also drift away from their training/validation manifolds.
- **Model Selection Protocol**: Logistic Regression was selected as primary model based strictly on validation rounds 6–7 (Val Acc: 0.6875). Test accuracy for this primary model is 0.6667 (Bal Acc: 0.6667, Macro F1: 0.6440, 95% Round-CI: [0.583, 0.708]). SVM-RBF achieved 0.7361 on test, while tree ensembles degraded significantly under temporal drift (Random Forest: 0.4444; Gradient Boosting: 0.4028).
- **Confidence Interval Structure**: CIs in `results.json` for E1 resample rounds (multisets of [8, 9, 10]); chunk-level CIs for E3 reflect intra-round shot variance ($n=24$ chunks/round).
- **Hardware Record Recoveries**: Three rounds were recovered: `ibm_kingston` Round 5 (Qiskit ALAP missing `cz` gate duration fallback) and `ibm_kingston` Rounds 9 and 10 (post-hoc API retrieval after local worker socket timeout during 361.6-minute host sleep). Excluding recovered Kingston rounds shifts E1 test accuracy between -0.0595 and +0.0853.
- **Log Evidence for Halting at Round 10**: `pipeline_autonomous.log` records submission of Round 10 at 21:20:15 local on 2026-10-09. Host sleep of 361.6 minutes caused a socket disconnection (`getaddrinfo failed`), triggering the orchestrator safety halt at 05:14:53 local. When resumed at ~10:30 local, only 1.5 hours remained until the 12:00 cutoff, preventing rounds 11–12 under the 2.0-hour hard floor.


