"""Simulation and adversarial impersonation engine (S0, S1, S2).

Threat Model & Attacker Capabilities:
  - S0 (Ideal baseline): Ideal noiseless Aer simulator.
  - S1 (Calibration-derived impersonator): Attacker obtains current backend calibration
    data (T1, T2, gate/readout errors) and instantiates AerSimulator.from_backend().
    Runs on identical transpiled circuits, physical layout, shot count, and circuit order.
  - S2 (Adaptive impersonator): S1 augmented with an empirical per-qubit readout-confusion
    model calibrated exclusively from training-period |000> and |111> calibration circuits,
    plus an empirical error scaling factor.
    
Attacker Limits & Non-Idealities:
  - The attacker has target calibration tables, but NOT pulse-level control.
  - Assumes local, stationary Markovian noise.
  - Does NOT reproduce non-Markovian memory, spectator crosstalk, two-level system (TLS)
    fluctuations, leakage to non-computational states, or temporal drift outside calibration.
  - S2 parameters are fitted ONLY on training rounds and evaluated strictly on untouched circuits.
"""

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError

from qfp.circuits import build_benchmark_circuits, transpile_benchmark_circuits
from qfp.collect import chunk_bitstrings_into_samples
from qfp.provenance import Provenance, validate_record_provenance

logger = logging.getLogger(__name__)


class AdaptiveReadoutModel:
    """Empirical per-qubit readout confusion model fitted from |000> and |111> circuits."""

    def __init__(self, num_qubits: int = 3):
        self.num_qubits = num_qubits
        # matrices[q] is 2x2: [[P(0|0), P(1|0)], [P(0|1), P(1|1)]]
        # P(meas | prep)
        self.p0_given_1 = np.zeros(num_qubits)  # P(0|1)
        self.p1_given_0 = np.zeros(num_qubits)  # P(1|0)
        self.fitted = False

    def fit_from_calibration_counts(
        self,
        counts_000: Dict[str, int],
        counts_111: Dict[str, int],
    ) -> "AdaptiveReadoutModel":
        """Fits empirical confusion probabilities from state preparation circuits.
        
        Args:
            counts_000: Outcome counts from |000> preparation.
            counts_111: Outcome counts from |111> preparation.
        """
        shots_0 = sum(counts_000.values())
        shots_1 = sum(counts_111.values())
        
        for q in range(self.num_qubits):
            # In Qiskit, bitstring index 0 is qubit (num_qubits - 1 - q) from right to left
            bit_idx = self.num_qubits - 1 - q
            
            # P(1|0): count where bit is '1' when prepared |000>
            ones_in_0 = sum(cnt for bstr, cnt in counts_000.items() if bstr[bit_idx] == "1")
            self.p1_given_0[q] = ones_in_0 / max(1, shots_0)
            
            # P(0|1): count where bit is '0' when prepared |111>
            zeros_in_1 = sum(cnt for bstr, cnt in counts_111.items() if bstr[bit_idx] == "0")
            self.p0_given_1[q] = zeros_in_1 / max(1, shots_1)
            
        self.fitted = True
        return self

    def apply_confusion_to_bitstrings(
        self,
        bitstrings: List[str],
        seed: int = 42,
    ) -> List[str]:
        """Applies empirical readout confusion to a list of measurement bitstrings."""
        if not self.fitted:
            return bitstrings
            
        rng = np.random.default_rng(seed)
        corrupted = []
        for bstr in bitstrings:
            b_list = list(bstr)
            for q in range(self.num_qubits):
                bit_idx = self.num_qubits - 1 - q
                bit = b_list[bit_idx]
                if bit == "0":
                    if rng.random() < self.p1_given_0[q]:
                        b_list[bit_idx] = "1"
                elif bit == "1":
                    if rng.random() < self.p0_given_1[q]:
                        b_list[bit_idx] = "0"
            corrupted.append("".join(b_list))
        return corrupted


