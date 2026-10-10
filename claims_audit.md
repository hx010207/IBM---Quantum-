# Empirical Claims Audit & Findings Verification

**Dataset Mode**: `real_hardware`  
**Evaluated Window**: Rounds [1, 2, 3, 4, 5] (train) $\to$ [6, 7] (val) $\to$ [8, 9, 10] (test)  
**Total Samples**: 960 across 3 backends  

| Claim ID | Research Claim / Hypothesis | Empirical Status | Key Supporting Metric | Source Reference | Notes |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **CLAIM-1** | Black-box measurement statistics from fixed circuits can uniquely identify quantum backends across chronological splits. | **PARTIALLY SUPPORTED / DRIFT-CONSTRAINED** | Primary Model (LogReg): Acc = 0.667 [0.583, 0.708]; SVM-RBF: 0.736; RF: 0.444; GB: 0.403; MLP: 0.514 | Table T3, Fig 5, Fig 6 | Selected primary on val (LogReg acc 0.688); linear/kernel models withstand drift better than tree ensembles. |
| Claim ID | Research Claim / Hypothesis | Empirical Status | Key Supporting Metric | Source Reference | Notes |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **CLAIM-1** | Black-box measurement statistics from fixed circuits can uniquely identify quantum backends across chronological splits. | **PARTIALLY SUPPORTED / DRIFT-CONSTRAINED** | Primary Model (LogReg): Acc = 0.667 [0.583, 0.708]; SVM-RBF: 0.736; RF: 0.444; GB: 0.403; MLP: 0.514 | Table T3, Fig 5, Fig 6 | Selected primary on val (LogReg acc 0.688); linear/kernel models withstand drift better than tree ensembles. |
| **CLAIM-2** | Random chunk-level splitting introduces substantial optimistic temporal leakage bias across all model architectures. | **SUPPORTED** | Random split accuracy exceeds chronological split by +20.62 pp (SVM) to +53.96 pp (GB); RF gap: +50.14 pp | Fig 12, Table T3, scripts/audit_point5_leakage.py | Confirms non-negotiable rule: random chunk splitting inflates all architectures (LogReg +25.1 pp, MLP +38.9 pp). |
| **CLAIM-3** | Calibration-derived simulators (S1) can be reliably distinguished from real hardware backends. | **SUPPORTED (BACKEND-DEPENDENT ON DRIFT)** | Fez/Kingston Integrity Detectors achieved ROC-AUC = 1.000 vs S1; Fleet-wide E2 classifiers achieve AUC 1.000 (0.996-0.999 without c10) | Fig 8, Table T4, scripts/audit_point3_ablations.py | Marrakesh test detector degraded (AUC 0.186 vs S1) due to physical qubit 5 degradation and calibration drift. |
| **CLAIM-4** | Adaptive empirical readout tuning (S2) increases impersonator acceptance but remains detectable under multi-circuit verification. | **SUPPORTED** | S2 adversary achieved attack acceptance rate AAR = 0.000 on Fez and Kingston; ROC-AUC = 1.000 | Table T4, Fig 8, Fig 9 | Readout confusion tuning matches single-qubit marginals but cannot mimic multi-qubit ZZ parity correlations across depths. |
| **CLAIM-5** | Black-box output statistics provide stronger chronological identification than static calibration properties. | **SUPPORTED** | Full Output Features (Primary LogReg) = 0.667 vs Calibration Properties = 0.333 (0.429 on clean test chunks) | Table T3, Table T5 | Calibration tables are coarse daily snapshots and miss fine-grained runtime drift and circuit-specific cross-talk. |
| **CLAIM-6** | Unseen backends are rejected by the integrity detector in open-set evaluations. | **SUPPORTED (WITH HIGH GENUINE FRR)** | Unseen backend rejection = 1.000; Genuine seen FRR = 0.417 (Fez), 0.208 (Kingston), 0.958 (Marrakesh) | results/metrics/e5_open_set.json | Held-out hardware backend exceeds genuine threshold, but genuine device drift also elevates false rejections. |
| **CLAIM-7** | A modest verification budget of <=10 circuits and 2048 shots provides robust security against noise-model spoofing. | **SUPPORTED** | S2 Attack Acceptance Rate drops to 7.0% with 10 benchmark circuits | Fig 10, Table T5, results/metrics/e7_budget_security.json | Verification requires <1.5 QPU seconds per check, well within the IBM Open Plan 10-minute monthly window. |

---

## Pre-Paper Audit Findings & Rigor Controls

1. **Feature Integrity & Circuit Suite**:
   - Canonical 10 benchmark circuits (`src/qfp/circuits.py`): State prep ($c_1, c_2$), Bell pairs ($c_3, c_4$), GHZ ($c_5, c_6$), Random Cliffords ($c_7, c_8$), and Mirror circuits ($c_9, c_{10}$ with 30µs delay).
   - Zero provenance or metadata leakage (0/196 features). Feature extraction path is strictly `src/qfp/features.py`.
   - Aer simulation limitation: `NoiseModel.from_backend()` ignores `delay` instructions (`'delay' in noise_instructions` is `False`). Delays run noiselessly in S1/S2.
   - Leave-$c_{10}$-out ablations confirm E2 retains AUC $\ge 0.9963$ across models without delay features.
2. **Hardware Recalibration Drift Diagnosis (Marrakesh & Fez)**:
   - Identical execution pipeline across all rounds (layout `[4,5,6]`, 2048 shots, 8 chunks, transpile path `alap`).
   - Marrakesh R8 shift caused by physical qubit 5 degradation (spurious $|000\rangle$ excitation jumped to 6.64%). IBM recalibration registered qubit 5 readout error jumping 4x (0.0096 to 0.0361) in R9 before restoring to 0.0076 in R10.
3. **Multi-Model Leakage Gap Audit**:
   - Chronological vs Random split: LogReg (+25.14 pp), SVM (+20.62 pp), Random Forest (+50.14 pp), Gradient Boosting (+53.96 pp), MLP (+38.89 pp).
4. **Hardware Record Recovery**:
   - Kingston R5 (`transpile_fallback_and_post_hoc_retrieval`), Kingston R9 & R10 (`post_hoc_api_retrieval`). Retrieval-time field: `properties_snapshot`.
   - Like-for-like sensitivity on identical clean test chunks ($n=56$) shifts full feature accuracy by at most $\pm 0.0179$ and calibration baseline by $0.0000$.
5. **Operational Interruptions**:
   - 361.6-minute (6.03h) Windows host sleep occurred between 2026-10-09 23:14 and 2026-10-10 05:14 local despite keep-awake scripting, causing worker socket timeout and safety halt. Insufficient time remained before the Oct 10 12:00 cutoff to collect rounds 11–12 with the required 2.0h floor.
6. **Exploratory Re-Enrollment**:
   - Re-enrolling detectors on rounds 1–7 with post-gap validation calibration reduces Marrakesh FRR from 0.9583 to 0.5000.


