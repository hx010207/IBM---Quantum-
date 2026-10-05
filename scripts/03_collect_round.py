#!/usr/bin/env python3
"""Script 03: Collect an experimental round on IBM Quantum hardware or dry-run backends.

Runs the 10 benchmark circuits in a single batch/job per backend with fixed physical
qubit layout, 2048 shots, and records raw bitstrings, 8 chronological chunks,
and backend calibration properties snapshots.

Idempotent and resumable: skips already collected (backend, round_id) pairs.
"""

import argparse
import logging
import os
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qfp.budget import QPUBudgetGuard
from qfp.collect import run_collection_round

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("collect_round")


def parse_args():
    parser = argparse.ArgumentParser(description="Collect benchmark circuit measurements for a specific round.")
    parser.add_argument("--round-id", type=int, required=True, help="Chronological round number (e.g. 1 to 8).")
    parser.add_argument("--backend", type=str, default=None, help="Target specific backend name (optional).")
    parser.add_argument("--shots", type=int, default=None, help="Shots per circuit (overrides config).")
    parser.add_argument("--chunks", type=int, default=None, help="Chunks per round (overrides config).")
    parser.add_argument("--min-gap-hours", type=float, default=4.0, help="Minimum wall-clock gap in hours required since previous round (default 4.0h).")
    parser.add_argument("--force", action="store_true", help="Bypass min-gap-hours check.")
    parser.add_argument("--dry-run", action="store_true", help="Run locally using fake backends.")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sampling_cfg = config.get("sampling", {})
    shots = args.shots or int(sampling_cfg.get("shots_per_circuit", 2048))
    num_chunks = args.chunks or int(sampling_cfg.get("chunks_per_round", 8))
    round_id = args.round_id
    min_gap_hours = args.min_gap_hours

    budget_guard = None
    if not args.dry_run:
        budget_guard = QPUBudgetGuard()

    if args.dry_run:
        logger.info(f"[Dry-Run] Executing Round {round_id} on fake backends.")
        from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeBrisbane, FakeKyiv
        fake_map = {
            "fake_sherbrooke": FakeSherbrooke,
            "fake_brisbane": FakeBrisbane,
            "fake_kyiv": FakeKyiv,
        }
        
        backends_cfg = config["backends"].get("dryrun_backends", [])
        if args.backend:
            backends_cfg = [b for b in backends_cfg if b["name"] == args.backend]

        for b_entry in backends_cfg:
            b_name = b_entry["name"]
            layout = b_entry["layout"]
            logger.info(f"Processing Round {round_id} for dry-run backend '{b_name}' with layout {layout}...")
            
            backend_cls = fake_map.get(b_name, FakeSherbrooke)
            backend_obj = backend_cls()
            
            raw_path = run_collection_round(
                backend=backend_obj,
                layout=layout,
                round_id=round_id,
                shots=shots,
                num_chunks=num_chunks,
                is_dryrun=True,
                seed=42,
            )
            logger.info(f"Finished Round {round_id} for '{b_name}': {raw_path}")
        return

    # Real Hardware Execution
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("QISKIT_IBM_TOKEN")
    instance = os.environ.get("QISKIT_IBM_INSTANCE")
    channel = os.environ.get("QISKIT_IBM_CHANNEL", "ibm_quantum_platform")

    logger.info("Initializing IBM Quantum Service for real hardware collection...")
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        if token and instance:
            service = QiskitRuntimeService(channel=channel, token=token, instance=instance)
        elif token:
            service = QiskitRuntimeService(channel=channel, token=token)
        else:
            service = QiskitRuntimeService()
    except Exception as e:
        logger.error(f"IBM authentication failed: {e}")
        sys.exit(1)

    real_backends_cfg = config["backends"].get("real_backends", [])
    if not real_backends_cfg:
        logger.error("No real backends specified in study.yaml. Run 01_select_backends.py first.")
        sys.exit(1)

    if args.backend:
        real_backends_cfg = [b for b in real_backends_cfg if b["name"] == args.backend]

    round_results = []
    for b_entry in real_backends_cfg:
        b_name = b_entry["name"]
        layout = b_entry["layout"]

        # Check time gap from previous round if round_id > 1
        elapsed_hours = None
        if round_id > 1 and not args.dry_run:
            from datetime import datetime, timezone
            prev_file = Path("data/raw") / b_name / f"round_{round_id - 1:03d}.json"
            if prev_file.exists():
                import json
                with open(prev_file, "r", encoding="utf-8") as f:
                    prev_rec = json.load(f)
                prev_end_str = prev_rec.get("end_timestamp") or prev_rec.get("start_timestamp")
                if prev_end_str:
                    prev_dt = datetime.fromisoformat(prev_end_str.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    elapsed_sec = (now_dt - prev_dt).total_seconds()
                    elapsed_hours = elapsed_sec / 3600.0
                    if elapsed_hours < min_gap_hours and not args.force:
                        logger.error(
                            f"Time gap guard triggered for '{b_name}': Only {elapsed_hours:.2f}h elapsed since Round {round_id - 1} "
                            f"(minimum required: {min_gap_hours:.2f}h). Halting to preserve protocol."
                        )
                        print(f"\n[TIME GAP GUARD TRIGGERED]: Only {elapsed_hours:.2f}h elapsed since Round {round_id - 1} on '{b_name}' (minimum required: {min_gap_hours:.2f}h).")
                        print(f"Next allowed submission on '{b_name}' is after {(min_gap_hours - elapsed_hours):.2f}h.\n")
                        sys.exit(3)

        logger.info(f"Connecting to IBM backend '{b_name}' (layout: {layout}) for Round {round_id}...")
        backend_obj = service.backend(b_name)

        raw_path = run_collection_round(
            backend=backend_obj,
            layout=layout,
            round_id=round_id,
            shots=shots,
            num_chunks=num_chunks,
            is_dryrun=False,
            budget_guard=budget_guard,
            seed=42,
        )
        logger.info(f"Finished hardware Round {round_id} on '{b_name}': {raw_path}")

        # Read saved record to extract exact job details
        import json
        with open(raw_path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        round_results.append({
            "backend": b_name,
            "job_id": rec.get("job_id"),
            "layout": layout,
            "quantum_seconds": rec.get("execution_time_seconds", 0.0),
            "file": str(raw_path),
            "wall_clock_gap_hours": elapsed_hours,
        })

    print("\n" + "=" * 95)
    print(f"STAGE 2: HARDWARE DATA COLLECTION — ROUND {round_id} SUMMARY")
    print("=" * 95)
    total_round_seconds = sum(r["quantum_seconds"] for r in round_results)
    running_total = budget_guard.used_seconds if budget_guard else total_round_seconds
    cap = budget_guard.max_allowed_seconds if budget_guard else 510.0
    allowance = budget_guard.allowance_seconds if budget_guard else 600.0

    print(f"{'Backend':<16} | {'Job ID':<26} | {'Layout':<15} | {'Quantum Time':<14} | {'Gap from Prev':<14}")
    print("-" * 95)
    for r in round_results:
        gap_str = f"{r['wall_clock_gap_hours']:.2f} h" if r['wall_clock_gap_hours'] is not None else "Round 1 (Init)"
        print(f"{r['backend']:<16} | {str(r['job_id']):<26} | {str(r['layout']):<15} | {r['quantum_seconds']:>8.3f} s    | {gap_str:<14}")
    print("-" * 95)
    print(f"Round {round_id} QPU Consumption           : {total_round_seconds:>8.3f} s")
    print(f"Running Total QPU Consumed So Far   : {running_total:>8.3f} s / {cap:.1f} s (85% Safety Cap)")
    print(f"Safety Cap Utilization              : {(running_total / cap) * 100.0:>8.1f} %")
    print(f"Total Monthly Allowance Used        : {(running_total / allowance) * 100.0:>8.1f} % ({allowance:.1f} s total)")
    print(f"Remaining Safe QPU Budget           : {max(0.0, cap - running_total):>8.3f} s")
    print("=" * 85 + "\n")


if __name__ == "__main__":
    main()