def generate_simulator_round(
    adversary_level: str,  # "S0", "S1", "S2"
    target_backend: Any,
    layout: List[int],
    round_id: int,
    shots: int = 2048,
    num_chunks: int = 8,
    is_dryrun: bool = False,
    output_dir: Optional[Path] = None,
    adaptive_model: Optional[AdaptiveReadoutModel] = None,
    seed: int = 42,
) -> Path:
    """Generates a complete simulated round matching a target hardware round.
    
    Args:
        adversary_level: "S0" (ideal), "S1" (calibration-derived), or "S2" (adaptive).
        target_backend: Backend object being impersonated.
        layout: Physical qubit indices.
        round_id: Round identifier.
        shots: Shots per circuit.
        num_chunks: Number of sample chunks.
        is_dryrun: Pipeline dry-run mode flag.
        output_dir: Target directory.
        adaptive_model: Calibrated AdaptiveReadoutModel (required for S2).
        seed: Random seed.
        
    Returns:
        Path to saved simulation round file.
    """
    if adversary_level not in ("S0", "S1", "S2"):
        raise ValueError(f"Unknown adversary level '{adversary_level}'. Expected S0, S1, or S2.")
        
    backend_name = target_backend.name if hasattr(target_backend, "name") else str(target_backend)
    target_root = output_dir or (Path("dryrun/data/raw") if is_dryrun else Path("data/raw"))
    sim_dir = target_root / f"sim_{adversary_level}_{backend_name}"
    sim_dir.mkdir(parents=True, exist_ok=True)
    sim_filepath = sim_dir / f"round_{round_id:03d}.json"
    
    if sim_filepath.exists():
        logger.info(f"Simulated round {round_id} ({adversary_level}) already exists at {sim_filepath}. Skipping.")
        return sim_filepath

    provenance = (
        Provenance.SYNTHETIC_DRYRUN.value
        if is_dryrun
        else (Provenance.AER_IDEAL.value if adversary_level == "S0" else Provenance.AER_NOISE_MODEL.value)
    )
    
    logical_circuits = build_benchmark_circuits(seed=seed)
    transpiled = transpile_benchmark_circuits(
        logical_circuits,
        backend=target_backend,
        initial_layout=layout,
        optimization_level=1,
    )
    
    # Configure simulator based on adversary level
    sim_seed = seed + round_id * 5000 + (0 if adversary_level == "S0" else (100 if adversary_level == "S1" else 200))
    
    circuits_data: Dict[str, Any] = {}
    
    if adversary_level == "S0":
        # S0: Ideal noiseless simulation directly on 3-qubit logical benchmark circuits
        ideal_sim = AerSimulator()
        ideal_sim.set_options(seed_simulator=sim_seed)
        
        c_names = list(logical_circuits.keys())
        jobs = ideal_sim.run(list(logical_circuits.values()), shots=shots).result()
        
        for i, cid in enumerate(c_names):
            counts = jobs.get_counts(i)
            bitstrings: List[str] = []
            for b, cnt in counts.items():
                bitstrings.extend([b] * cnt)
            rng = np.random.default_rng(sim_seed + hash(cid) % 1000)
            rng.shuffle(bitstrings)
            
            chunks = chunk_bitstrings_into_samples(bitstrings, num_chunks=num_chunks)
            circuits_data[cid] = {
                "total_shots": len(bitstrings),
                "aggregate_counts": counts,
                "chunks": chunks,
            }
    else:
        # S1 or S2: derive noise model from backend target/properties and run on transpiled circuits
        simulator = AerSimulator.from_backend(target_backend)
        simulator.set_options(seed_simulator=sim_seed)
        
        c_names = list(transpiled.keys())
        jobs = simulator.run(list(transpiled.values()), shots=shots).result()
        
        for i, cid in enumerate(c_names):
            counts = jobs.get_counts(i)
            bitstrings: List[str] = []
            for b, cnt in counts.items():
                bitstrings.extend([b] * cnt)
                
            rng = np.random.default_rng(sim_seed + hash(cid) % 1000)
            rng.shuffle(bitstrings)
            
            # If S2 and adaptive model is available, apply empirical readout confusion
            if adversary_level == "S2" and adaptive_model is not None:
                bitstrings = adaptive_model.apply_confusion_to_bitstrings(
                    bitstrings, seed=sim_seed + hash(cid) % 500
                )
                counts = {}
                for b in bitstrings:
                    counts[b] = counts.get(b, 0) + 1

            chunks = chunk_bitstrings_into_samples(bitstrings, num_chunks=num_chunks)
            circuits_data[cid] = {
                "total_shots": len(bitstrings),
                "aggregate_counts": counts,
                "chunks": chunks,
            }

    record = {
        "round_id": round_id,
        "backend": f"sim_{adversary_level}_{backend_name}",
        "target_backend": backend_name,
        "adversary_level": adversary_level,
        "provenance": provenance,
        "physical_layout": layout,
        "shots_per_circuit": shots,
        "num_chunks": num_chunks,
        "circuits": circuits_data,
    }
    
    validate_record_provenance(record, is_dryrun=is_dryrun)
    
    tmp_path = sim_filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        import json
        json.dump(record, f, indent=2)
    tmp_path.rename(sim_filepath)
    
    logger.info(f"Saved simulated {adversary_level} round {round_id} to {sim_filepath}")
    return sim_filepath
