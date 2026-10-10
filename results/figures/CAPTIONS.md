# Figure Captions Catalog

Dataset context:
- Run mode: `real_hardware`
- Total samples: 960 (240 hardware/dry-run samples, 720 simulator samples)
- Training rounds: [1, 2, 3, 4, 5]
- Validation rounds: [6, 7]
- Test rounds: [8, 9, 10]

---

### Figure 1: Experiment Pipeline and Threat Model
Schematic illustration of the experimental architecture and trust verification pipeline. User-visible black-box measurement statistics are generated across 10 standardized 3-qubit circuits on real IBM Quantum backends ($R_1, R_2, R_3$) and three classes of adversary simulators ($S_0$: ideal noiseless, $S_1$: calibration-derived noise model, $S_2$: adaptive noise model with empirical readout confusion). Features are mapped into a 196-dimensional representation, and integrity detectors evaluate incoming workloads against genuine hardware profiles.

### Figure 2: The Benchmark Circuit Suite
Circuit schematics for four representative 3-qubit circuits from the 10-circuit benchmark suite: Bell pair on edge (0, 1), GHZ state directed $0\to 1\to 2$, seeded random Clifford circuit (depth $\sim 8$), and barrier-protected mirror circuit (depth $\sim 12$). Barriers prevent compiler optimization passes from canceling the forward and backward unitary blocks.

### Figure 3: Example Output Probability Distributions
Grouped empirical measurement outcome probabilities for the 3-qubit GHZ benchmark circuit ($c05\_ghz\_012$) across real backends and simulator classes ($S_0, S_1, S_2$). Error bars depict the standard deviation across chronological sample chunks (256 shots/chunk).

### Figure 4: Two-Dimensional PCA Embedding of Statistical Feature Space
Principal component projection of the 196-dimensional statistical feature representation across all sample chunks. Samples are colored by physical backend class. Circles denote real hardware executions; triangles denote simulator impersonation workloads.

### Figure 5: Normalized Confusion Matrix for Closed-Set Identification
Classification confusion matrix for closed-set backend identification on the hold-out test rounds ([8, 9, 10]) under a chronological split. Values display normalized class recall with absolute chunk sample counts in parentheses.

### Figure 6: Cross-Day Identification Accuracy vs Elapsed Wall-Clock Time
Backend identification accuracy evaluated at increasing elapsed wall-clock separation intervals (hours derived directly from hardware execution timestamps) between training rounds ([1, 2]) and subsequent test rounds. Shaded envelope indicates the 95% confidence interval computed via round-level bootstrap resampling (with test rounds spaced ~2-3h apart under the compressed cadence noted as not fully independent).

### Figure 7: Inter-Round Total Variation Distance Drift Heatmap
Pairwise Total Variation Distance (TVD) matrix computed between collection rounds for backend `ibm_fez` across the 10 benchmark circuits. Measures empirical drift over the observed experimental collection window.

### Figure 8: Receiver Operating Characteristic (ROC) Curves for Spoofing Detection
ROC curves for the Mahalanobis integrity detector trained exclusively on genuine data of `ibm_fez`. Curves evaluate discrimination against cross-device hardware ($R_j$), ideal simulation ($S_0$), calibration-derived simulation ($S_1$), and adaptive empirical simulation ($S_2$).

### Figure 9: False Acceptance Rate (FAR) and False Rejection Rate (FRR) vs Decision Threshold
Operational error trade-off curve showing FAR and FRR as a function of the detector anomaly threshold. The Equal Error Rate (EER) operating point is marked at the intersection.

### Figure 10: Performance Sensitivity to Shots per Sample Chunk
Ablation analysis demonstrating identification accuracy and spoofing detection ROC-AUC as sample chunk size varies from 128 to 2048 shots per circuit.

### Figure 11: Top Statistical Feature Importance
Relative feature importance ranking extracted from the top-performing ensemble classifier, highlighting the diagnostic contribution of pairwise $ZZ$ correlators, per-qubit marginals, and information-theoretic divergence metrics.

### Figure 12: Chronological Split vs Random-Split Leakage Comparison
Performance comparison across supervised classifiers under the valid chronological split (rounds 1..4 train, 5..6 val, 7..8 test) versus an unconstrained random chunk-level split, quantifying the degree of optimistic performance bias introduced by round-level temporal leakage.
