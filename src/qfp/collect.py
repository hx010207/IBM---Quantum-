"""Data collection engine for IBM Quantum hardware and dry-run execution.

Provides an idempotent, resumable, and provenance-tagged collector that
records full raw measurement bitstrings, chunked probability samples,
and backend calibration property snapshots.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from qiskit import QuantumCircuit
from qiskit.primitives.containers import PrimitiveResult
from qiskit_aer import AerSimulator

from qfp.budget import QPUBudgetGuard
from qfp.circuits import build_benchmark_circuits, transpile_benchmark_circuits
from qfp.provenance import Provenance, validate_record_provenance

logger = logging.getLogger(__name__)


def extract_backend_properties_snapshot(
    backend: Any,
    layout: List[int],
) -> Dict[str, Any]:
    """Extracts calibration properties (T1, T2, readout error, gate error) for the active qubits.
    
    Args:
        backend: IBMBackend or fake backend instance.
        layout: Physical qubit indices (e.g. [0, 1, 2]).
        
    Returns:
        Dictionary of calibration properties and update timestamp.
    """
    props_dict: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "calibration_date": None,
        "qubit_properties": {},
        "two_qubit_gate_errors": {},
    }
    
    if not hasattr(backend, "properties") or backend.properties() is None:
        return props_dict
        
    props = backend.properties()
    if hasattr(props, "last_update_date") and props.last_update_date:
        props_dict["calibration_date"] = str(props.last_update_date)
        
    for q in layout:
        q_props = {}
        try:
            q_props["t1_seconds"] = float(props.t1(q))
        except Exception:
            q_props["t1_seconds"] = None
        try:
            q_props["t2_seconds"] = float(props.t2(q))
        except Exception:
            q_props["t2_seconds"] = None
        try:
            q_props["readout_error"] = float(props.readout_error(q))
        except Exception:
            q_props["readout_error"] = None
        props_dict["qubit_properties"][str(q)] = q_props

    # Extract 2-qubit gate errors for adjacent pairs in layout
    for i in range(len(layout) - 1):
        q1, q2 = layout[i], layout[i + 1]
        pair_str = f"{q1}_{q2}"
        for gate_name in ["ecr", "cz", "cx"]:
            try:
                err = props.gate_error(gate_name, [q1, q2])
                if err is not None:
                    props_dict["two_qubit_gate_errors"][pair_str] = {
                        "gate": gate_name,
                        "error": float(err),
                    }
                    break
            except Exception:
                pass
                
    return props_dict


def chunk_bitstrings_into_samples(
    bitstrings: List[str],
    num_chunks: int = 8,
) -> List[Dict[str, int]]:
    """Splits a chronological sequence of measurement bitstrings into fixed chunk counts.
    
    Args:
        bitstrings: List of binary measurement outcome strings (e.g. ['000', '111', ...]).
        num_chunks: Number of chronological chunks to create.
        
    Returns:
        List of count dictionaries, one per chunk.
    """
    total_shots = len(bitstrings)
    chunk_size = total_shots // num_chunks
    if chunk_size == 0:
        raise ValueError(f"Cannot split {total_shots} shots into {num_chunks} chunks.")
        
    chunk_counts: List[Dict[str, int]] = []
    for i in range(num_chunks):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < num_chunks - 1 else total_shots
        chunk = bitstrings[start:end]
        
        counts: Dict[str, int] = {}
        for b in chunk:
            counts[b] = counts.get(b, 0) + 1
        chunk_counts.append(counts)
        
    return chunk_counts


def run_collection_round(
    backend: Any,
    layout: List[int],
    round_id: int,
    shots: int = 2048,
    num_chunks: int = 8,
    is_dryrun: bool = False,
    output_dir: Optional[Path] = None,
    budget_guard: Optional[QPUBudgetGuard] = None,
    seed: int = 42,
) -> Path:
    """Executes a complete benchmark round on the specified backend.
    
    This function is idempotent: if the round raw file already exists, it is
    skipped and returned immediately to avoid redundant QPU usage or overwrites.
    
    Args:
        backend: Backend instance (hardware or fake).
        layout: Physical qubit indices.
        round_id: Chronological round identifier (1-indexed integer).
        shots: Total shots per circuit (default 2048).
        num_chunks: Number of chunks per circuit (default 8 -> 256 shots/chunk).
        is_dryrun: If True, executes locally on fake backend with synthetic provenance.
        output_dir: Root directory for raw output (data/raw or dryrun/data/raw).
        budget_guard: Optional QPUBudgetGuard instance for real hardware.
        seed: Random seed for circuit generation and dry-run execution.
        
    Returns:
        Path to the immutable saved raw JSON file.
    """
    backend_name = backend.name if hasattr(backend, "name") else str(backend)
    target_root = output_dir or (Path("dryrun/data/raw") if is_dryrun else Path("data/raw"))
    backend_dir = target_root / backend_name
    backend_dir.mkdir(parents=True, exist_ok=True)
    raw_filepath = backend_dir / f"round_{round_id:03d}.json"
    
    if raw_filepath.exists():
        logger.info(f"Round {round_id} on {backend_name} already exists at {raw_filepath}. Skipping (idempotent).")
        return raw_filepath

    provenance = Provenance.SYNTHETIC_DRYRUN.value if is_dryrun else Provenance.IBM_HARDWARE.value
    start_time = datetime.utcnow().isoformat() + "Z"
    
    # 1. Build circuits and transpile
    logical_circuits = build_benchmark_circuits(seed=seed, backend=backend)
    transpiled, transpile_path = transpile_benchmark_circuits(
        logical_circuits,
        backend=backend,
        initial_layout=layout,
        optimization_level=1,
        return_path=True,
    )

    
    # 2. Extract backend calibration snapshot
    props_snapshot = extract_backend_properties_snapshot(backend, layout)
    
    # 3. Budget pre-flight check if real hardware
    if not is_dryrun and budget_guard:
        est_seconds = budget_guard.estimate_job_seconds(len(transpiled), shots)
        budget_guard.check_preflight_budget(est_seconds, is_dryrun=False)

    circuits_data: Dict[str, Any] = {}
    job_id = None
    execution_time_seconds = 0.0

    if is_dryrun:
        # Dry-run execution via local AerSimulator from backend
        sim = AerSimulator.from_backend(backend)
        sim.set_options(seed_simulator=seed + round_id * 1000)
        
        t0 = time.time()
        c_names = list(transpiled.keys())
        sim_res = sim.run(list(transpiled.values()), shots=shots).result()
        
        for i, cid in enumerate(c_names):
            counts = sim_res.get_counts(i)
            bitstrings: List[str] = []
            for b, cnt in counts.items():
                bitstrings.extend([b] * cnt)
            rng = np.random.default_rng(seed + round_id * 100 + hash(cid) % 1000)
            rng.shuffle(bitstrings)
            
            chunks = chunk_bitstrings_into_samples(bitstrings, num_chunks=num_chunks)
            circuits_data[cid] = {
                "total_shots": len(bitstrings),
                "aggregate_counts": counts,
                "chunks": chunks,
            }
        execution_time_seconds = time.time() - t0
        job_id = f"dryrun_job_r{round_id:03d}_{backend_name}"
    else:
        # Real IBM hardware execution via SamplerV2
        from qiskit_ibm_runtime import SamplerV2
        sampler = SamplerV2(mode=backend)
        
        # Build pub list: [(circuit, None, shots), ...]
        pubs = [(t_qc, None, shots) for t_qc in transpiled.values()]
        job = sampler.run(pubs)
        job_id = job.job_id()
        logger.info(f"Submitted hardware job {job_id} on {backend_name}. Waiting for results...")
        
        result: PrimitiveResult = job.result()
        
        # Readout usage if available
        try:
            usage_data = job.usage()
            if isinstance(usage_data, dict):
                execution_time_seconds = float(usage_data.get("quantum_seconds", 0.0))
            elif isinstance(usage_data, (int, float)):
                execution_time_seconds = float(usage_data)
        except Exception as e:
            logger.warning(f"Could not retrieve job.usage(): {e}")
            
        if execution_time_seconds <= 0.0:
            try:
                metrics = job.metrics() or {}
                execution_time_seconds = float(metrics.get("usage", {}).get("quantum_seconds", 0.0))
            except Exception:
                pass

        if budget_guard:
            budget_guard.record_job_consumption(execution_time_seconds, job_id=job_id, is_dryrun=False)

        # Process each pub result
        for (cid, _), pub_res in zip(transpiled.items(), result):
            # Extract bitstrings from primary classical data register
            meas_data = pub_res.data
            key = list(meas_data.keys())[0]
            bit_array = getattr(meas_data, key)
            bitstrings = bit_array.get_bitstrings()
            counts = bit_array.get_counts()
            chunks = chunk_bitstrings_into_samples(bitstrings, num_chunks=num_chunks)
            circuits_data[cid] = {
                "total_shots": len(bitstrings),
                "aggregate_counts": counts,
                "chunks": chunks,
            }

    end_time = datetime.utcnow().isoformat() + "Z"
    
    record = {
        "round_id": round_id,
        "backend": backend_name,
        "provenance": provenance,
        "transpile_path": transpile_path,
        "physical_layout": layout,
        "shots_per_circuit": shots,
        "num_chunks": num_chunks,
        "start_timestamp": start_time,
        "end_timestamp": end_time,
        "job_id": job_id,
        "execution_time_seconds": execution_time_seconds,
        "properties_snapshot": props_snapshot,
        "circuits": circuits_data,
    }

    
    validate_record_provenance(record, is_dryrun=is_dryrun)
    
    # Save atomically to disk
    tmp_path = raw_filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    tmp_path.rename(raw_filepath)
    
    logger.info(f"Successfully saved round {round_id} data to {raw_filepath}")
    return raw_filepath
