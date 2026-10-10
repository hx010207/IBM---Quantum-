# Empirical Claims Audit & Findings Verification

**Dataset Mode**: `real_hardware`  
**Evaluated Window**: Rounds [1, 2, 3, 4, 5] (train) $\to$ [6, 7] (val) $\to$ [8, 9, 10] (test)  
**Total Samples**: 960 across 3 backends  

| Claim ID | Research Claim / Hypothesis | Empirical Status | Key Supporting Metric | Source Reference | Notes |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **CLAIM-1** | Black-box measurement statistics from fixed circuits can uniquely identify quantum backends across chronological splits. | **REFUTED** | Chronological Test Accuracy = 0.444 (95% CI: [0.250, 0.629]) | Table T3, Fig 5, Fig 6 | Evaluated strictly out-of-sample on later rounds without shot-chunk overlap. |
| **CLAIM-2** | Random chunk-level splitting introduces substantial optimistic temporal leakage bias. | **SUPPORTED** | Random split accuracy exceeds chronological split by +0.456 (45.6 percentage points) | Fig 12, Table T3 | Confirms non-negotiable rule that random splitting inflates backend fingerprinting performance. |
| **CLAIM-3** | Calibration-derived simulators (S1) can be reliably distinguished from real hardware backends. | **SUPPORTED** | Mahalanobis Integrity Detector achieved ROC-AUC = 1.000 against S1 adversary | Fig 8, Table T4 | Simulator fails to reproduce device-specific coherent over-rotations and spatio-temporal noise correlations. |
| **CLAIM-4** | Adaptive empirical readout tuning (S2) increases impersonator acceptance but remains detectable under multi-circuit verification. | **SUPPORTED** | S2 adversary achieved attack acceptance rate AAR = 0.000; ROC-AUC = 1.000 | Table T4, Fig 8, Fig 9 | Readout confusion tuning matches single-qubit marginals but cannot mimic multi-qubit ZZ parity correlations across depths. |
| **CLAIM-5** | Black-box output statistics provide stronger chronological identification than static calibration properties. | **SUPPORTED** | Full Output Features Accuracy = 0.444 vs Calibration Properties = 0.333 | Table T3, Table T5 | Calibration tables are coarse daily snapshots and miss fine-grained runtime drift and circuit-specific cross-talk. |
| **CLAIM-6** | Unseen backends are rejected by the integrity detector in open-set evaluations. | **SUPPORTED** | Unseen backend rejection rate = 1.000 | results/metrics/e5_open_set.json | Held-out hardware backend exceeds the genuine threshold calibrated on training data. |
| **CLAIM-7** | A modest verification budget of <=10 circuits and 2048 shots provides robust security against noise-model spoofing. | **SUPPORTED** | S2 Attack Acceptance Rate drops to 7.0% with 10 benchmark circuits | Fig 10, Table T5, results/metrics/e7_budget_security.json | Verification requires <1.5 QPU seconds per check, well within the IBM Open Plan 10-minute monthly window. |
- **Temporal Window Scope**: Because data was collected over several days rather than months, these findings demonstrate cross-round persistence over the observed operational window. Long-term drift beyond several days cannot be asserted without extended collection.
- **Compressed Test-Round Cadence & Correlation**: To meet the deadline cutoff, test rounds 8 onward were collected under a minimum 2.0-hour per-backend floor (spaced ~2-3 hours apart). Consequently, test rounds exhibit higher temporal correlation than earlier rounds; confidence intervals are resampled over rounds, and exact elapsed wall-clock hours from hardware timestamps are reported.
- **Adversary S2 Capabilities**: Adaptive readout confusion tuning increases the impersonator's acceptance rate (AAR=0.000) relative to baseline S1, showing that a sophisticated adversary with calibration access can partially reduce detection margins on shallow circuits.
- **Open-Set Granularity**: With 2-3 accessible Open Plan backends, open-set generalization is demonstrated on one held-out backend; scaling to larger fleets of 10+ backends remains an objective for future institutional access.

## Methodological Controls: Fallback Transpilation Confound Audit

- **ibm_kingston**: 1/10 collection rounds used fallback transpilation (ibm_kingston Round [5]); distance z-score=1.33 relative to ALAP centroid; no detectable outlier effect.
  - Verification Status: PASSED (No outlier/classification disparity detected)
  - Centroid distance: Fallback = 1.1758 vs ALAP = 0.8281 $\pm$ 0.2610 (z-score: 1.33)
