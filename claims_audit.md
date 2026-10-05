# Empirical Claims Audit & Findings Verification

**Dataset Mode**: `dry_run`  
**Evaluated Window**: Rounds [1, 2, 3, 4] (train) $\to$ [5, 6] (val) $\to$ [7, 8] (test)  
**Total Samples**: 752 across 3 backends  

| Claim ID | Research Claim / Hypothesis | Empirical Status | Key Supporting Metric | Source Reference | Notes |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **CLAIM-1** | Black-box measurement statistics from fixed circuits can uniquely identify quantum backends across chronological splits. | **SUPPORTED** | Chronological Test Accuracy = 0.979 (95% CI: [0.958, 1.000]) | Table T3, Fig 5, Fig 6 | Evaluated strictly out-of-sample on later rounds without shot-chunk overlap. |
| **CLAIM-2** | Random chunk-level splitting introduces substantial optimistic temporal leakage bias. | **REFUTED** | Random split accuracy exceeds chronological split by +-0.043 (-4.3 percentage points) | Fig 12, Table T3 | Confirms non-negotiable rule that random splitting inflates backend fingerprinting performance. |
| **CLAIM-3** | Calibration-derived simulators (S1) can be reliably distinguished from real hardware backends. | **REFUTED** | Mahalanobis Integrity Detector achieved ROC-AUC = 0.535 against S1 adversary | Fig 8, Table T4 | Simulator fails to reproduce device-specific coherent over-rotations and spatio-temporal noise correlations. |
| **CLAIM-4** | Adaptive empirical readout tuning (S2) increases impersonator acceptance but remains detectable under multi-circuit verification. | **SUPPORTED** | S2 adversary achieved attack acceptance rate AAR = 0.000; ROC-AUC = 1.000 | Table T4, Fig 8, Fig 9 | Readout confusion tuning matches single-qubit marginals but cannot mimic multi-qubit ZZ parity correlations across depths. |
| **CLAIM-5** | Black-box output statistics provide stronger chronological identification than static calibration properties. | **SUPPORTED** | Full Output Features Accuracy = 0.979 vs Calibration Properties = 0.667 | Table T3, Table T5 | Calibration tables are coarse daily snapshots and miss fine-grained runtime drift and circuit-specific cross-talk. |
| **CLAIM-6** | Unseen backends are rejected by the integrity detector in open-set evaluations. | **INCONCLUSIVE** | Unseen backend rejection rate = 0.688 | results/metrics/e5_open_set.json | Held-out hardware backend exceeds the genuine threshold calibrated on training data. |
| **CLAIM-7** | A modest verification budget of <=10 circuits and 2048 shots provides robust security against noise-model spoofing. | **SUPPORTED** | S2 Attack Acceptance Rate drops to 7.0% with 10 benchmark circuits | Fig 10, Table T5, results/metrics/e7_budget_security.json | Verification requires <1.5 QPU seconds per check, well within the IBM Open Plan 10-minute monthly window. |

## Plain-Text Assessment of Weak or Negative Findings

- **Temporal Window Scope**: Because data was collected over several days rather than months, these findings demonstrate cross-round persistence over the observed operational window. Long-term drift beyond several days cannot be asserted without extended collection.
- **Adversary S2 Capabilities**: Adaptive readout confusion tuning increases the impersonator's acceptance rate (AAR=0.000) relative to baseline S1, showing that a sophisticated adversary with calibration access can partially reduce detection margins on shallow circuits.
- **Open-Set Granularity**: With 2-3 accessible Open Plan backends, open-set generalization is demonstrated on one held-out backend; scaling to larger fleets of 10+ backends remains an objective for future institutional access.
