"""3-Qubit Benchmark Circuit Suite for Quantum Fingerprinting.

Defines the 10 standardized 3-qubit circuits sensitive to readout errors,
two-qubit coupling edges, entangling direction, coherent gate over-rotation,
depth accumulation, and decoherence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from qiskit import QuantumCircuit, qpy, transpile
from qiskit.quantum_info import Clifford, Statevector, random_clifford


CIRCUIT_NAMES = [
    "c01_prep_000",
    "c02_prep_111",
    "c03_bell_01",
    "c04_bell_12",
    "c05_ghz_012",
    "c06_ghz_210",
    "c07_clifford_depth8",
    "c08_clifford_depth24",
    "c09_mirror_depth12",
    "c10_mirror_depth24_delay",
]


def _build_mirror_unitary(
    num_qubits: int = 3,
    depth: int = 6,
    seed: int = 42,
) -> Tuple[QuantumCircuit, QuantumCircuit]:
    """Generates a forward pseudo-random unitary block and its exact inverse.
    
    Args:
        num_qubits: Number of qubits (3).
        depth: Number of alternating 1Q-2Q layers.
        seed: Random seed for reproducibility.
        
    Returns:
        Tuple of (forward_circuit, inverse_circuit).
    """
    rng = np.random.default_rng(seed)
    fwd = QuantumCircuit(num_qubits, name="fwd_block")
    
    for layer in range(depth):
        # 1-Qubit layer
        for q in range(num_qubits):
            choice = rng.choice(["sx", "x", "rz", "h", "s"])
            if choice == "sx":
                fwd.sx(q)
            elif choice == "x":
                fwd.x(q)
            elif choice == "rz":
                theta = float(rng.choice([np.pi / 4, np.pi / 2, np.pi, 3 * np.pi / 4]))
                fwd.rz(theta, q)
            elif choice == "h":
                fwd.h(q)
            elif choice == "s":
                fwd.s(q)
        
        # 2-Qubit layer
        if layer % 2 == 0:
            fwd.cx(0, 1)
        else:
            fwd.cx(1, 2)
            
    inv = fwd.inverse()
    inv.name = "inv_block"
    return fwd, inv


def build_benchmark_circuits(
    seed: int = 42,
    delay_dt: int = 7500,
    delay_sec: Optional[float] = None,
    backend: Optional[Any] = None,
) -> Dict[str, QuantumCircuit]:
    """Constructs the canonical 10 benchmark circuits on 3 logical qubits.
    
    Args:
        seed: Master seed for random Clifford and mirror circuits.
        delay_dt: Delay duration in dt units for circuit 10 (default 7500 dt = 30 us at dt=4ns).
        delay_sec: Delay duration in real seconds (e.g. 30e-6 for 30 us). If supplied, takes precedence.
        backend: Optional backend to query dt and timing constraints.
        
    Returns:
        Dictionary mapping circuit ID to QuantumCircuit (with measure_all applied).
    """
    if delay_sec is not None:
        dt = 4e-09
        if backend is not None:
            dt = getattr(backend, "dt", None) or getattr(getattr(backend, "target", None), "dt", 4e-09)
        delay_dt = int(round(delay_sec / dt))
    circuits: Dict[str, QuantumCircuit] = {}

    # 1. State preparation |000>
    c1 = QuantumCircuit(3, name="c01_prep_000")
    c1.measure_all()
    circuits["c01_prep_000"] = c1

    # 2. State preparation |111>
    c2 = QuantumCircuit(3, name="c02_prep_111")
    c2.x([0, 1, 2])
    c2.measure_all()
    circuits["c02_prep_111"] = c2

    # 3. Bell pair on physical edge (0, 1)
    c3 = QuantumCircuit(3, name="c03_bell_01")
    c3.h(0)
    c3.cx(0, 1)
    c3.measure_all()
    circuits["c03_bell_01"] = c3

    # 4. Bell pair on physical edge (1, 2)
    c4 = QuantumCircuit(3, name="c04_bell_12")
    c4.h(1)
    c4.cx(1, 2)
    c4.measure_all()
    circuits["c04_bell_12"] = c4

    # 5. GHZ state directed 0 -> 1 -> 2
    c5 = QuantumCircuit(3, name="c05_ghz_012")
    c5.h(0)
    c5.cx(0, 1)
    c5.cx(1, 2)
    c5.measure_all()
    circuits["c05_ghz_012"] = c5

    # 6. GHZ state directed 2 -> 1 -> 0
    c6 = QuantumCircuit(3, name="c06_ghz_210")
    c6.h(2)
    c6.cx(2, 1)
    c6.cx(1, 0)
    c6.measure_all()
    circuits["c06_ghz_210"] = c6

    # 7. Seeded random Clifford (depth ~8)
    c7_raw = random_clifford(3, seed=seed).to_circuit()
    c7 = QuantumCircuit(3, name="c07_clifford_depth8")
    c7.compose(c7_raw, inplace=True)
    c7.measure_all()
    circuits["c07_clifford_depth8"] = c7

    # 8. Seeded random Clifford (depth ~24)
    c8_1 = random_clifford(3, seed=seed + 10).to_circuit()
    c8_2 = random_clifford(3, seed=seed + 20).to_circuit()
    c8 = QuantumCircuit(3, name="c08_clifford_depth24")
    c8.compose(c8_1, inplace=True)
    c8.barrier()
    c8.compose(c8_2, inplace=True)
    c8.measure_all()
    circuits["c08_clifford_depth24"] = c8

    # 9. Seeded mirror circuit (depth ~12)
    # Uses a barrier at reflection point to prevent compiler from optimizing U * U^dag to identity
    fwd9, inv9 = _build_mirror_unitary(num_qubits=3, depth=6, seed=seed + 30)
    c9 = QuantumCircuit(3, name="c09_mirror_depth12")
    c9.compose(fwd9, inplace=True)
    c9.barrier()  # CRITICAL: prevents cancellation across the midpoint
    c9.compose(inv9, inplace=True)
    c9.measure_all()
    circuits["c09_mirror_depth12"] = c9

    # 10. Seeded mirror circuit (depth ~24 + delay)
    fwd10, inv10 = _build_mirror_unitary(num_qubits=3, depth=10, seed=seed + 40)
    c10 = QuantumCircuit(3, name="c10_mirror_depth24_delay")
    c10.compose(fwd10, inplace=True)
    c10.barrier()
    c10.delay(delay_dt, 0, unit="dt")
    c10.delay(delay_dt, 1, unit="dt")
    c10.delay(delay_dt, 2, unit="dt")
    c10.barrier()
    c10.compose(inv10, inplace=True)
    c10.measure_all()
    circuits["c10_mirror_depth24_delay"] = c10

    return circuits


def transpile_benchmark_circuits(
    circuits: Dict[str, QuantumCircuit],
    backend: Any,
    initial_layout: List[int],
    optimization_level: int = 1,
) -> Dict[str, QuantumCircuit]:
    """Transpiles benchmark circuits to native backend target instructions.
    
    Fixed physical layout and scheduling ensures deterministic mapping.
    
    Args:
        circuits: Logical benchmark circuits.
        backend: IBM hardware backend or fake backend object.
        initial_layout: Physical qubit indices (e.g. [0, 1, 2]).
        optimization_level: Transpiler optimization level (default 1).
        
    Returns:
        Dictionary of transpiled native QuantumCircuits.
    """
    transpiled = {}
    circuit_list = list(circuits.values())
    
    # Check if any circuit contains delays
    has_delay = any(any(inst.operation.name == "delay" for inst in qc.data) for qc in circuit_list)
    scheduling = "alap" if has_delay else None
    
    t_list = transpile(
        circuit_list,
        backend=backend,
        initial_layout=initial_layout,
        optimization_level=optimization_level,
        scheduling_method=scheduling,
        seed_transpiler=42,
    )
    
    for original_id, t_qc in zip(circuits.keys(), t_list):
        t_qc.name = original_id
        transpiled[original_id] = t_qc
        
    return transpiled


def compute_ideal_probabilities(circuits: Dict[str, QuantumCircuit]) -> Dict[str, np.ndarray]:
    """Computes noiseless ideal statevector measurement probability vectors for all circuits.
    
    Returns:
        Dict mapping circuit ID to an 8-element probability array for states |000> ... |111>.
    """
    ideal_probs = {}
    for cid, qc in circuits.items():
        # Remove measurements and barriers for pure statevector simulation
        qc_pure = QuantumCircuit(3)
        for inst in qc.data:
            op_name = inst.operation.name
            if op_name not in ("measure", "barrier", "delay"):
                # Map logical qubits 0, 1, 2
                qubit_indices = [qc.find_bit(q).index for q in inst.qubits]
                qc_pure.append(inst.operation, qubit_indices)
                
        sv = Statevector.from_instruction(qc_pure)
        probs = sv.probabilities()  # Length 8: 000, 001, 010, 011, 100, 101, 110, 111
        ideal_probs[cid] = probs
    return ideal_probs


def save_circuits_qpy(circuits: Dict[str, QuantumCircuit], filepath: Union[str, Path]) -> None:
    """Serializes circuits to binary QPY format."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        qpy.dump(list(circuits.values()), f)


def load_circuits_qpy(filepath: Union[str, Path]) -> Dict[str, QuantumCircuit]:
    """Loads circuits from binary QPY format."""
    path = Path(filepath)
    with open(path, "rb") as f:
        loaded_list = qpy.load(f)
    return {qc.name: qc for qc in loaded_list}
