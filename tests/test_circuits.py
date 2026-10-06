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


def test_c10_fallback_equivalence_and_barrier_position():
    """Verify that c10 fallback transpile path produces a circuit equivalent to ALAP path.
    
    Specifically confirms:
    1. Only c10 (and no other circuit) uses scheduling / delay instructions.
    2. Under both normal ALAP path and Fallback path, delay duration == 7500dt (30 us).
    3. The delay instructions' position relative to the mirror circuit's midpoint barriers
       is identical: exactly 3 delay instructions positioned strictly between barrier_0
       and barrier_1 on qubits [0, 1, 2].
    4. Midpoint barrier protection survives the fallback without gate cancellation.
    """
    from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
    from qfp.circuits import transpile_benchmark_circuits

    backend = FakeSherbrooke()
    circuits = build_benchmark_circuits(seed=42)

    # 1. Assert only c10 contains delay instructions among all benchmark circuits
    for cid, qc in circuits.items():
        has_delay = any(inst.operation.name == "delay" for inst in qc.data)
        if cid == "c10_mirror_depth24_delay":
            assert has_delay, "c10 must contain delay instructions"
        else:
            assert not has_delay, f"Circuit {cid} should not contain delay instructions"

    # 2. Transpile via both ALAP and Fallback paths
    layout = [0, 1, 2]
    t_alap, path_alap = transpile_benchmark_circuits(
        circuits, backend, layout, force_path="alap", return_path=True
    )
    t_fall, path_fall = transpile_benchmark_circuits(
        circuits, backend, layout, force_path="fallback", return_path=True
    )

    assert path_alap == "alap", f"Expected 'alap' path, got {path_alap}"
    assert path_fall == "fallback", f"Expected 'fallback' path, got {path_fall}"

    c10_alap = t_alap["c10_mirror_depth24_delay"]
    c10_fall = t_fall["c10_mirror_depth24_delay"]

    # 3. Assert delay duration == 7500dt and position relative to midpoint barriers survives
    for path_name, circ in [("alap", c10_alap), ("fallback", c10_fall)]:
        barrier_indices = [
            idx for idx, inst in enumerate(circ.data) if inst.operation.name == "barrier"
        ]
        assert len(barrier_indices) >= 2, (
            f"{path_name}: Expected at least 2 barriers (midpoint entry & exit), "
            f"found {len(barrier_indices)}"
        )
        b0, b1 = barrier_indices[0], barrier_indices[1]

        # Instructions strictly between b0 and b1 must be exactly the 3 dephasing delays
        mid_ops = circ.data[b0 + 1 : b1]
        assert len(mid_ops) == 3, (
            f"{path_name}: Expected exactly 3 instructions between midpoint barriers, "
            f"got {len(mid_ops)}"
        )

        delays_found = []
        for inst in mid_ops:
            assert inst.operation.name == "delay", (
                f"{path_name}: Midpoint instruction is {inst.operation.name}, expected 'delay'"
            )
            assert inst.operation.duration == 7500, (
                f"{path_name}: Delay duration {inst.operation.duration} != 7500dt"
            )
            assert inst.operation.unit == "dt", (
                f"{path_name}: Delay unit {inst.operation.unit} != 'dt'"
            )
            q_idx = [circ.find_bit(q).index for q in inst.qubits]
            delays_found.append(q_idx)

        assert sorted(delays_found) == [[0], [1], [2]], (
            f"{path_name}: Midpoint delays not targeted to layout qubits [0, 1, 2]"
        )

        # Assert no 7500dt dephasing delay leaked before b0 or after b1
        pre_delays = [
            inst for inst in circ.data[:b0]
            if inst.operation.name == "delay" and inst.operation.duration == 7500
        ]
        assert len(pre_delays) == 0, f"{path_name}: Found 7500dt delay before midpoint barrier b0"

