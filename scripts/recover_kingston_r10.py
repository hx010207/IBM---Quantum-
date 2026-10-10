#!/usr/bin/env python3
"""Recover completed job db4gqkcvf2bc73cujge0 for ibm_kingston Round 10."""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from qiskit_ibm_runtime import QiskitRuntimeService
from qfp.budget import QPUBudgetGuard
from qfp.circuits import build_benchmark_circuits, transpile_benchmark_circuits
from qfp.collect import chunk_bitstrings_into_samples, extract_backend_properties_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recover_kingston_r10")


def main():
    service = QiskitRuntimeService(
        channel=os.environ.get("QISKIT_IBM_CHANNEL", "ibm_quantum_platform"),
        token=os.environ.get("QISKIT_IBM_TOKEN"),
        instance=os.environ.get("QISKIT_IBM_INSTANCE"),
    )
    job_id = "db4gqkcvf2bc73cujge0"
    logger.info(f"Retrieving completed job {job_id}...")
    job = service.job(job_id)
    status = job.status()
    logger.info(f"Job status: {status}")
    if str(status) != "DONE":
        logger.error(f"Job {job_id} is not DONE! Status is {status}")
        sys.exit(1)

    backend_name = "ibm_kingston"
    layout = [89, 90, 91]
    shots = 2048
    num_chunks = 8
    round_id = 10

    backend = service.backend(backend_name)
    logical_circuits = build_benchmark_circuits(seed=42, backend=backend)
    transpiled, transpile_path = transpile_benchmark_circuits(
        logical_circuits,
        backend=backend,
        initial_layout=layout,
        optimization_level=1,
        return_path=True,
    )

    logger.info("Fetching job results...")
    result = job.result()

    usage_data = getattr(job, "usage", lambda: None)()
    q_sec = 8.0
    if isinstance(usage_data, (int, float)):
        q_sec = float(usage_data)
    elif isinstance(usage_data, dict):
        q_sec = float(usage_data.get("quantum_seconds", 8.0))

    circuits_data = {}
    for (cid, _), pub_res in zip(transpiled.items(), result):
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

    props_snapshot = extract_backend_properties_snapshot(backend, layout)

    metrics = getattr(job, "metrics", lambda: None)()
    ts = metrics.get("timestamps", {}) if metrics else {}
    start_str = ts.get("created", "2026-10-09T15:50:41.294304Z")
    end_str = ts.get("finished", "2026-10-09T18:48:52.779505Z")

    record = {
        "round_id": round_id,
        "backend": backend_name,
        "provenance": "ibm_hardware",
        "transpile_path": transpile_path,
        "physical_layout": layout,
        "shots_per_circuit": shots,
        "num_chunks": num_chunks,
        "start_timestamp": start_str,
        "end_timestamp": end_str,
        "job_id": job_id,
        "execution_time_seconds": q_sec,
        "properties_snapshot": props_snapshot,
        "circuits": circuits_data,
    }

    out_dir = PROJECT_ROOT / "data" / "raw" / backend_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"round_{round_id:03d}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    logger.info(f"Saved recovered round to {out_file}")

    # Update budget guard
    guard = QPUBudgetGuard()
    guard.record_consumption(q_sec)
    logger.info(f"Updated QPUBudgetGuard (+{q_sec:.1f}s). Cumulative: {guard.cumulative_quantum_seconds:.1f}s")


if __name__ == "__main__":
    main()
