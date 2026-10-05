"""Unit tests for the 10 benchmark circuits and barrier protections."""

import numpy as np
from qfp.circuits import CIRCUIT_NAMES, build_benchmark_circuits, compute_ideal_probabilities


def test_ten_circuits_created():
    circuits = build_benchmark_circuits(seed=42)
    assert len(circuits) == 10
    for name in CIRCUIT_NAMES:
        assert name in circuits


def test_mirror_circuit_barrier_protection():
    circuits = build_benchmark_circuits(seed=42)
    c09 = circuits["c09_mirror_depth12"]
    
    # Check that a barrier exists in the mirror circuit to prevent gate cancellation
    has_barrier = any(inst.operation.name == "barrier" for inst in c09.data)
    assert has_barrier, "Mirror circuit c09 must contain a barrier to protect against compiler cancellation!"


def test_ideal_probabilities_validity():
    circuits = build_benchmark_circuits(seed=42)
    ideal_probs = compute_ideal_probabilities(circuits)
    
    for cid, probs in ideal_probs.items():
        assert len(probs) == 8
        assert np.isclose(np.sum(probs), 1.0), f"Ideal probabilities for {cid} do not sum to 1.0"
        assert np.all(probs >= 0.0)
