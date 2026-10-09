#!/usr/bin/env python3
"""Recover completed job db4c73o4qg6s73c1vucg for ibm_kingston Round 9."""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from qiskit_ibm_runtime import QiskitRuntimeService
from qfp.budget import QPUBudgetGuard
from qfp.circuits import build_benchmark_circuits, transpile_benchmark_circuits
from qfp.collect import chunk_bitstrings_into_samples, extract_backend_properties_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recover_kingston")

def main():
    service = QiskitRuntimeService(
        channel=os.environ.get("QISKIT_IBM_CHANNEL", "ibm_quantum_platform"),
        token=os.environ.get("QISKIT_IBM_TOKEN"),
        instance=os.environ.get("QISKIT_IBM_INSTANCE"),
    )
    job_id = "db4c73o4qg6s73c1vucg"
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
    round_id = 9

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

    created_time = getattr(job, "creation_date", None)
    if callable(created_time):
        created_time = created_time()
    created_str = created_time.isoformat() if created_time else "2026-10-09T10:32:01.000000Z"
    end_str = datetime.now(timezone.utc).isoformat()

    record = {
        "round_id": round_id,
        "backend": backend_name,
        "provenance": "ibm_hardware",
        "transpile_path": transpile_path,
        "physical_layout": layout,
        "shots_per_circuit": shots,
        "num_chunks": num_chunks,
        "start_timestamp": created_str,
        "end_timestamp": end_str,
        "job_id": job_id,
        "execution_time_seconds": q_sec,
        "properties_snapshot": props_snapshot,
        "circuits": circuits_data,
    }

    out_file = Path("data/raw") / backend_name / f"round_{round_id:03d}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    logger.info(f"Successfully saved {out_file} (execution time: {q_sec}s)")

    budget_guard = QPUBudgetGuard()
    budget_guard.record_job_consumption(q_sec, job_id=job_id, is_dryrun=False)
    logger.info(f"Recorded budget usage. Total cumulative: {budget_guard.used_seconds:.2f}s / 510.0s")

if __name__ == "__main__":
    main()
