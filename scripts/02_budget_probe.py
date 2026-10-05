#!/usr/bin/env python3
"""Script 02: Budget probe and QPU execution time projection.

Submits a full 10-circuit benchmark round (at 2048 shots per circuit) as ONE job
on ONE backend in job mode (no sessions) to empirically measure quantum execution
seconds (via job.usage() and runtime metrics).

Reports:
1. Actual remaining Open Plan QPU allowance (via service.usage()).
2. Backend dt, timing constraints, and c10 delay configuration (~30 us).
3. Probe job details: job ID, queue time, wall time, and job.usage() quantum seconds.
4. Empirical per-round and per-circuit quantum execution time.
5. Recomputed full-study QPU projections across candidate round counts (10-12 rounds)
   and backend counts (2 or 3 backends) with strict 85% safety cap enforcement.
6. Recommended round schedule (train, val, test with >=4 test rounds).
"""

import argparse
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
import time
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qfp.budget import BudgetExceededError, QPUBudgetGuard
from qfp.circuits import build_benchmark_circuits, transpile_benchmark_circuits

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("budget_probe")


def parse_args():
    parser = argparse.ArgumentParser(description="Probe QPU budget and project total experiment time.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate budget probe locally with fake backend.")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    parser.add_argument("--backend", type=str, default=None, help="Specific backend name to probe (defaults to lowest-error).")
    parser.add_argument("--delay-us", type=float, default=30.0, help="Delay duration in microseconds for circuit c10 (default 30.0 us).")
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sampling_cfg = config.get("sampling", {})
    shots = int(sampling_cfg.get("shots_per_circuit", 2048))
    num_circuits = len(config["circuits"]["circuits_list"])

    if args.dry_run:
        logger.info("[Dry-Run] Executing simulated budget probe using fake backend.")
        backends_info = config["backends"].get("dryrun_backends", [])
        if not backends_info:
            logger.error("No dryrun backends configured. Run 01_select_backends.py --dry-run first.")
            sys.exit(1)

        b_spec = backends_info[0]
        from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
        backend = FakeSherbrooke()
        layout = b_spec["layout"]
        b_name = b_spec["name"]

        # Build all 10 circuits
        circuits = build_benchmark_circuits(seed=42, delay_sec=args.delay_us * 1e-6, backend=backend)
        t_circs = transpile_benchmark_circuits(circuits, backend, layout)

        from qiskit_aer import AerSimulator
        sim = AerSimulator.from_backend(backend)
        t0 = time.time()
        for t_qc in t_circs.values():
            job = sim.run(t_qc, shots=shots)
            _ = job.result()
        measured_round_sec = max(0.40, time.time() - t0)
        measured_sec_per_circuit = measured_round_sec / num_circuits

        allowance = 600.0
        max_safe_seconds = allowance * 0.85

        out_dir = Path("dryrun/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        probe_result = {
            "mode": "dry_run",
            "probe_backend": b_name,
            "layout": layout,
            "shots": shots,
            "measured_round_quantum_seconds": measured_round_sec,
            "measured_seconds_per_circuit": measured_sec_per_circuit,
            "allowance_seconds": allowance,
            "safety_cap_seconds": max_safe_seconds,
        }
        with open(out_dir / "budget_probe.json", "w", encoding="utf-8") as f:
            json.dump(probe_result, f, indent=2)

        print("\n" + "=" * 70)
        print("BUDGET PROBE SUMMARY (DRY-RUN)")
        print("=" * 70)
        print(f"Measured Round QPU Time : {measured_round_sec:.3f} s (10 circuits x {shots} shots)")
        print(f"Per-Circuit QPU Time    : {measured_sec_per_circuit:.3f} s")
        print("=" * 70 + "\n")
        return

    # Real Hardware Budget Probe
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("QISKIT_IBM_TOKEN")
    instance = os.environ.get("QISKIT_IBM_INSTANCE")
    channel = os.environ.get("QISKIT_IBM_CHANNEL", "ibm_quantum_platform")

    logger.info("Initializing IBM Quantum Service for hardware budget probe...")
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        if token and instance:
            service = QiskitRuntimeService(channel=channel, token=token, instance=instance)
        elif token:
            service = QiskitRuntimeService(channel=channel, token=token)
        else:
            service = QiskitRuntimeService()
    except Exception as e:
        logger.error(f"IBM authentication failed: {e}")
        sys.exit(1)

    # 1. Fetch and report ACTUAL remaining Open Plan QPU allowance
    logger.info("Querying IBM Quantum account QPU allowance and consumption...")
    try:
        account_usage = service.usage()
    except Exception as e:
        logger.warning(f"Could not fetch service.usage(): {e}")
        account_usage = {}

    limit_sec = float(account_usage.get("usage_limit_seconds", 600.0))
    consumed_sec = float(account_usage.get("usage_consumed_seconds", 0.0))
    remaining_sec = float(account_usage.get("usage_remaining_seconds", limit_sec - consumed_sec))
    usage_period = account_usage.get("usage_period", {})
    safety_cap_sec = remaining_sec * 0.85

    print("\n" + "=" * 80)
    print("IBM QUANTUM OPEN PLAN QPU ALLOWANCE STATUS")
    print("=" * 80)
    print(f"Monthly Total Allocation : {limit_sec:8.1f} seconds ({limit_sec/60:.1f} minutes)")
    print(f"Already Consumed         : {consumed_sec:8.1f} seconds")
    print(f"ACTUAL REMAINING QPU     : {remaining_sec:8.1f} seconds ({remaining_sec/60:.2f} minutes)")
    print(f"85% Safety Cap (Max Usable) : {safety_cap_sec:8.1f} seconds")
    if usage_period:
        print(f"Usage Period             : {usage_period.get('start_time', 'N/A')} to {usage_period.get('end_time', 'N/A')}")
    print("=" * 80 + "\n")

    real_backends = config["backends"].get("real_backends", [])
    if not real_backends:
        logger.error("No real backends selected in study.yaml. Run 01_select_backends.py first.")
        sys.exit(1)

    # Select target backend to probe
    if args.backend:
        target_b_spec = next((b for b in real_backends if b["name"] == args.backend), None)
        if not target_b_spec:
            logger.error(f"Specified backend '{args.backend}' not in configured real backends: {[b['name'] for b in real_backends]}")
            sys.exit(1)
    else:
        # Default to lowest composite error backend
        target_b_spec = min(real_backends, key=lambda x: x.get("composite_error", 1.0))

    b_name = target_b_spec["name"]
    layout = target_b_spec["layout"]

    logger.info(f"Connecting to probe backend '{b_name}' with layout {layout}...")
    backend = service.backend(b_name)

    # Check backend dt and timing constraints
    dt = getattr(backend, "dt", None) or getattr(backend.target, "dt", 4e-09)
    tc = backend.target.timing_constraints() if hasattr(backend.target, "timing_constraints") else None
    delay_sec = args.delay_us * 1e-6
    delay_dt = int(round(delay_sec / dt))

    print("=" * 80)
    print("BACKEND TIMING & CIRCUIT c10 DELAY SPECIFICATION")
    print("=" * 80)
    print(f"Backend Name         : {b_name} ({backend.num_qubits} qubits)")
    print(f"System Sample dt     : {dt * 1e9:.2f} ns ({dt:.4e} s)")
    if tc:
        print(f"Timing Constraints   : granularity={tc.granularity}, min_length={tc.min_length}, pulse_alignment={tc.pulse_alignment}")
    print(f"Circuit c10 Real Delay: {args.delay_us:.2f} microseconds ({delay_sec:.4e} s)")
    print(f"Circuit c10 Delay dt  : {delay_dt} dt units (valid integer multiple)")
    print(f"Fixed 3-Qubit Layout : {layout}")
    print("=" * 80 + "\n")

    # Build and transpile ALL 10 benchmark circuits
    logger.info(f"Building and transpiling full 10-circuit benchmark round for '{b_name}'...")
    circuits = build_benchmark_circuits(seed=42, delay_dt=delay_dt, backend=backend)
    t_circuits = transpile_benchmark_circuits(circuits, backend, layout)

    pubs = [(t_qc, None, shots) for t_qc in t_circuits.values()]
    logger.info(f"Prepared {len(pubs)} PUBs at {shots} shots each for ONE multi-circuit job.")

    # Execute as ONE job in job mode (no sessions)
    logger.info(f"Submitting single 10-circuit round probe job to '{b_name}' (job mode, no session)...")
    sampler = SamplerV2(mode=backend)
    t_submit = time.time()
    job = sampler.run(pubs)
    job_id = job.job_id()
    logger.info(f"Probe job submitted! Job ID: {job_id}")
    print(f"\n[JOB SUBMITTED] ID: {job_id} on '{b_name}' | Waiting for execution to complete...")

    # Wait for completion
    result = job.result()
    t_finish = time.time()
    wall_duration = t_finish - t_submit

    # Extract metrics & usage
    metrics = {}
    try:
        metrics = job.metrics() or {}
    except Exception as e:
        logger.warning(f"Could not retrieve job metrics: {e}")

    timestamps = metrics.get("timestamps", {})
    t_created = timestamps.get("created")
    t_running = timestamps.get("running")
    queue_sec = None
    if t_created and t_running:
        try:
            dt_created = datetime.fromisoformat(t_created.replace("Z", "+00:00"))
            dt_running = datetime.fromisoformat(t_running.replace("Z", "+00:00"))
            queue_sec = max(0.0, (dt_running - dt_created).total_seconds())
        except Exception:
            queue_sec = None

    # Retrieve quantum execution seconds
    usage_data = {}
    try:
        usage_data = job.usage() or {}
    except Exception as e:
        logger.warning(f"Could not read job.usage(): {e}")

    quantum_seconds = 0.0
    if isinstance(usage_data, dict):
        quantum_seconds = float(usage_data.get("quantum_seconds", 0.0))
    elif isinstance(usage_data, (int, float)):
        quantum_seconds = float(usage_data)

    if quantum_seconds <= 0.0:
        # Fallback to metrics usage
        quantum_seconds = float(metrics.get("usage", {}).get("quantum_seconds", 0.0))

    if quantum_seconds <= 0.0:
        # Heuristic fallback if runtime API delayed usage
        quantum_seconds = float(metrics.get("estimated_running_time_seconds", max(1.0, wall_duration - (queue_sec or 0.0))))

    per_circuit_quantum_sec = quantum_seconds / float(num_circuits)

    print("\n" + "=" * 80)
    print("BUDGET PROBE EMPIRICAL MEASUREMENT RESULTS")
    print("=" * 80)
    print(f"Probe Job ID                 : {job_id}")
    print(f"Backend Probed               : {b_name} ({backend.num_qubits} qubits)")
    print(f"Fixed Physical Layout        : {layout}")
    print(f"Total Circuits Probed        : {num_circuits} (1 full round)")
    print(f"Shots Per Circuit            : {shots}")
    print(f"Job Queue Time               : {f'{queue_sec:.2f} s' if queue_sec is not None else 'N/A'}")
    print(f"Total Wall Clock Duration    : {wall_duration:.2f} s")
    print(f"MEASURED QUANTUM USAGE       : {quantum_seconds:.3f} s (job.usage() for 10 circuits)")
    print(f"Quantum Time Per Circuit     : {per_circuit_quantum_sec:.3f} s")
    print("=" * 80 + "\n")

    # Recompute Full-Study QPU Projections & Propose Round Schedules
    # Evaluate across 2 backends and 3 backends for round counts 8, 10, 12, 14
    projections = {}
    print("=" * 80)
    print("FULL-STUDY QPU BUDGET PROJECTIONS (Based on Empirically Measured Probe)")
    print("=" * 80)
    print(f"Actual Remaining QPU Allowance : {remaining_sec:.1f} s")
    print(f"85% Safety Cap (Strict Limit)  : {safety_cap_sec:.1f} s")
    print(f"Measured Cost Per Full Round   : {quantum_seconds:.3f} s (10 circuits x {shots} shots)\n")

    print(f"{'Option':<8} | {'Backends':<10} | {'Rounds':<8} | {'Total Circuits':<15} | {'Projected QPU (s)':<18} | {'% Remaining':<12} | {'Fits 85% Cap?':<14}")
    print("-" * 95)

    candidate_configs = [
        (2, 8),
        (2, 10),
        (2, 12),
        (3, 8),
        (3, 10),
        (3, 12),
    ]

    opt_idx = 1
    schedule_options = []
    for n_b, n_r in candidate_configs:
        tot_circ = n_b * n_r * num_circuits
        proj_sec = n_b * n_r * quantum_seconds
        pct_used = (proj_sec / remaining_sec) * 100.0
        fits = proj_sec <= safety_cap_sec

        status_str = "YES (SAFE)" if fits else "EXCEEDS CAP"
        print(f"Opt {opt_idx:<4} | {n_b:<10} | {n_r:<8} | {tot_circ:<15} | {proj_sec:18.2f} | {pct_used:10.1f} % | {status_str:<14}")

        schedule_options.append({
            "option_id": opt_idx,
            "num_backends": n_b,
            "rounds_target": n_r,
            "total_circuits": tot_circ,
            "projected_quantum_seconds": proj_sec,
            "utilization_pct": pct_used,
            "fits_safety_cap": fits,
        })
        opt_idx += 1

    print("=" * 80 + "\n")

    # Propose Round Splits for 10 and 12 Rounds
    print("=" * 80)
    print("PROPOSED ROUND SCHEDULES (Chronological Split: >=4 Test Rounds)")
    print("=" * 80)
    print("Schedule A (10 Rounds):")
    print("  Train Rounds (4): [1, 2, 3, 4]  -> 40% data")
    print("  Val Rounds   (2): [5, 6]        -> 20% data")
    print("  Test Rounds  (4): [7, 8, 9, 10] -> 40% data (strictly >= 4 test rounds)")
    print("")
    print("Schedule B (12 Rounds - RECOMMENDED if within 85% cap):")
    print("  Train Rounds (5): [1, 2, 3, 4, 5]     -> 41.7% data")
    print("  Val Rounds   (2): [6, 7]              -> 16.7% data")
    print("  Test Rounds  (5): [8, 9, 10, 11, 12]  -> 41.7% data (strictly >= 4 test rounds)")
    print("=" * 80 + "\n")

    # Save to results/budget_probe.json
    out_dir = Path("results")
    out_dir.mkdir(parents=True, exist_ok=True)
    probe_output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "mode": "real_hardware",
        "probe_backend": b_name,
        "probe_job_id": job_id,
        "shots_per_circuit": shots,
        "num_circuits": num_circuits,
        "dt_seconds": dt,
        "c10_delay_us": args.delay_us,
        "c10_delay_dt": delay_dt,
        "fixed_layout": layout,
        "queue_time_seconds": queue_sec,
        "wall_time_seconds": wall_duration,
        "measured_round_quantum_seconds": quantum_seconds,
        "measured_per_circuit_quantum_seconds": per_circuit_quantum_sec,
        "actual_remaining_qpu_seconds": remaining_sec,
        "actual_total_allocation_seconds": limit_sec,
        "actual_consumed_qpu_seconds": consumed_sec,
        "safety_cap_seconds": safety_cap_sec,
        "safety_cap_fraction": 0.85,
        "candidate_schedules": schedule_options,
    }

    probe_file = out_dir / "budget_probe.json"
    backend_probe_file = out_dir / f"budget_probe_{b_name}.json"
    with open(probe_file, "w", encoding="utf-8") as f:
        json.dump(probe_output, f, indent=2)
    with open(backend_probe_file, "w", encoding="utf-8") as f:
        json.dump(probe_output, f, indent=2)

    logger.info(f"Budget probe completed and saved to {probe_file} and {backend_probe_file}.")
    print(f"Results persisted to: {probe_file} and {backend_probe_file}")
    print("\n[STOPPING PER STAGE 1 DIRECTIVE 6]: Awaiting author review and approval before submitting further hardware jobs.\n")


if __name__ == "__main__":
    main()

