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
