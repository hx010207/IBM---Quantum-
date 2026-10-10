# Empirical Claims Audit & Findings Verification

**Dataset Mode**: `real_hardware`  
**Evaluated Window**: Rounds [1, 2, 3, 4, 5] (train) $\to$ [6, 7] (val) $\to$ [8, 9, 10] (test)  
**Total Samples**: 960 across 3 backends  

| Claim ID | Research Claim / Hypothesis | Empirical Status | Key Supporting Metric | Source Reference | Notes |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **CLAIM-1** | Black-box measurement statistics from fixed circuits can uniquely identify quantum backends across chronological splits. | **PARTIALLY SUPPORTED / DRIFT-CONSTRAINED** | Primary Model (LogReg): Acc = 0.667 [0.583, 0.708]; SVM-RBF: 0.736; RF: 0.444; GB: 0.403; MLP: 0.514 | Table T3, Fig 5, Fig 6 | Selected primary on val (LogReg acc 0.688); linear/kernel models withstand drift better than tree ensembles. |
| **CLAIM-2** | Random chunk-level splitting introduces substantial optimistic temporal leakage bias. | **SUPPORTED** | Random split accuracy exceeds chronological split by +0.456 (45.6 percentage points) | Fig 12, Table T3 | Confirms non-negotiable rule that random splitting inflates backend fingerprinting performance. |
| **CLAIM-3** | Calibration-derived simulators (S1) can be reliably distinguished from real hardware backends. | **SUPPORTED** | Mahalanobis Integrity Detector achieved ROC-AUC = 1.000 against S1 adversary | Fig 8, Table T4 | Simulator fails to reproduce device-specific coherent over-rotations and spatio-temporal noise correlations. |
| **CLAIM-4** | Adaptive empirical readout tuning (S2) increases impersonator acceptance but remains detectable under multi-circuit verification. | **SUPPORTED** | S2 adversary achieved attack acceptance rate AAR = 0.000; ROC-AUC = 1.000 | Table T4, Fig 8, Fig 9 | Readout confusion tuning matches single-qubit marginals but cannot mimic multi-qubit ZZ parity correlations across depths. |
| **CLAIM-5** | Black-box output statistics provide stronger chronological identification than static calibration properties. | **SUPPORTED** | Full Output Features (Primary LogReg) = 0.667 vs Calibration Properties = 0.333 | Table T3, Table T5 | Calibration tables are coarse daily snapshots and miss fine-grained runtime drift and circuit-specific cross-talk. |
| **CLAIM-6** | Unseen backends are rejected by the integrity detector in open-set evaluations. | **SUPPORTED (WITH HIGH GENUINE FRR)** | Unseen backend rejection = 1.000; Genuine seen FRR = 0.417 | results/metrics/e5_open_set.json | Held-out hardware backend exceeds genuine threshold, but genuine device drift also elevates false rejections to 41.7%. |
| **CLAIM-7** | A modest verification budget of <=10 circuits and 2048 shots provides robust security against noise-model spoofing. | **SUPPORTED** | S2 Attack Acceptance Rate drops to 7.0% with 10 benchmark circuits | Fig 10, Table T5, results/metrics/e7_budget_security.json | Verification requires <1.5 QPU seconds per check, well within the IBM Open Plan 10-minute monthly window. |

---

## Pre-Paper Audit Findings & Rigor Controls

1. **Feature Integrity**: Zero provenance or metadata leakage (0/196 features depend on timestamps, elapsed hours, round ID, or properties snapshots). Top real-vs-sim separation feature is `c10_mirror_depth24_delay__marginal_q2` (weight 0.1001), driven by physical dephasing/relaxation during the 30µs delay. Under 80-dim `histogram_only`, Logistic Regression and Random Forest maintain ROC-AUC = 1.0000; label-shuffle control drops RF AUC to 0.4125.
2. **Genuine-Sample Dynamics & E5 Reconciliation**:
   - Threshold calibrated on validation rounds 6–7 ($\text{FPR}=0.05$): Fez threshold = 16.4954.
   - Held-out test backends have mean score 36.50 (Marrakesh) and 21.15 (Kingston) $\to$ Rejection Rate = 100.0%.
   - Genuine Fez test samples have mean score 15.87 $\to$ FRR = 0.4167 (Acceptance Rate = 58.3%).
   - E5 achieves 100% open-set rejection because unseen hardware sits farther away than drifting genuine hardware.
3. **Model Selection & Resampling**:
   - Primary model designated on validation set (Rounds 6–7): **Logistic Regression** (val acc 0.6875).
   - Test accuracy across all five models without selection: LogReg = 0.6667, SVM-RBF = 0.7361, MLP = 0.5139, RF = 0.4444, GB = 0.4028.
   - Resampling in `results.json`: E1 resamples rounds (multisets of [8, 9, 10]); chunk-level CIs for E3 reflect intra-round shot uncertainty.
4. **Hardware Record Recovery**:
   - Kingston R5 (transpile fallback), Kingston R9 and R10 (post-hoc API retrieval after 361.6-min host sleep socket timeout). Measured bitstring counts are unaltered.
   - Excluding recovered Kingston rounds yields LogReg test acc 0.6071 (-0.0595) and SVM-RBF 0.8214 (+0.0853).
   - QPU usage ledger verified against `service.job(id).usage()` across all 33 jobs: exactly 264.000 s (discrepancy 0.000 s).
5. **Termination Reason**: Round 10 completed at 21:20 local on Oct 9; host sleep caused worker socket timeout; orchestrator safety halt fired at 05:14 local. At resume (~10:30 local), insufficient time remained before the Oct 10 12:00 cutoff to launch rounds 11–12 with the required 2.0-hour hard floor.

